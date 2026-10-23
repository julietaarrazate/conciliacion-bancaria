"""Límites de uso: IP real del cliente para slowapi y cupo diario de IA por organización.

IP real: Render pone el backend detrás de su proxy, así que `request.client.host` es la
IP del proxy y todos los usuarios compartían el mismo contador de slowapi (un atacante
con pocos intentos bloqueaba el login o la recuperación de contraseña de todos). El
proxy agrega la IP de quien le habló al final de `X-Forwarded-For`; lo que viene antes
lo puede escribir el cliente. Por eso se toma la primera IP pública contando desde la
derecha: no se puede falsificar mandando un `X-Forwarded-For` propio.

Cupo de IA: una fila por (organización, día, tipo) en `uso_ia_diario`. El incremento
es un único INSERT ... ON CONFLICT DO UPDATE ... WHERE cantidad < tope, así dos pedidos
simultáneos no pasan el tope.
"""
import ipaddress
import os
from datetime import date
from typing import Optional

from fastapi import HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app.models.uso_ia import UsoIaDiario
from app.services.excel_safe import verificar_xlsx
from app.services.tz import hoy_art

# Topes diarios por organización (configurables por env var en Render).
TOPES_IA_DEFAULT = {"chat": 200, "ocr": 100, "audio": 100}
_ENV_TOPE = {"chat": "IA_TOPE_DIARIO_CHAT", "ocr": "IA_TOPE_DIARIO_OCR", "audio": "IA_TOPE_DIARIO_AUDIO"}

_MENSAJES_TOPE = {
    "chat": "Tu organización llegó al límite diario del asistente IA. Volvé mañana 🙂",
    "ocr": "Tu organización llegó al límite diario de lectura de fotos con IA. Volvé mañana.",
    "audio": "Tu organización llegó al límite diario de transcripción de audios. Volvé mañana.",
}

# Tamaño máximo de un archivo que se manda a la IA (audio o foto).
MAX_BYTES_IA = 10 * 1024 * 1024
# Tamaño máximo de una planilla subida (Excel/CSV de clientes, tarjetas, Mis Comprobantes,
# cheques). Los extractos bancarios usan `settings.max_file_size` (50 MB).
MAX_BYTES_PLANILLA = 15 * 1024 * 1024


def ip_cliente(request: Request) -> str:
    """IP real del cliente detrás del proxy de Render (key_func de slowapi)."""
    xff = request.headers.get("x-forwarded-for", "")
    for parte in reversed([p.strip() for p in xff.split(",") if p.strip()]):
        try:
            ip = ipaddress.ip_address(parte)
        except ValueError:
            continue
        if ip.is_global:
            return str(ip)
    return request.client.host if request.client else "desconocida"


def tope_ia(tipo: str) -> int:
    try:
        return int(os.environ.get(_ENV_TOPE[tipo], TOPES_IA_DEFAULT[tipo]))
    except ValueError:
        return TOPES_IA_DEFAULT[tipo]


def consumir_cupo_ia(db: Session, organizacion_id: int, tipo: str, cantidad: int = 1) -> int:
    """Suma `cantidad` llamadas al cupo del día de la organización.

    Devuelve el total usado hoy. Si con esta suma se pasa el tope, no suma nada y
    responde 429 (el cupo es por organización: no lo gasta otra)."""
    tope = tope_ia(tipo)
    hoy = hoy_art()
    if cantidad > tope:
        raise HTTPException(429, _MENSAJES_TOPE[tipo])

    if db.bind.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert

    tabla = UsoIaDiario.__table__
    stmt = insert(tabla).values(
        organizacion_id=organizacion_id, fecha=hoy, tipo=tipo, cantidad=cantidad,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["organizacion_id", "fecha", "tipo"],
        set_={"cantidad": tabla.c.cantidad + cantidad},
        where=tabla.c.cantidad + cantidad <= tope,
    ).returning(tabla.c.cantidad)
    usado = db.execute(stmt).scalar()
    db.commit()
    if usado is None:  # la fila existía y el WHERE frenó el UPDATE: cupo agotado
        raise HTTPException(429, _MENSAJES_TOPE[tipo])
    return usado


def uso_ia(db: Session, organizacion_id: int, tipo: str, fecha: Optional[date] = None) -> dict:
    """Uso del día para mostrar en Perfil: {used, limit, remaining, date}."""
    fecha = fecha or hoy_art()
    fila = db.query(UsoIaDiario).filter(
        UsoIaDiario.organizacion_id == organizacion_id,
        UsoIaDiario.fecha == fecha,
        UsoIaDiario.tipo == tipo,
    ).first()
    usado = fila.cantidad if fila else 0
    tope = tope_ia(tipo)
    return {"used": usado, "limit": tope, "remaining": max(0, tope - usado), "date": str(fecha)}


async def leer_archivo(archivo: UploadFile, maximo: int) -> bytes:
    """Lee un archivo subido cortando en `maximo` bytes (413 si es más grande).

    Lee como mucho `maximo + 1` bytes: un archivo enorme no se carga entero en memoria."""
    raw = await archivo.read(maximo + 1)
    if len(raw) > maximo:
        raise HTTPException(413, f"El archivo supera el máximo de {maximo // (1024 * 1024)} MB")
    return raw


async def leer_archivo_ia(archivo: UploadFile, maximo: int = MAX_BYTES_IA) -> bytes:
    """Lee un archivo para mandar a la IA (audio o foto) con el tope de la IA."""
    return await leer_archivo(archivo, maximo)


async def leer_planilla(archivo: UploadFile, maximo: int = MAX_BYTES_PLANILLA) -> bytes:
    """Lee una planilla subida (.xlsx/.xls/.csv) con tope de tamaño y chequeo de zip bomb.

    Punto único antes de pasarle el archivo a openpyxl/pandas: si es un .xlsx (ZIP), revisa
    el tamaño descomprimido y la tasa de compresión (`excel_safe.verificar_xlsx`, 413)."""
    raw = await leer_archivo(archivo, maximo)
    verificar_xlsx(raw)
    return raw
