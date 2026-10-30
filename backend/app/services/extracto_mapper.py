"""Lector de extractos bancarios en Excel/CSV de cualquier banco (con mapeo).

Antes el parser buscaba columnas por palabras clave y, si no encontraba nada,
asumía en silencio las posiciones fijas de Banco Macro: un archivo de otro banco
se leía mal sin avisar. Este módulo hace la lectura en tres capas, igual que las
planillas de clientes (`planilla_mapper`) y los moldes de PDF:

1. **Plantilla guardada** de la organización: si el renglón de encabezado del
   archivo (normalizado) + el banco detectado coinciden con uno que la persona ya
   confirmó, se aplica ese mapeo tal cual.
2. **Detección automática**: encabezado por palabras clave (`excel_parser.
   rol_por_encabezado`), validado con el contenido de las filas siguientes.
3. **Sugerencia por contenido** cuando no hay encabezado reconocible: se propone
   un mapeo, pero NUNCA se importa sin que la persona lo confirme.

Sobre lo leído se controla el saldo fila por fila (`extracto_pdf.saldos.
validar_saldos`, la misma regla que el PDF) detectando solo si el archivo va del
más viejo al más nuevo o al revés.

Puro: no toca la base. Montos en `Decimal` punta a punta.

Mapeo (lo que devuelve la detección y lo que manda el frontend al confirmar):

    {
      "hoja": "Extracto conciliado",     # opcional (None = la que mejor se lee)
      "fila_encabezado": 2,              # 0 = primera fila; -1 = sin encabezado
      "columnas": {"fecha": 1, "titular": 3, "monto": 4, "saldo": 5, "orden": 0},
      "signo": "columna_unica",          # | "debito_credito" | "indicador"
      "formato_fecha": "auto",           # | "dmy" | "mdy" | "ymd"
      "decimal": "auto",                 # | "coma" | "punto"
    }

Índices de columna desde 0. Roles: ver `ROLES`.
"""

from __future__ import annotations

import csv
import hashlib
import io
import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Optional

import openpyxl

from app.services.banco_identificacion import banco_por_estructura, identificar_banco
from app.services.decimal_utils import parse_importe_ar
from app.services.excel_parser import (
    _convertir_xls_a_xlsx,
    _normalizar,
    detectar_banco_filas,
    detectar_delimitador,
    rol_por_encabezado,
)
from app.services.extracto_import import nombre_banco
from app.services.extracto_pdf.fechas import a_date, parsear_fecha
from app.services.extracto_pdf.saldos import validar_saldos

# ── Vocabulario ──────────────────────────────────────────────────────────────

ROLES = (
    "fecha", "titular", "monto", "debito", "credito", "indicador", "saldo",
    "orden", "cuit", "mes", "cliente_acreditado", "fecha_acred",
)
ROLES_IMPORTE = ("monto", "debito", "credito")
SIGNOS = ("columna_unica", "debito_credito", "indicador")
FORMATOS_FECHA = ("auto", "dmy", "mdy", "ymd")
ESTILOS_DECIMAL = ("auto", "coma", "punto")

# Nombres de `rol_por_encabezado` → nombres del mapeo.
_ROL_LEGACY = {
    "cliente_acred": "cliente_acreditado",
    "indicador_dc": "indicador",
}

MAX_COLUMNAS = 60
FILAS_GRILLA = 30           # filas que se muestran en la pantalla de mapeo
FILAS_BUSQUEDA = 30         # hasta qué fila se busca el encabezado
FILAS_MUESTRA = 20          # filas de datos para validar el contenido de cada columna
UMBRAL_CONTENIDO = 0.6      # % de celdas que tienen que "parecer" del tipo del rol
CONFIANZA_ALTA = 0.8
_INT32 = 2**31 - 1


class MapeoInvalido(ValueError):
    """El mapeo que mandó el frontend no se puede aplicar (mensaje para la persona)."""


@dataclass
class Hoja:
    nombre: str
    filas: list[list[Any]]
    # Propiedades del libro (título, asunto, descripción…): ahí a veces está el CBU.
    metadatos: list[str] = field(default_factory=list)


# ── Lectura del archivo a una grilla ─────────────────────────────────────────

def _recortar(fila) -> list:
    fila = list(fila)[:MAX_COLUMNAS]
    while fila and (fila[-1] is None or (isinstance(fila[-1], str) and not fila[-1].strip())):
        fila.pop()
    return fila


def _recortar_filas(filas: list[list]) -> list[list]:
    filas = [_recortar(f) for f in filas]
    while filas and not filas[-1]:
        filas.pop()
    return filas


def _decodificar(raw: bytes) -> str:
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def leer_texto_delimitado(contenido: str) -> list[list]:
    """CSV / TSV / TXT con `;`, `,`, tabulador o `|`. Las celdas quedan como texto
    (los importes y fechas se interpretan después, según el mapeo)."""
    delim = detectar_delimitador(contenido)
    filas = []
    for row in csv.reader(io.StringIO(contenido), delimiter=delim):
        filas.append([(c.strip() or None) for c in row])
    return _recortar_filas(filas)


