"""Comprobantes por revisar: lectura con IA de facturas de compra, controles
automáticos, recepción por mail (Resend Inbound) y confirmación hacia IVA/Pagos.

Diseño (ver `docs/business/COMPROBANTES_POR_REVISAR.md`):
  - Nada impacta solo: la IA deja un borrador y una persona lo confirma.
  - Al confirmar se crea un `ComprobanteIva` (dirección "recibido") con el mismo
    unique que usa el import de "Mis Comprobantes" → si después se importa el
    Excel de ARCA, la factura cuenta como duplicada y no se suma dos veces.
  - Opcionalmente se crea el `Egreso` (pago a proveedor por banco) con su asiento,
    usando el mismo motor contable que el módulo Pagos.
  - No toca la conciliación ni el cálculo de la liquidación de IVA.

Las funciones de normalización/validación y la verificación de firma del webhook
son puras para poder testearlas sin red ni Gemini.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import re
import secrets
import time
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.comprobante_compra import BorradorComprobante, BuzonComprobantes
from app.models.egreso import Egreso
from app.models.iva_liquidacion import ComprobanteIva
from app.services.iva_liquidacion_service import es_nota_credito
from app.services.tz import hoy_art

logger = logging.getLogger(__name__)

_DOS = Decimal("0.01")

MAX_ARCHIVO_BYTES = 5 * 1024 * 1024        # 5 MB por archivo (igual que LaPyme / Gemini inline)
MAX_ARCHIVOS_POR_SUBIDA = 10
MIMES_PERMITIDOS = {
    "application/pdf", "image/jpeg", "image/jpg", "image/png", "image/webp",
}

# Alícuotas de IVA (mismas claves que el parser de "Mis Comprobantes").
ALICUOTAS = {
    "0%": Decimal("0"),
    "2.5%": Decimal("0.025"),
    "5%": Decimal("0.05"),
    "10.5%": Decimal("0.105"),
    "21%": Decimal("0.21"),
    "27%": Decimal("0.27"),
}

# Códigos ARCA de los comprobantes que se esperan como compra.
TIPOS_COMPROBANTE = {
    1: "Factura A", 2: "Nota de Débito A", 3: "Nota de Crédito A",
    6: "Factura B", 7: "Nota de Débito B", 8: "Nota de Crédito B",
    11: "Factura C", 12: "Nota de Débito C", 13: "Nota de Crédito C",
    51: "Factura M", 52: "Nota de Débito M", 53: "Nota de Crédito M",
    201: "Factura de Crédito Electrónica MiPyMEs (FCE) A",
    206: "Factura de Crédito Electrónica MiPyMEs (FCE) B",
    211: "Factura de Crédito Electrónica MiPyMEs (FCE) C",
}
_TIPOS_A = {1, 2, 3, 51, 52, 53, 201}
_TIPOS_C = {11, 12, 13, 211}
# Letra + clase → código, para cuando la IA devuelve "A"/"FACTURA" en vez del código.
_LETRA_CLASE = {
    ("A", "factura"): 1, ("A", "debito"): 2, ("A", "credito"): 3,
    ("B", "factura"): 6, ("B", "debito"): 7, ("B", "credito"): 8,
    ("C", "factura"): 11, ("C", "debito"): 12, ("C", "credito"): 13,
    ("M", "factura"): 51, ("M", "debito"): 52, ("M", "credito"): 53,
}

CAMPOS_MONTO = [
    "neto_no_gravado", "exento", "percepciones_iva", "percepciones_iibb",
    "otros_tributos", "total",
]


class ComprobanteCompraError(Exception):
    """Error de negocio (se traduce a 4xx en el router)."""

    def __init__(self, mensaje: str, status: int = 400):
        super().__init__(mensaje)
        self.status = status


# ── Prompt de la IA ───────────────────────────────────────────────

PROMPT_FACTURA = (
    "Sos un asistente contable argentino. Extraé los datos de este comprobante de COMPRA "
    "(factura, nota de crédito o nota de débito emitida por un proveedor, formato ARCA/AFIP). "
    "Respondé SOLO con un JSON válido, sin texto extra ni markdown. "
    "Montos: número decimal puro con punto decimal, sin $ ni separadores de miles "
    "(si ves '$ 1.234,56' devolvé 1234.56). Si un dato no está o no se lee, usá null; "
    "nunca inventes datos. Campos:\n"
    '{"tipo_codigo": código ARCA del comprobante (1 Factura A, 6 Factura B, 11 Factura C, '
    "3/8/13 Nota de Crédito A/B/C, 2/7/12 Nota de Débito A/B/C, 51 Factura M, "
    '201/206/211 FCE A/B/C) o null, '
    '"letra": "A"|"B"|"C"|"M" o null, '
    '"clase": "factura"|"credito"|"debito" o null, '
    '"punto_venta": entero o null, "numero": entero o null, '
    '"fecha": "YYYY-MM-DD" (fecha de emisión) o null, '
    '"cuit_emisor": CUIT del EMISOR/proveedor, 11 dígitos sin guiones, o null, '
    '"razon_social": razón social del emisor o null, '
    '"cae": número de CAE o null, '
    '"alicuotas": [{"alicuota": "21%"|"10.5%"|"27%"|"5%"|"2.5%"|"0%", '
    '"neto": neto gravado a esa alícuota, "iva": IVA de esa alícuota}] (lista vacía si no discrimina IVA), '
    '"neto_no_gravado": número o null, "exento": número o null, '
    '"percepciones_iva": número o null, "percepciones_iibb": número o null, '
    '"otros_tributos": número o null (impuestos internos, tasas, etc.), '
    '"total": importe total del comprobante o null}'
)


# ── Parseo tolerante ──────────────────────────────────────────────

def parse_decimal(raw: Any) -> Optional[Decimal]:
    """Monto del OCR → Decimal(2) tolerando formato argentino. None si no parsea."""
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, Decimal):
        return raw.quantize(_DOS)
    if isinstance(raw, (int, float)):
        try:
            return Decimal(str(raw)).quantize(_DOS)
        except (InvalidOperation, ValueError):
            return None
    s = str(raw).strip().replace("$", "").replace(" ", "")
    if not s:
        return None
    if "," in s:                     # coma = decimal argentino
        s = s.replace(".", "").replace(",", ".")
    elif s.count(".") > 1:           # varios puntos = miles
        s = s.replace(".", "")
    try:
        return Decimal(s).quantize(_DOS)
    except (InvalidOperation, ValueError):
        return None


def _parse_int(raw: Any) -> Optional[int]:
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw
    digitos = re.sub(r"\D", "", str(raw))
    if not digitos:
        return None
    try:
        return int(digitos)
    except ValueError:
        return None


def _parse_fecha(raw: Any) -> Optional[date]:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    s = str(raw).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def normalizar_cuit(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    digitos = re.sub(r"\D", "", str(raw))
    return digitos or None


def cuit_valido(cuit: Optional[str]) -> bool:
    """Dígito verificador del CUIT/CUIL (módulo 11)."""
    if not cuit or not re.fullmatch(r"\d{11}", cuit):
        return False
    pesos = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
    suma = sum(int(d) * p for d, p in zip(cuit[:10], pesos))
    resto = 11 - (suma % 11)
    dv = 0 if resto == 11 else (9 if resto == 10 else resto)
    return dv == int(cuit[10])


def _resolver_tipo(datos: dict) -> Optional[int]:
    tipo = _parse_int(datos.get("tipo_codigo"))
    if tipo in TIPOS_COMPROBANTE:
        return tipo
    letra = str(datos.get("letra") or "").strip().upper()[:1]
    clase = str(datos.get("clase") or "").strip().lower()
    if "cr" in clase:
        clase = "credito"
    elif "d" in clase[:1]:
        clase = "debito"
    elif clase:
        clase = "factura"
    return _LETRA_CLASE.get((letra, clase or "factura")) if letra else None


def _normalizar_alicuota(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    s = str(raw).strip().replace("%", "").replace(",", ".")
    try:
        valor = Decimal(s)
    except (InvalidOperation, ValueError):
        return None
    if valor > 1:            # "21" → 0.21
        valor = valor / 100
    for clave, tasa in ALICUOTAS.items():
        if abs(tasa - valor) < Decimal("0.0001"):
            return clave
    return None


# ── Normalización + controles ─────────────────────────────────────

def normalizar_datos(crudo: Optional[dict]) -> dict:
    """Respuesta (o edición) cruda → datos canónicos del borrador.

    Montos como string con 2 decimales (JSON sin pérdida de precisión).
    `alicuotas` queda como {"21%": {"neto": "...", "iva": "..."}}.
    """
    crudo = crudo or {}
    if isinstance(crudo, list):
        crudo = crudo[0] if crudo and isinstance(crudo[0], dict) else {}

    tipo = _resolver_tipo(crudo)
    fecha = _parse_fecha(crudo.get("fecha"))

    alicuotas: dict[str, dict[str, str]] = {}
    raw_ali = crudo.get("alicuotas") or []
    if isinstance(raw_ali, dict):   # ya viene en formato canónico (edición desde la UI)
        raw_ali = [{"alicuota": k, **(v or {})} for k, v in raw_ali.items()]
    for item in raw_ali:
        if not isinstance(item, dict):
            continue
        clave = _normalizar_alicuota(item.get("alicuota"))
        neto = parse_decimal(item.get("neto"))
        iva = parse_decimal(item.get("iva"))
        if clave is None or (not neto and not iva):
            continue
        previo = alicuotas.get(clave, {"neto": "0.00", "iva": "0.00"})
        alicuotas[clave] = {
            "neto": str(Decimal(previo["neto"]) + (neto or Decimal("0"))),
            "iva": str(Decimal(previo["iva"]) + (iva or Decimal("0"))),
        }

    out: dict[str, Any] = {
        "tipo_codigo": tipo,
        "punto_venta": _parse_int(crudo.get("punto_venta")),
        "numero": _parse_int(crudo.get("numero")),
        "fecha": fecha.isoformat() if fecha else None,
        "cuit_emisor": normalizar_cuit(crudo.get("cuit_emisor")),
        "razon_social": (str(crudo.get("razon_social")).strip()[:255] or None)
        if crudo.get("razon_social") else None,
        "cae": normalizar_cuit(crudo.get("cae")),
        "alicuotas": alicuotas,
    }
    for campo in CAMPOS_MONTO:
        v = parse_decimal(crudo.get(campo))
        out[campo] = str(v) if v is not None else None
    return out


def totales(datos: dict) -> dict[str, Decimal]:
    neto = sum((Decimal(a["neto"]) for a in datos["alicuotas"].values()), Decimal("0"))
    iva = sum((Decimal(a["iva"]) for a in datos["alicuotas"].values()), Decimal("0"))
    otros = sum(
        (Decimal(datos[c]) for c in ("neto_no_gravado", "exento", "percepciones_iva",
                                      "percepciones_iibb", "otros_tributos") if datos.get(c)),
        Decimal("0"),
    )
    return {"neto_gravado": neto, "iva": iva, "otros": otros,
            "suma": neto + iva + otros,
            "total": Decimal(datos["total"]) if datos.get("total") else Decimal("0")}


def validar_datos(datos: dict, hoy: Optional[date] = None) -> list[str]:
    """Controles automáticos. Devuelve textos para mostrar a la persona (vacío = todo cierra)."""
    hoy = hoy or hoy_art()
    alertas: list[str] = []

    faltan = [nombre for campo, nombre in (
        ("tipo_codigo", "tipo de comprobante"), ("punto_venta", "punto de venta"),
        ("numero", "número"), ("fecha", "fecha"), ("cuit_emisor", "CUIT del proveedor"),
        ("total", "total"),
    ) if not datos.get(campo)]
    if faltan:
        alertas.append("Falta completar: " + ", ".join(faltan) + ".")

    cuit = datos.get("cuit_emisor")
    if cuit and not cuit_valido(cuit):
        alertas.append("El CUIT del proveedor no es válido (revisá los dígitos).")

    t = totales(datos)
    if datos.get("total") and abs(t["suma"] - t["total"]) > Decimal("0.10"):
        alertas.append(
            f"La suma no cierra: neto + IVA + otros da ${t['suma']:,.2f} y el total dice "
            f"${t['total']:,.2f}.".replace(",", "X").replace(".", ",").replace("X", ".")
        )

    for clave, a in datos["alicuotas"].items():
        esperado = (Decimal(a["neto"]) * ALICUOTAS[clave]).quantize(_DOS)
        tolerancia = max(Decimal("0.10"), Decimal(a["neto"]) * Decimal("0.001"))
        if abs(esperado - Decimal(a["iva"])) > tolerancia:
            alertas.append(f"El IVA {clave} no coincide con el neto gravado a esa alícuota.")

    tipo = datos.get("tipo_codigo")
    if tipo in _TIPOS_C and t["iva"] > 0:
        alertas.append("Es un comprobante C pero tiene IVA discriminado: no genera crédito fiscal.")
    if tipo in _TIPOS_A and datos.get("total") and t["iva"] == 0 and not datos.get("exento"):
        alertas.append("Es un comprobante A sin IVA discriminado: revisá las alícuotas.")

    if datos.get("fecha"):
        f = date.fromisoformat(datos["fecha"])
        if f > hoy:
            alertas.append("La fecha del comprobante es posterior a hoy.")
        elif (hoy - f).days > 365:
            alertas.append("El comprobante tiene más de un año.")
    return alertas


def ya_cargado_en_iva(db: Session, org_id: int, datos: dict) -> Optional[ComprobanteIva]:
    if not (datos.get("tipo_codigo") and datos.get("punto_venta")
            and datos.get("numero") and datos.get("cuit_emisor")):
        return None
    return db.query(ComprobanteIva).filter(
        ComprobanteIva.organizacion_id == org_id,
        ComprobanteIva.direccion == "recibido",
        ComprobanteIva.tipo_codigo == datos["tipo_codigo"],
        ComprobanteIva.punto_venta == datos["punto_venta"],
        ComprobanteIva.numero == datos["numero"],
        ComprobanteIva.cuit_contraparte == datos["cuit_emisor"],
    ).first()


def alertas_completas(db: Session, org_id: int, datos: dict) -> list[str]:
    alertas = validar_datos(datos)
    if ya_cargado_en_iva(db, org_id, datos):
        alertas.append("Este comprobante ya está cargado en IVA.")
    return alertas


# ── Archivos ──────────────────────────────────────────────────────

def mime_normalizado(mime: Optional[str], nombre: Optional[str] = None) -> Optional[str]:
    m = (mime or "").split(";")[0].strip().lower()
    if m == "image/jpg":
        m = "image/jpeg"
    if m in MIMES_PERMITIDOS:
        return m
    ext = (nombre or "").lower().rsplit(".", 1)[-1] if nombre and "." in nombre else ""
    return {"pdf": "application/pdf", "jpg": "image/jpeg", "jpeg": "image/jpeg",
            "png": "image/png", "webp": "image/webp"}.get(ext)


def a_data_url(mime: str, contenido: bytes) -> str:
    return f"data:{mime};base64,{base64.b64encode(contenido).decode()}"


def leer_archivo(archivo: str) -> tuple[str, bytes]:
    """Devuelve (mime, bytes) de un archivo guardado como data URL o URL de R2."""
    if archivo.startswith("data:"):
        header, data = archivo.split(",", 1)
        mime = header.split(":", 1)[1].split(";", 1)[0]
        return mime, base64.b64decode(data)
    import requests
    resp = requests.get(archivo, timeout=30)
    resp.raise_for_status()
    return (resp.headers.get("content-type") or "application/pdf").split(";")[0], resp.content


# ── IA ────────────────────────────────────────────────────────────

_FACTURAS_DAILY_LIMIT = int(os.environ.get("FACTURAS_OCR_DAILY_LIMIT", "200"))


def _ocr_factura_default(mime: str, contenido: bytes) -> dict:
    """Llama a Gemini con el mismo helper que el OCR de cheques/transferencias."""
    from app.routers.agente import _call_gemini_ocr, _check_limit, _make_counter

    global _facturas_ctr
    if _facturas_ctr is None:
        _facturas_ctr = _make_counter()
    if not _check_limit(_facturas_ctr, _FACTURAS_DAILY_LIMIT):
        raise ComprobanteCompraError("Se alcanzó el límite diario de lecturas con IA. Probá mañana o cargalo a mano.", 429)
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise ComprobanteCompraError("La lectura con IA no está configurada (falta GEMINI_API_KEY).", 503)
    return _call_gemini_ocr(api_key, mime, contenido, PROMPT_FACTURA)


_facturas_ctr = None
# Inyectable en tests: (mime, bytes) -> dict crudo
ocr_factura: Callable[[str, bytes], dict] = _ocr_factura_default


def procesar_borrador(db: Session, borrador: BorradorComprobante,
                      contenido: Optional[bytes] = None, mime: Optional[str] = None) -> BorradorComprobante:
    """Lee el archivo con IA, normaliza y corre los controles. Nunca lanza:
    ante cualquier falla el borrador queda en estado `error` con el motivo."""
    try:
        if contenido is None:
            if not borrador.archivo:
                raise ComprobanteCompraError("El borrador no tiene archivo.")
            mime, contenido = leer_archivo(borrador.archivo)
        mime = mime or borrador.archivo_mime or "application/pdf"
        crudo = ocr_factura(mime, contenido)
        datos = normalizar_datos(crudo)
        borrador.datos = datos
        borrador.alertas = alertas_completas(db, borrador.organizacion_id, datos)
        borrador.error = None
        borrador.estado = "listo"
    except ComprobanteCompraError as ex:
        borrador.estado = "error"
        borrador.error = str(ex)
    except Exception as ex:   # JSON inválido, Gemini caído, archivo ilegible…
        logger.warning("Lectura de comprobante %s falló: %s", borrador.id, ex)
        borrador.estado = "error"
        borrador.error = "No se pudo leer el comprobante. Podés reintentar o completarlo a mano."
    db.commit()
    return borrador


# ── Buzón de mail ─────────────────────────────────────────────────

_RE_DIRECCION = re.compile(r"facturas-([a-z0-9]{12,32})@([a-z0-9.\-]+)", re.IGNORECASE)


def direccion_buzon(token: str, dominio: str) -> str:
    return f"facturas-{token}@{dominio}"


def generar_token() -> str:
    # 16 caracteres [a-z0-9] → difícil de adivinar, legible en un mail.
    alfabeto = "abcdefghijkmnpqrstuvwxyz23456789"
    return "".join(secrets.choice(alfabeto) for _ in range(16))


def activar_buzon(db: Session, org_id: int, regenerar: bool = False) -> BuzonComprobantes:
    buzon = db.query(BuzonComprobantes).filter(BuzonComprobantes.organizacion_id == org_id).first()
    if buzon and not regenerar:
        buzon.activo = True
    elif buzon:
        buzon.token = generar_token()
        buzon.activo = True
    else:
        buzon = BuzonComprobantes(organizacion_id=org_id, token=generar_token(), activo=True)
        db.add(buzon)
    db.commit()
    db.refresh(buzon)
    return buzon


def buscar_org_por_destinatarios(db: Session, destinatarios: list[str], dominio: str) -> Optional[int]:
    """Busca el token `facturas-<token>@<dominio>` en los destinatarios del mail."""
    dominio = (dominio or "").lower()
    for d in destinatarios:
        for token, dom in _RE_DIRECCION.findall(str(d) or ""):
            if dominio and dom.lower() != dominio:
                continue
            buzon = db.query(BuzonComprobantes).filter(
                BuzonComprobantes.token == token.lower(),
                BuzonComprobantes.activo == True,  # noqa: E712
            ).first()
            if buzon:
                return buzon.organizacion_id
    return None


def verificar_firma_svix(secret: str, headers: dict, body: bytes,
                         tolerancia_seg: int = 300, ahora: Optional[float] = None) -> bool:
    """Verifica la firma de un webhook de Resend (formato Svix).

    firma = base64(HMAC-SHA256(secret, f"{svix-id}.{svix-timestamp}.{body}")),
    con el secret en base64 después del prefijo `whsec_`. El header
    `svix-signature` trae una o más firmas `v1,<firma>` separadas por espacio.
    """
    if not secret:
        return False
    msg_id = headers.get("svix-id")
    ts = headers.get("svix-timestamp")
    firmas = headers.get("svix-signature")
    if not (msg_id and ts and firmas):
        return False
    try:
        ts_int = int(ts)
    except ValueError:
        return False
    ahora = time.time() if ahora is None else ahora
    if abs(ahora - ts_int) > tolerancia_seg:
        return False
    try:
        clave = base64.b64decode(secret.split("_", 1)[1] if secret.startswith("whsec_") else secret)
    except Exception:
        return False
    firmado = f"{msg_id}.{ts}.".encode() + body
    esperado = base64.b64encode(hmac.new(clave, firmado, hashlib.sha256).digest()).decode()
    for parte in firmas.split():
        version, _, firma = parte.partition(",")
        if version == "v1" and hmac.compare_digest(firma, esperado):
            return True
    return False


def adjuntos_utiles(adjuntos: list[dict]) -> list[dict]:
    """Filtra los adjuntos que pueden ser comprobantes: PDF/foto, no logos inline de firmas."""
    out = []
    for a in adjuntos or []:
        if not isinstance(a, dict):
            continue
        mime = mime_normalizado(a.get("content_type"), a.get("filename"))
        if not mime:
            continue
        if mime.startswith("image/") and (a.get("content_disposition") == "inline" or a.get("content_id")):
            continue   # logo o firma embebida en el cuerpo del mail
        out.append({**a, "mime": mime})
    return out


def descargar_adjunto_resend(api_key: str, email_id: str, adjunto_id: str) -> bytes:
    """Busca la URL temporal del adjunto en la API de Resend y lo descarga."""
    import requests
    resp = requests.get(
        f"https://api.resend.com/emails/receiving/{email_id}/attachments",
        headers={"Authorization": f"Bearer {api_key}"}, params={"limit": 100}, timeout=30,
    )
    resp.raise_for_status()
    for a in resp.json().get("data", []):
        if a.get("id") == adjunto_id:
            if a.get("size") and int(a["size"]) > MAX_ARCHIVO_BYTES:
                raise ComprobanteCompraError("El adjunto supera los 5 MB.")
            archivo = requests.get(a["download_url"], timeout=60)
            archivo.raise_for_status()
            if len(archivo.content) > MAX_ARCHIVO_BYTES:
                raise ComprobanteCompraError("El adjunto supera los 5 MB.")
            return archivo.content
    raise ComprobanteCompraError("Resend no devolvió el adjunto.")


# ── Confirmación ──────────────────────────────────────────────────

def periodo_de(fecha_iso: str) -> str:
    return fecha_iso[:7]


def confirmar_borrador(
    db: Session,
    borrador: BorradorComprobante,
    datos_editados: Optional[dict],
    usuario_id: int,
    periodo: Optional[str] = None,
    registrar_pago: bool = False,
    fecha_pago: Optional[date] = None,
) -> dict:
    """Crea el ComprobanteIva (y el Egreso si se pidió). Devuelve un resumen."""
    if borrador.estado == "confirmado":
        raise ComprobanteCompraError("Este comprobante ya fue confirmado.", 409)
    if borrador.estado in ("descartado", "sin_adjunto", "procesando"):
        raise ComprobanteCompraError("Este borrador no se puede confirmar.", 409)

    datos = normalizar_datos(datos_editados if datos_editados is not None else (borrador.datos or {}))
    obligatorios = ("tipo_codigo", "punto_venta", "numero", "fecha", "cuit_emisor", "total")
    faltan = [c for c in obligatorios if not datos.get(c)]
    if faltan:
        raise ComprobanteCompraError("Faltan datos para confirmar: " + ", ".join(faltan), 422)
    if len(datos["cuit_emisor"]) != 11:
        raise ComprobanteCompraError("El CUIT del proveedor debe tener 11 dígitos.", 422)
    if periodo is not None and not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", periodo):
        raise ComprobanteCompraError("El período debe tener formato AAAA-MM.", 422)

    t = totales(datos)
    tipo = datos["tipo_codigo"]
    comp = ComprobanteIva(
        organizacion_id=borrador.organizacion_id,
        direccion="recibido",
        periodo=periodo or periodo_de(datos["fecha"]),
        fecha=date.fromisoformat(datos["fecha"]),
        tipo_codigo=tipo,
        tipo_desc=f"{tipo} - {TIPOS_COMPROBANTE.get(tipo, 'Comprobante')}",
        punto_venta=datos["punto_venta"],
        numero=datos["numero"],
        cuit_contraparte=datos["cuit_emisor"],
        denominacion=datos.get("razon_social"),
        neto_gravado_total=t["neto_gravado"],
        total_iva=t["iva"],
        imp_total=t["total"],
        detalle_alicuotas={k: {"neto": float(Decimal(v["neto"])), "iva": float(Decimal(v["iva"]))}
                           for k, v in datos["alicuotas"].items()} or None,
        archivo_origen=f"Comprobantes por revisar #{borrador.id}"[:255],
    )
    db.add(comp)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise ComprobanteCompraError("Este comprobante ya está cargado en IVA.", 409)

    borrador.datos = datos
    borrador.alertas = validar_datos(datos)
    borrador.comprobante_iva_id = comp.id
    borrador.estado = "confirmado"
    borrador.confirmado_por = usuario_id
    borrador.confirmado_at = datetime.utcnow()
    db.commit()

    resultado = {"comprobante_iva_id": comp.id, "periodo": comp.periodo,
                 "egreso_id": None, "contabilidad_ok": None}

    if registrar_pago:
        if es_nota_credito(tipo):
            return resultado    # una nota de crédito no se paga
        egreso = Egreso(
            organizacion_id=borrador.organizacion_id,
            tipo="proveedor",
            forma_pago="banco",
            monto=t["total"],
            fecha=fecha_pago or hoy_art(),
            beneficiario=datos.get("razon_social"),
            concepto=f"{TIPOS_COMPROBANTE.get(tipo, 'Comprobante')} "
                     f"{datos['punto_venta']:05d}-{datos['numero']:08d}",
            referencia=f"CUIT {datos['cuit_emisor']}",
            foto_comprobante=borrador.archivo if (borrador.archivo_mime or "").startswith("image/") else None,
            notas=f"Cargado desde Comprobantes por revisar #{borrador.id}",
            usuario_id=usuario_id,
        )
        db.add(egreso)
        db.commit()
        db.refresh(egreso)
        borrador.egreso_id = egreso.id
        db.commit()
        resultado["egreso_id"] = egreso.id
        # Asiento automático, igual que POST /pagos (fault-tolerant).
        try:
            from app.services.motor_contable import registrar_egreso
            registrar_egreso(
                db=db, egreso_id=egreso.id, org_id=borrador.organizacion_id, usuario_id=usuario_id,
                tipo="proveedor", forma_pago="banco", monto=egreso.monto, fecha=egreso.fecha,
                beneficiario=egreso.beneficiario or "", concepto=egreso.concepto or "",
                cliente_id=None, cliente_nombre="",
            )
            resultado["contabilidad_ok"] = True
        except Exception as ex:
            logger.error("motor_contable egreso falló (egreso %s): %s", egreso.id, ex)
            resultado["contabilidad_ok"] = False
    return resultado