def leer_hojas(filepath: str) -> list[Hoja]:
    """Lee todas las hojas del archivo como listas de valores.

    `.xlsx` con `data_only=True`: las celdas con fórmula (p. ej. una columna Orden
    `=A5+1`) traen el último valor calculado que guardó Excel."""
    ext = os.path.splitext(filepath)[1].lower()
    if ext in (".csv", ".tsv", ".txt"):
        with open(filepath, "rb") as f:
            return [Hoja(nombre="Hoja 1", filas=leer_texto_delimitado(_decodificar(f.read())))]
    ruta, limpiar = (filepath, False)
    if ext == ".xls":
        ruta, limpiar = _convertir_xls_a_xlsx(filepath), True
    try:
        wb = openpyxl.load_workbook(ruta, data_only=True)
        try:
            meta = _metadatos_libro(wb)
            hojas = []
            for ws in wb.worksheets:
                filas = [list(r) for r in ws.iter_rows(values_only=True)]
                hojas.append(Hoja(nombre=ws.title, filas=_recortar_filas(filas), metadatos=meta))
            return hojas
        finally:
            wb.close()
    finally:
        if limpiar and os.path.exists(ruta):
            os.remove(ruta)


def _metadatos_libro(wb) -> list[str]:
    props = getattr(wb, "properties", None)
    if props is None:
        return []
    out = []
    for attr in ("title", "subject", "description", "keywords", "category"):
        v = getattr(props, attr, None)
        if isinstance(v, str) and v.strip():
            out.append(v.strip()[:500])
    return out


# ── Interpretación de celdas ─────────────────────────────────────────────────

_EPOCA_EXCEL = date(1899, 12, 30)
_RE_HORA = re.compile(r"[ T]+\d{1,2}:\d{2}.*$")
_RE_YMD = re.compile(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$")
_RE_DMY = re.compile(r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4}|\d{2})$")
_RE_COMPACTA = re.compile(r"^(\d{4})(\d{2})(\d{2})$")
_RE_SERIAL = re.compile(r"^\d{5}(?:[.,]\d+)?$")


def _serial_a_fecha(n: float) -> Optional[date]:
    # 20000 ≈ 1954, 80000 ≈ 2119: fuera de eso no es una fecha de extracto.
    if 20000 <= n <= 80000:
        return _EPOCA_EXCEL + timedelta(days=int(n))
    return None


def _fecha_segura(y: int, m: int, d: int) -> Optional[date]:
    if y < 100:
        y += 2000 if y < 70 else 1900
    if not 1990 <= y <= 2100:
        return None
    try:
        return date(y, m, d)
    except ValueError:
        return None


def parse_fecha(v, formato: str = "auto") -> Optional[date]:
    """Fecha de una celda de extracto. Acepta date/datetime, número de serie de
    Excel, `dd/mm/aaaa`, `d/m/aaaa`, `dd/mm/aa`, `dd-mm-aaaa`, `dd.mm.aaaa`,
    `aaaa-mm-dd`, `aaaammdd`, `19-may-26`, `19 may 2026` (con o sin hora).
    `formato="mdy"` lee `05/19/2026` como mes/día (archivos en formato EE.UU.)."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, (int, float, Decimal)):
        return _serial_a_fecha(float(v))
    s = _RE_HORA.sub("", str(v).strip())
    if not s:
        return None
    if _RE_SERIAL.match(s):
        return _serial_a_fecha(float(s.replace(",", ".")))
    m = _RE_YMD.match(s)
    if m:
        return _fecha_segura(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = _RE_DMY.match(s)
    if m:
        a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if formato == "mdy":
            a, b = b, a
        return _fecha_segura(y, b, a)
    m = _RE_COMPACTA.match(s)
    if m:
        return _fecha_segura(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    # Con nombre de mes ("19-may-26", "19 may 2026"): mismo lector que el PDF.
    return a_date(parsear_fecha(s))


def detectar_formato_fecha(valores) -> str:
    """"dmy" salvo que algún valor `a/b/aaaa` tenga b > 12 (solo posible en mes/día)."""
    dmy = mdy = 0
    for v in valores:
        if not isinstance(v, str):
            continue
        m = _RE_DMY.match(_RE_HORA.sub("", v.strip()))
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            dmy += a > 12
            mdy += b > 12
    return "mdy" if mdy > dmy else "dmy"


def parse_importe(v, decimal: str = "auto") -> Optional[Decimal]:
    """Importe de una celda a `Decimal` (0,01). Acepta `1.234,56`, `-1.234,56`,
    `1.234,56-`, `(1.234,56)`, `$ 1.234,56`, `1,234.56` y números de Excel.
    Con `decimal="coma"`/`"punto"` se fuerza el separador decimal de la columna."""
    if isinstance(v, str) and decimal in ("coma", "punto"):
        s = v.strip()
        if decimal == "coma":
            s = s.replace(".", "")
        else:
            s = s.replace(",", "")
            if s.count(".") == 1:
                s = s.replace(".", ",")
        return parse_importe_ar(s)
    if isinstance(v, (date, datetime)):
        return None
    return parse_importe_ar(v)


def detectar_decimal(valores) -> str:
    """Separador decimal de una columna de texto: el de la derecha cuando aparecen
    los dos (`1.234,56` → coma; `1,234.56` → punto). "auto" si no hay pistas."""
    coma = punto = 0
    for v in valores:
        if not isinstance(v, str):
            continue
        s = v.strip()
        if "," in s and "." in s:
            if s.rfind(",") > s.rfind("."):
                coma += 1
            else:
                punto += 1
        elif re.search(r",\d{1,2}\s*-?\)?$", s):
            coma += 1
    if coma > punto:
        return "coma"
    if punto > coma:
        return "punto"
    return "auto"


def _texto(v) -> str:
    if v is None:
        return ""
    if isinstance(v, datetime):
        if v.hour or v.minute:
            return v.strftime("%d/%m/%Y %H:%M")
        return v.strftime("%d/%m/%Y")
    if isinstance(v, date):
        return v.strftime("%d/%m/%Y")
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def _celda(fila: list, idx: Optional[int]):
    if idx is None or idx < 0 or idx >= len(fila):
        return None
    return fila[idx]


def _vacia(v) -> bool:
    return v is None or (isinstance(v, str) and not v.strip())


def _es_dato(v) -> bool:
    """Número o fecha: lo que tiene una fila de movimientos y no un encabezado."""
    if isinstance(v, (int, float, Decimal, date, datetime)) and not isinstance(v, bool):
        return True
    return isinstance(v, str) and parse_fecha(v) is not None


# ── Filas de total / saldo (no son movimientos) ──────────────────────────────

_RE_RESUMEN = re.compile(
    r"^(total(es)?|sub ?total|suma|transporte|saldo (anterior|inicial|final|al|actual|"
    r"de cierre|del periodo|a la fecha))\b"
)
_INICIAL = ("saldo anterior", "saldo inicial")
_FINAL = ("saldo final", "saldo al", "saldo actual", "saldo de cierre", "saldo a la fecha")


def _es_fila_resumen(fila: list) -> bool:
    """Fila de total/saldo SIN fecha (una empresa "TOTAL ENERGIES" con fecha es un
    movimiento). Para elegir filas de muestra; al leer se usa `aplicar_mapeo`."""
    return bool(_clave_resumen(fila)) and not any(
        isinstance(v, (date, datetime)) or (isinstance(v, str) and parse_fecha(v) is not None)
        for v in fila
    )


def _clave_resumen(fila: list) -> Optional[str]:
    for v in fila:
        if isinstance(v, str):
            t = _normalizar(v.strip().lower())
            if _RE_RESUMEN.match(t):
                return t
    return None


# ── Firma del encabezado (clave de la plantilla) ─────────────────────────────

def _normalizar_encabezado(v) -> str:
    t = _normalizar(str(v).strip().lower())
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", t)).strip()


def firma_encabezado(fila: list, banco_clave: Optional[str]) -> Optional[str]:
    """Huella del renglón de encabezado + banco. None si el renglón no parece un
    encabezado (menos de 2 textos o alguna celda con números/fechas)."""
    textos = []
    for v in fila:
        if _vacia(v):
            textos.append("")
            continue
        if not isinstance(v, str) or _es_dato(v):
            return None
        textos.append(_normalizar_encabezado(v))
    if sum(1 for t in textos if t) < 2:
        return None
    while textos and not textos[-1]:
        textos.pop()
    raw = f"v1|{banco_clave or 'generico'}|{'|'.join(textos)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ── Mapeo: normalización y validación ────────────────────────────────────────

def inferir_signo(columnas: dict) -> str:
    if "monto" in columnas and "indicador" in columnas:
        return "indicador"
    if "debito" in columnas or "credito" in columnas:
        if "monto" not in columnas or ("debito" in columnas and "credito" in columnas):
            return "debito_credito"
    return "columna_unica"


def normalizar_mapeo(mapeo: dict) -> dict:
    """Valida y completa un mapeo. Lanza `MapeoInvalido` con un mensaje claro."""
    if not isinstance(mapeo, dict):
        raise MapeoInvalido("El mapeo de columnas no tiene el formato esperado.")
    cols_in = mapeo.get("columnas") or {}
    if not isinstance(cols_in, dict):
        raise MapeoInvalido("El mapeo de columnas no tiene el formato esperado.")
    columnas: dict[str, int] = {}
    for rol, idx in cols_in.items():
        if idx is None:
            continue
        if rol not in ROLES:
            raise MapeoInvalido(f"Columna con un uso desconocido: {rol}.")
        try:
            idx = int(idx)
        except (TypeError, ValueError):
            raise MapeoInvalido("Hay una columna mal indicada en el mapeo.")
        if not 0 <= idx < MAX_COLUMNAS:
            raise MapeoInvalido("Hay una columna fuera de la planilla en el mapeo.")
        columnas[rol] = idx
    signo = mapeo.get("signo") or inferir_signo(columnas)
    if signo not in SIGNOS:
        raise MapeoInvalido("No se entiende cómo vienen los débitos y créditos.")
    if signo == "columna_unica" and "monto" not in columnas:
        raise MapeoInvalido("Falta indicar la columna del importe.")
    if signo == "debito_credito" and not ("debito" in columnas or "credito" in columnas):
        raise MapeoInvalido("Falta indicar las columnas de débitos y créditos.")
    if signo == "indicador" and not ("monto" in columnas and "indicador" in columnas):
        raise MapeoInvalido("Falta indicar la columna del importe y la que dice si es débito o crédito.")
    try:
        fila = int(mapeo.get("fila_encabezado", 0))
    except (TypeError, ValueError):
        raise MapeoInvalido("La fila de encabezado no es válida.")
    if fila < -1:
        raise MapeoInvalido("La fila de encabezado no es válida.")
    formato = mapeo.get("formato_fecha") or "auto"
    decimal = mapeo.get("decimal") or "auto"
    if formato not in FORMATOS_FECHA:
        raise MapeoInvalido("Formato de fecha desconocido.")
    if decimal not in ESTILOS_DECIMAL:
        raise MapeoInvalido("Separador decimal desconocido.")
    hoja = mapeo.get("hoja")
    return {
        "hoja": str(hoja) if hoja else None,
        "fila_encabezado": fila,
        "columnas": columnas,
        "signo": signo,
        "formato_fecha": formato,
        "decimal": decimal,
    }


# ── Aplicar un mapeo ─────────────────────────────────────────────────────────

def _orden_int(v) -> Optional[int]:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float, Decimal)):
        n = float(v)
        if n.is_integer() and abs(n) <= _INT32:
            return int(n)
        return None
    if isinstance(v, str) and v.strip().isdigit() and int(v.strip()) <= _INT32:
        return int(v.strip())
    return None


def _mes(v, f: Optional[date]) -> Optional[str]:
    if v is not None and str(v).strip():
        try:
            n = int(float(str(v).strip()))
            if 1 <= n <= 12:
                return str(n)
        except ValueError:
            pass
    return str(f.month) if f else None


def _signo_indicador(v) -> int:
    t = _normalizar(str(v or "").strip().lower())
    if not t:
        return 0
    if t.startswith(("deb", "db", "dr", "egr", "-")) or t in ("d", "debe"):
        return -1
    if t.startswith(("cred", "cr", "ing", "+")) or t in ("c", "haber", "h"):
        return 1
    return 0


def _importe_fila(fila, cols, signo, dec) -> Optional[Decimal]:
    if signo == "debito_credito":
        cr = parse_importe(_celda(fila, cols.get("credito")), dec.get("credito", "auto"))
        db = parse_importe(_celda(fila, cols.get("debito")), dec.get("debito", "auto"))
        if cr is None and db is None:
            return None
        return abs(cr or Decimal("0")) - abs(db or Decimal("0"))
    monto = parse_importe(_celda(fila, cols.get("monto")), dec.get("monto", "auto"))
    if monto is None:
        return None
    if signo == "indicador":
        s = _signo_indicador(_celda(fila, cols.get("indicador")))
        if s:
            return abs(monto) * s
    return monto


def _decimales_por_columna(datos: list[list], cols: dict, decimal: str) -> dict:
    if decimal != "auto":
        return {rol: decimal for rol in ("monto", "debito", "credito", "saldo")}
    return {
        rol: detectar_decimal(_celda(f, cols[rol]) for f in datos[:200])
        for rol in ("monto", "debito", "credito", "saldo") if rol in cols
    }


def aplicar_mapeo(filas: list[list], mapeo: dict) -> dict:
    """Lee los movimientos con un mapeo ya normalizado.

    Salteadas: filas vacías, de total/saldo (sin fecha o sin importe) y filas sin
    importe o sin fecha legible (cuentan en `filas_descartadas`). Una fila de
    "Saldo anterior"/"Saldo final" aporta el saldo de apertura/cierre."""
    cols = mapeo["columnas"]
    signo = mapeo["signo"]
    inicio = mapeo["fila_encabezado"] + 1
    datos = filas[inicio:]
    formato = mapeo["formato_fecha"]
    if formato == "auto" and "fecha" in cols:
        formato = detectar_formato_fecha(_celda(f, cols["fecha"]) for f in datos[:200])
    dec = _decimales_por_columna(datos, cols, mapeo["decimal"])

    movimientos: list[dict] = []
    descartadas = resumen = sin_fecha = 0
    saldo_inicial = saldo_final = None
    for off, fila in enumerate(datos):
        if not fila or all(_vacia(v) for v in fila):
            continue
        n_fila = inicio + off + 1          # número de fila como lo ve la persona en Excel
        fecha = parse_fecha(_celda(fila, cols.get("fecha")), formato) if "fecha" in cols else None
        monto = _importe_fila(fila, cols, signo, dec)
        clave = _clave_resumen(fila)
        if clave and (monto is None or ("fecha" in cols and fecha is None)):
            resumen += 1
            valor = parse_importe(_celda(fila, cols.get("saldo")), dec.get("saldo", "auto"))
            if valor is None:
                valor = monto
            if valor is not None:
                if clave.startswith(_INICIAL) and saldo_inicial is None:
                    saldo_inicial = valor
                elif clave.startswith(_FINAL):
                    saldo_final = valor
            continue
        if monto is None or monto == 0:
            descartadas += 1
            continue
        if "fecha" in cols and fecha is None:
            descartadas += 1
            sin_fecha += 1
            continue
        titular = _texto(_celda(fila, cols.get("titular"))) if "titular" in cols else ""
        cuit = re.sub(r"\D", "", _texto(_celda(fila, cols.get("cuit")))) if "cuit" in cols else ""
        if cuit and cuit not in re.sub(r"\D", "", titular):
            # El motor de conciliación busca el CUIT dentro del texto del titular.
            titular = f"{titular} {cuit}".strip()
        cliente = _texto(_celda(fila, cols.get("cliente_acreditado"))) if "cliente_acreditado" in cols else ""
        movimientos.append({
            "fila": n_fila,
            "orden": _orden_int(_celda(fila, cols.get("orden"))),
            "fecha": fecha,
            "mes": _mes(_celda(fila, cols.get("mes")), fecha),
            "titular": titular or None,
            "monto": monto,
            "saldo": parse_importe(_celda(fila, cols.get("saldo")), dec.get("saldo", "auto")) if "saldo" in cols else None,
            "cliente_acreditado": cliente or None,
            "fecha_acred": parse_fecha(_celda(fila, cols.get("fecha_acred")), formato) if "fecha_acred" in cols else None,
        })
    return {
        "movimientos": movimientos,
        "filas_descartadas": descartadas,
        "filas_sin_fecha": sin_fecha,
        "filas_resumen": resumen,
        "saldo_inicial": saldo_inicial,
        "saldo_final": saldo_final,
        "formato_fecha": formato,
    }


# ── Control de saldos ────────────────────────────────────────────────────────

def _orden_por_fechas(movs: list[dict]) -> Optional[str]:
    fechas = [m["fecha"] for m in movs if m.get("fecha")]
    sube = sum(1 for a, b in zip(fechas, fechas[1:]) if b > a)
    baja = sum(1 for a, b in zip(fechas, fechas[1:]) if b < a)
    if sube != baja:
        return "asc" if sube > baja else "desc"
    ordenes = [m["orden"] for m in movs if m.get("orden") is not None]
    sube = sum(1 for a, b in zip(ordenes, ordenes[1:]) if b > a)
    baja = sum(1 for a, b in zip(ordenes, ordenes[1:]) if b < a)
    if sube != baja:
        return "asc" if sube > baja else "desc"
    return None


def _str(v) -> Optional[str]:
    return None if v is None else str(v)


def controlar_saldos(movs: list[dict], saldo_inicial=None, saldo_final=None) -> dict:
    """¿Cuadran los saldos? Detecta solo el sentido del archivo (más viejo
    primero o más nuevo primero) probando los dos y quedándose con el que corta
    menos veces el saldo corrido; si empatan, por las fechas.

    `orden_detectado` es False cuando no hubo con qué decidir (sin saldo y con
    todas las fechas y órdenes iguales): ahí "asc" es solo un valor por defecto y
    los movimientos no se reordenan."""
    por_fechas = _orden_por_fechas(movs)
    if not movs or not any(m.get("saldo") is not None for m in movs):
        return {
            "tiene_saldo": False, "cuadra": None, "orden": por_fechas or "asc",
            "orden_detectado": por_fechas is not None,
            "mensaje": "El archivo no trae columna de saldo: no se puede controlar que cierre.",
        }
    asc = validar_saldos(movs, orden="asc", saldo_inicial=saldo_inicial, saldo_final=saldo_final)
    desc = validar_saldos(movs, orden="desc", saldo_inicial=saldo_inicial, saldo_final=saldo_final)
    clave_a = (len(asc["filas_con_salto"]), not asc["cierra"])
    clave_d = (len(desc["filas_con_salto"]), not desc["cierra"])
    if clave_a != clave_d:
        por_saldo = "asc" if clave_a < clave_d else "desc"
        # Si el saldo tampoco encadena en el sentido "mejor" y las fechas dicen
        # otra cosa, mandan las fechas (un archivo con huecos engaña al saldo).
        if por_fechas and por_fechas != por_saldo and min(clave_a, clave_d)[0] > 0:
            orden = por_fechas
        else:
            orden = por_saldo
        detectado = True
    else:
        orden = por_fechas or "asc"
        detectado = por_fechas is not None
    r = asc if orden == "asc" else desc
    saltos = r["filas_con_salto"]
    # La primera fila que corta el saldo en orden cronológico: es la del error (la
    # que sigue también "salta" porque arranca de un saldo equivocado).
    primera = None
    if saltos:
        primera = movs[saltos[0] if orden == "asc" else saltos[-1]]["fila"]
    if r["cierra"]:
        mensaje = "Los saldos cuadran."
    elif primera is not None:
        mensaje = f"No cuadra en la fila {primera}: el saldo no sigue al de la fila anterior."
    else:
        mensaje = "No cuadra: el saldo final no coincide con el inicial más los movimientos."
    return {
        "tiene_saldo": True,
        "cuadra": bool(r["cierra"]),
        "orden": orden,
        "orden_detectado": detectado,
        "saldo_inicial": _str(r["saldo_inicial"]),
        "saldo_final": _str(r["saldo_final"]),
        "saldo_final_calculado": _str(r["saldo_final_calculado"]),
        "diferencia": _str(r["diferencia"]),
        "total_creditos": _str(r["total_creditos"]),
        "total_debitos": _str(r["total_debitos"]),
        "filas_con_error": len(saltos),
        "primera_fila_con_error": primera,
        "mensaje": mensaje,
    }


# ── Detección automática ─────────────────────────────────────────────────────

def _roles_por_palabras(fila: list) -> dict:
    roles: dict[str, int] = {}
    for c, v in enumerate(fila):
        if not isinstance(v, str):
            continue
        rol = rol_por_encabezado(v)
        if rol:
            roles.setdefault(_ROL_LEGACY.get(rol, rol), c)
    return roles


def _parece_encabezado(fila: list) -> bool:
    """Otra fila de títulos (≥2 palabras clave y ningún número/fecha)."""
    if any(_es_dato(v) for v in fila if not _vacia(v)):
        return False
    return len(_roles_por_palabras(fila)) >= 2


def _muestra(filas: list[list], desde: int) -> list[list]:
    out = []
    for fila in filas[desde:]:
        if not fila or all(_vacia(v) for v in fila):
            continue
        if _parece_encabezado(fila):
            break
        if _es_fila_resumen(fila):
            continue
        out.append(fila)
        if len(out) >= FILAS_MUESTRA:
            break
    return out


def _proporcion(valores: list, ok) -> tuple[float, int]:
    llenos = [v for v in valores if not _vacia(v)]
    if not llenos:
        return 0.0, 0
    return sum(1 for v in llenos if ok(v)) / len(llenos), len(llenos)


def _validar_roles(muestra: list[list], roles: dict) -> dict:
    """Se queda con los roles cuyo contenido acompaña al encabezado."""
    validos = {}
    for rol, c in roles.items():
        vals = [_celda(f, c) for f in muestra]
        if rol in ("monto", "debito", "credito", "saldo"):
            prop, n = _proporcion(vals, lambda v: parse_importe(v) is not None)
            # Débito o crédito pueden venir vacías en toda la muestra (cada fila llena una).
            if n == 0 and rol in ("debito", "credito"):
                validos[rol] = c
            elif n and prop >= UMBRAL_CONTENIDO:
                validos[rol] = c
        elif rol in ("fecha", "fecha_acred"):
            fmt = detectar_formato_fecha(vals)
            prop, n = _proporcion(vals, lambda v: parse_fecha(v, fmt) is not None)
            if (n and prop >= UMBRAL_CONTENIDO) or (n == 0 and rol == "fecha_acred"):
                validos[rol] = c
        else:
            validos[rol] = c
    tiene_importe = any(
        any(parse_importe(_celda(f, validos[r])) is not None for f in muestra)
        for r in ROLES_IMPORTE if r in validos
    )
    return validos if tiene_importe else {}


def detectar_por_encabezado(filas: list[list]) -> Optional[dict]:
    """Primer renglón con palabras clave de importe cuyo contenido lo confirma."""
    for r in range(min(FILAS_BUSQUEDA, len(filas))):
        roles = _roles_por_palabras(filas[r])
        if not (set(ROLES_IMPORTE) & roles.keys()):
            continue
        if any(_es_dato(v) for v in filas[r] if not _vacia(v)):
            continue
        muestra = _muestra(filas, r + 1)
        validos = _validar_roles(muestra, roles)
        if not validos:
            continue
        return {
            "fila_encabezado": r,
            "columnas": validos,
            "descartados": sorted(set(roles) - set(validos)),
        }
    return None


def sugerir_por_contenido(filas: list[list]) -> Optional[dict]:
    """Sin encabezado reconocible: propone fecha / importe / saldo / detalle según
    lo que hay en las celdas. Es SOLO una sugerencia para la pantalla de mapeo."""
    inicio = None
    for r in range(min(40, len(filas))):
        fila = filas[r]
        tiene_fecha = any(parse_fecha(v) is not None for v in fila
                          if isinstance(v, (str, date, datetime)))
        tiene_importe = any(
            parse_importe(v) is not None and parse_fecha(v) is None
            for v in fila if not _vacia(v)
        )
        if tiene_fecha and tiene_importe:
            inicio = r
            break
    if inicio is None:
        return None
    muestra = [f for f in filas[inicio:inicio + FILAS_MUESTRA] if f and not _es_fila_resumen(f)]
    if not muestra:
        return None
    ancho = max(len(f) for f in muestra)
    fecha_col = None
    numericas, textos = [], []
    for c in range(ancho):
        vals = [_celda(f, c) for f in muestra]
        p_fecha, n = _proporcion(vals, lambda v: parse_fecha(v) is not None and not isinstance(v, (int, float)))
        if n and p_fecha >= UMBRAL_CONTENIDO and fecha_col is None:
            fecha_col = c
            continue
        p_imp, n = _proporcion(vals, lambda v: parse_importe(v) is not None)
        if n and p_imp >= UMBRAL_CONTENIDO:
            numericas.append(c)
        elif n:
            largo = sum(len(_texto(v)) for v in vals) / max(1, n)
            textos.append((largo, c))
    if not numericas:
        return None
    columnas: dict[str, int] = {}
    if fecha_col is not None:
        columnas["fecha"] = fecha_col
    if textos:
        columnas["titular"] = max(textos)[1]
    # Si hay una columna de números enteros consecutivos al principio, es el orden.
    candidatas = list(numericas)
    for c in candidatas[:1]:
        ints = [_orden_int(_celda(f, c)) for f in muestra]
        if all(i is not None for i in ints) and all(abs(b - a) == 1 for a, b in zip(ints, ints[1:])):
            columnas["orden"] = c
            candidatas.remove(c)
    if not candidatas:
        return None
    mejor = None
    pruebas = []
    if len(candidatas) >= 2:
        for i, a in enumerate(candidatas):
            for b in candidatas[i + 1:]:
                pruebas.append({"monto": a, "saldo": b})
    if len(candidatas) >= 3:
        for i in range(len(candidatas) - 2):
            d, c_, s = candidatas[i:i + 3]
            pruebas.append({"debito": d, "credito": c_, "saldo": s})
    for cols in pruebas:
        prueba = normalizar_mapeo({"fila_encabezado": inicio - 1, "columnas": {**columnas, **cols}})
        leido = aplicar_mapeo(filas, prueba)
        if not leido["movimientos"]:
            continue
        cuadre = controlar_saldos(leido["movimientos"])
        puntaje = (bool(cuadre.get("cuadra")), -cuadre.get("filas_con_error", 0), len(leido["movimientos"]))
        if mejor is None or puntaje > mejor[0]:
            mejor = (puntaje, cols)
    if mejor is not None and mejor[0][0]:
        columnas.update(mejor[1])
    else:
        columnas["monto"] = candidatas[0]
    return {"fila_encabezado": inicio - 1, "columnas": columnas, "descartados": []}


# ── Análisis completo ────────────────────────────────────────────────────────

def _confianza(origen: str, mapeo: dict, leido: dict, cuadre: dict) -> float:
    if origen == "manual":
        return 1.0
    if origen == "plantilla":
        return 1.0 if cuadre.get("cuadra") is not False else 0.6
    if origen != "heuristica":
        return 0.3 if cuadre.get("cuadra") else 0.2
    cols = mapeo["columnas"]
    c = 0.6
    c += 0.15 if "fecha" in cols else 0.0
    c += 0.1 if "titular" in cols else 0.0
    if cuadre.get("cuadra") is True:
        c += 0.15
    elif cuadre.get("cuadra") is False:
        c -= 0.2
    else:
        c += 0.05
    total = len(leido["movimientos"]) + leido["filas_descartadas"]
    if total and leido["filas_descartadas"] / total > 0.2:
        c -= 0.15
    return round(max(0.0, min(1.0, c)), 2)


def _leer_hoja(hoja: Hoja, mapeo: dict) -> tuple[dict, dict]:
    leido = aplicar_mapeo(hoja.filas, mapeo)
    cuadre = controlar_saldos(leido["movimientos"], leido["saldo_inicial"], leido["saldo_final"])
    return leido, cuadre


def analizar_hojas(hojas: list[Hoja], *, plantillas: Optional[dict] = None,
                   mapeo: Optional[dict] = None, nombre_archivo: Optional[str] = None) -> dict:
    """Elige hoja + mapeo (manual → plantilla → detección → sugerencia), lee los
    movimientos y controla los saldos. `plantillas`: {firma: {"id", "mapeo",
    "banco_clave", "banco_confirmado"}}. `nombre_archivo`: el que subió la persona
    (para reconocer el banco por el CBU o el nombre escrito ahí)."""
    hojas = [h for h in hojas if h.filas]
    ctx = {"plantillas": plantillas or {}, "nombre_archivo": nombre_archivo}

    def _resultado(*args):
        return _armar_resultado(*args, ctx=ctx)

    if not hojas:
        return _resultado(None, None, "ninguno", None, None, None, None, None)

    if mapeo is not None:
        m = normalizar_mapeo(mapeo)
        hoja = next((h for h in hojas if h.nombre == m["hoja"]), None) or hojas[0]
        if m["fila_encabezado"] >= len(hoja.filas):
            raise MapeoInvalido("La fila de encabezado está más abajo que el final de la planilla.")
        m["hoja"] = hoja.nombre
        leido, cuadre = _leer_hoja(hoja, m)
        return _resultado(hoja, hojas, "manual", m, leido, cuadre, None, None)

    if plantillas:
        for hoja in hojas:
            banco = detectar_banco_filas(hoja.filas[:10])
            for r in range(min(FILAS_BUSQUEDA, len(hoja.filas))):
                f = firma_encabezado(hoja.filas[r], banco)
                if f and f in plantillas:
                    try:
                        m = normalizar_mapeo({**plantillas[f]["mapeo"], "fila_encabezado": r,
                                              "hoja": hoja.nombre})
                    except MapeoInvalido:
                        continue
                    leido, cuadre = _leer_hoja(hoja, m)
                    if leido["movimientos"]:
                        return _resultado(hoja, hojas, "plantilla", m, leido, cuadre,
                                          plantillas[f].get("id"), None)

    mejor = None
    for hoja in hojas:
        det = detectar_por_encabezado(hoja.filas)
        if not det:
            continue
        m = normalizar_mapeo({**det, "hoja": hoja.nombre})
        leido, cuadre = _leer_hoja(hoja, m)
        if mejor is None or len(leido["movimientos"]) > len(mejor[2]["movimientos"]):
            mejor = (hoja, m, leido, cuadre, det["descartados"])
    if mejor and mejor[2]["movimientos"]:
        hoja, m, leido, cuadre, descartados = mejor
        return _resultado(hoja, hojas, "heuristica", m, leido, cuadre, None, descartados)

    for hoja in hojas:
        sug = sugerir_por_contenido(hoja.filas)
        if not sug:
            continue
        m = normalizar_mapeo({**sug, "hoja": hoja.nombre})
        leido, cuadre = _leer_hoja(hoja, m)
        if leido["movimientos"]:
            return _resultado(hoja, hojas, "sugerencia", m, leido, cuadre, None, None)

    return _resultado(hojas[0], hojas, "ninguno", None, None, None, None, None)


def _zona_encabezado(filas: list[list], fila_enc: int) -> list[list]:
    """Filas de arriba de la tabla (membrete, datos de la cuenta): lo de antes del
    renglón de títulos o, sin títulos, lo de antes de la primera fila con números o
    fechas. Las descripciones de los movimientos NO entran (nombran otros bancos)."""
    if fila_enc > 0:
        return filas[:fila_enc]
    out = []
    for fila in filas[:10]:
        if any(_es_dato(v) for v in fila if not _vacia(v)):
            break
        out.append(fila)
    return out


def _deteccion_banco(hoja: Optional[Hoja], filas: list[list], mapeo: Optional[dict], encabezado: list,
                     movs: list[dict], firma: Optional[str], ctx: dict) -> dict:
    fila_enc = mapeo["fila_encabezado"] if mapeo else -1
    zona = _zona_encabezado(filas, fila_enc)
    textos = [str(v) for fila in zona for v in fila if isinstance(v, str) and v.strip()]
    # Nombre: el detector de siempre, pero solo sobre el membrete + títulos.
    por_nombre = detectar_banco_filas(zona + ([encabezado] if encabezado else [])) if (zona or encabezado) else None
    estructura = banco_por_estructura(
        encabezados=[v for v in encabezado if isinstance(v, str)],
        conceptos=[m.get("titular") or "" for m in movs[:200]],
        filas_cabecera=(zona + [encabezado])[-5:] if encabezado else None,
    )
    plantilla = (ctx.get("plantillas") or {}).get(firma) if firma else None
    return identificar_banco(
        textos_encabezado=textos,
        nombre_archivo=ctx.get("nombre_archivo"),
        metadatos=hoja.metadatos if hoja else [],
        por_nombre=por_nombre,
        por_estructura=estructura,
        aprendido=(plantilla or {}).get("banco_clave"),
        aprendido_confirmado=bool((plantilla or {}).get("banco_confirmado")),
    )


def _armar_resultado(hoja, hojas, origen, mapeo, leido, cuadre, plantilla_id, descartados, *, ctx) -> dict:
    filas = hoja.filas if hoja else []
    # Banco "de la firma": el detector por nombre de siempre. La huella de las
    # plantillas ya guardadas se calculó con él, así que no se cambia.
    banco_firma = detectar_banco_filas(filas[:10]) if filas else "generico"
    leido = leido or {"movimientos": [], "filas_descartadas": 0, "filas_sin_fecha": 0,
                      "filas_resumen": 0, "saldo_inicial": None, "saldo_final": None}
    cuadre = cuadre or {"tiene_saldo": False, "cuadra": None, "orden": "asc", "mensaje": ""}
    movs = leido["movimientos"]
    fila_enc = mapeo["fila_encabezado"] if mapeo else -1
    encabezado = filas[fila_enc] if mapeo and 0 <= fila_enc < len(filas) else []
    firma = firma_encabezado(encabezado, banco_firma) if encabezado else None
    confianza = _confianza(origen, mapeo, leido, cuadre) if mapeo else 0.0

    motivos: list[str] = []
    if origen == "ninguno":
        motivos.append("No reconocimos las columnas del archivo. Indicá cuál es cada una.")
    elif origen == "sugerencia":
        motivos.append("El archivo no tiene títulos de columnas que reconozcamos: revisá la propuesta.")
    if mapeo and not movs:
        motivos.append("Con estas columnas no se leyó ningún movimiento.")
    if cuadre.get("cuadra") is False:
        motivos.append(cuadre["mensaje"])
    if origen == "heuristica" and mapeo and "fecha" not in mapeo["columnas"]:
        motivos.append("No encontramos la columna de fecha.")
    if descartados:
        motivos.append("Algunas columnas con título conocido no tenían datos del tipo esperado: "
                       + ", ".join(descartados) + ".")
    if leido.get("filas_sin_fecha"):
        motivos.append(f"{leido['filas_sin_fecha']} fila(s) con importe se saltearon porque no tenían una fecha legible.")
    # Con un formato guardado de la org, que no cuadren los saldos NO frena la
    # importación (suele ser un archivo al que le faltan movimientos): se importa
    # y queda el aviso. Sin plantilla, un descuadre sí pide revisar las columnas.
    necesita = (
        origen in ("ninguno", "sugerencia")
        or not movs
        or (cuadre.get("cuadra") is False and origen != "plantilla")
        or (origen == "heuristica" and confianza < CONFIANZA_ALTA)
    )
    aviso_saldos = None
    if cuadre.get("cuadra") is False:
        desde = cuadre.get("primera_fila_con_error")
        aviso_saldos = (
            f"Los saldos no cuadran desde la fila {desde}: puede que falten movimientos en este archivo"
            if desde is not None else
            "Los saldos no cuadran: puede que falten movimientos en este archivo"
        )
    deteccion = _deteccion_banco(hoja, filas, mapeo, encabezado, movs, firma, ctx)
    banco_clave = deteccion["banco_clave"]
    return {
        "hoja": hoja.nombre if hoja else None,
        "hojas": [h.nombre for h in hojas] if hojas else [],
        "filas": filas,
        "banco_clave": banco_clave,
        "banco": nombre_banco(banco_clave),
        "banco_deteccion": deteccion,
        "origen": origen,
        "plantilla_id": plantilla_id,
        "mapeo": mapeo,
        "firma": firma,
        "encabezados": [_texto(v) for v in encabezado],
        "confianza": confianza,
        "movimientos": movs,
        "filas_descartadas": leido["filas_descartadas"],
        "filas_resumen": leido["filas_resumen"],
        "cuadre": cuadre,
        "necesita_mapeo": bool(necesita),
        "motivos": motivos,
        "aviso_saldos": aviso_saldos,
    }


def analizar_extracto(filepath: str, *, plantillas: Optional[dict] = None,
                      mapeo: Optional[dict] = None, nombre_archivo: Optional[str] = None) -> dict:
    """Lee el archivo y lo analiza (ver `analizar_hojas`)."""
    return analizar_hojas(leer_hojas(filepath), plantillas=plantillas, mapeo=mapeo,
                          nombre_archivo=nombre_archivo)


# ── Salida JSON para la pantalla de mapeo ────────────────────────────────────

def _mov_json(m: dict) -> dict:
    return {
        "fila": m["fila"],
        "fecha": m["fecha"].isoformat() if m.get("fecha") else None,
        "titular": m.get("titular"),
        "monto": str(m["monto"]),
        "saldo": _str(m.get("saldo")),
        "orden": m.get("orden"),
    }


def serializar_analisis(res: dict, *, muestra: int = 10) -> dict:
    """Respuesta de `POST /extractos/preview` (todo JSON: montos como texto)."""
    filas = res["filas"]
    fila_enc = res["mapeo"]["fila_encabezado"] if res["mapeo"] else -1
    desde = max(0, fila_enc - 2) if fila_enc > FILAS_GRILLA - 10 else 0
    grilla = filas[desde:desde + FILAS_GRILLA]
    ancho = max((len(f) for f in grilla), default=0)
    movs = res["movimientos"]
    return {
        "hoja": res["hoja"],
        "hojas": res["hojas"],
        "banco_clave": res["banco_clave"],
        "banco": res["banco"],
        "banco_deteccion": res["banco_deteccion"],
        "origen": res["origen"],
        "plantilla_id": res["plantilla_id"],
        "mapeo": res["mapeo"],
        "firma": res["firma"],
        "confianza": res["confianza"],
        "necesita_mapeo": res["necesita_mapeo"],
        "motivos": res["motivos"],
        "aviso_saldos": res["aviso_saldos"],
        "grilla": {
            "desde": desde,
            "columnas": ancho,
            "filas": [[_texto(_celda(f, c)) for c in range(ancho)] for f in grilla],
        },
        "encabezados": res["encabezados"],
        "total_movimientos": len(movs),
        "filas_descartadas": res["filas_descartadas"],
        "filas_resumen": res["filas_resumen"],
        "muestra": [_mov_json(m) for m in movs[:muestra]],
        "cuadre": res["cuadre"],
    }
