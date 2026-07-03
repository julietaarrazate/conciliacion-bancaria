"""Parser del Excel "Mis Comprobantes" de ARCA (Emitidos / Recibidos).

Formato oficial FIJO (verificado con archivos reales):
  - Fila 1: título "Mis Comprobantes Emitidos - CUIT XXXXXXXXXXX" (o "Recibidos").
  - Fila 2: headers.
  - Datos desde fila 3.

La detección de columnas es POR NOMBRE DE HEADER (no por posición): emitidos y
recibidos difieren (recibidos agrega Tipo/Nro./Denominación del RECEPTOR además
de los del EMISOR). La contraparte se resuelve según la dirección:
  - emitido  → Nro. Doc. / Denominación **Receptor**
  - recibido → Nro. Doc. / Denominación **Emisor**

Devuelve una lista de dicts (uno por comprobante) con montos ya en Decimal.
Ignora filas sin fecha o sin tipo. Los None de Excel se normalizan a Decimal('0').
"""

from __future__ import annotations

import io
from datetime import date, datetime
from decimal import Decimal

import openpyxl

from app.services.decimal_utils import to_decimal as _D

_DOS = Decimal("0.01")

# Alícuotas del formato ARCA: (nombre_alicuota, header_iva, header_neto)
_ALICUOTAS = [
    ("0%", None, "Neto Grav. IVA 0%"),
    ("2.5%", "IVA 2,5%", "Neto Grav. IVA 2,5%"),
    ("5%", "IVA 5%", "Neto Grav. IVA 5%"),
    ("10.5%", "IVA 10,5%", "Neto Grav. IVA 10,5%"),
    ("21%", "IVA 21%", "Neto Grav. IVA 21%"),
    ("27%", "IVA 27%", "Neto Grav. IVA 27%"),
]


def _norm_header(h) -> str:
    return " ".join(str(h).split()).strip() if h is not None else ""


def _parse_fecha(v):
    """Fecha ARCA: string 'DD/MM/YYYY' o datetime (si Excel la tipó). None si no válida."""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v).strip()
    if not s:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d/%m/%y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _parse_tipo(v):
    """'1 - Factura A' → (1, '1 - Factura A'). None si no hay código numérico."""
    if v is None:
        return None, None
    s = str(v).strip()
    if not s:
        return None, None
    # El código es el número inicial antes del guion.
    head = s.split("-", 1)[0].strip()
    try:
        codigo = int(head)
    except (ValueError, TypeError):
        return None, s
    return codigo, s


def _to_int(v):
    if v is None:
        return None
    try:
        return int(str(v).strip().split(".")[0])
    except (ValueError, TypeError, AttributeError):
        return None


def parsear_mis_comprobantes(contenido: bytes, direccion: str) -> list[dict]:
    """Parsea el Excel de ARCA y devuelve la lista de comprobantes.

    Args:
        contenido: bytes del .xlsx.
        direccion: 'emitido' o 'recibido' (define de qué contraparte se toma el CUIT/denominación).

    Raises:
        ValueError: si la fila 1 no contiene "Mis Comprobantes" (archivo equivocado)
                    o si no se encuentran los headers esperados.
    """
    if direccion not in ("emitido", "recibido"):
        raise ValueError("direccion debe ser 'emitido' o 'recibido'")

    try:
        wb = openpyxl.load_workbook(io.BytesIO(contenido), read_only=True, data_only=True)
    except Exception as ex:  # noqa: BLE001
        raise ValueError(f"No se pudo abrir el archivo como Excel: {ex}")

    ws = wb.active
    rows = ws.iter_rows(values_only=True)

    try:
        fila1 = next(rows)
    except StopIteration:
        wb.close()
        raise ValueError("El archivo está vacío.")

    titulo = " ".join(str(c) for c in fila1 if c is not None)
    if "mis comprobantes" not in titulo.lower():
        wb.close()
        raise ValueError(
            "El archivo no parece ser un export de 'Mis Comprobantes' de ARCA "
            f"(la primera fila no lo menciona: {titulo[:80]!r})."
        )

    try:
        headers = next(rows)
    except StopIteration:
        wb.close()
        raise ValueError("El archivo no tiene fila de encabezados.")

    idx = {}
    for i, h in enumerate(headers):
        nombre = _norm_header(h)
        if nombre:
            idx[nombre] = i

    def col(nombre):
        return idx.get(nombre)

    # Columnas base comunes.
    c_fecha = col("Fecha")
    c_tipo = col("Tipo")
    if c_fecha is None or c_tipo is None:
        wb.close()
        raise ValueError("No se encontraron las columnas 'Fecha' y 'Tipo' en el encabezado.")

    c_pv = col("Punto de Venta")
    c_num = col("Número Desde")
    c_neto_total = col("Neto Gravado Total")
    c_total_iva = col("Total IVA")
    c_imp_total = col("Imp. Total")

    # Contraparte según dirección.
    if direccion == "emitido":
        c_cuit = col("Nro. Doc. Receptor")
        c_denom = col("Denominación Receptor")
    else:
        c_cuit = col("Nro. Doc. Emisor")
        c_denom = col("Denominación Emisor")

    # Índices de alícuotas presentes.
    alicuotas_cols = []
    for nombre_ali, h_iva, h_neto in _ALICUOTAS:
        alicuotas_cols.append((
            nombre_ali,
            col(h_iva) if h_iva else None,
            col(h_neto) if h_neto else None,
        ))

    def cell(row, i):
        if i is None or i >= len(row):
            return None
        return row[i]

    resultado: list[dict] = []
    for row in rows:
        fecha = _parse_fecha(cell(row, c_fecha))
        tipo_codigo, tipo_desc = _parse_tipo(cell(row, c_tipo))
        if fecha is None or tipo_codigo is None:
            continue  # fila vacía / sin datos válidos

        detalle_alicuotas = {}
        for nombre_ali, i_iva, i_neto in alicuotas_cols:
            iva = _D(cell(row, i_iva)).quantize(_DOS) if i_iva is not None else Decimal("0")
            neto = _D(cell(row, i_neto)).quantize(_DOS) if i_neto is not None else Decimal("0")
            if iva != 0 or neto != 0:
                detalle_alicuotas[nombre_ali] = {
                    "neto": float(neto),
                    "iva": float(iva),
                }

        cuit_raw = cell(row, c_cuit)
        cuit = str(_to_int(cuit_raw)) if _to_int(cuit_raw) is not None else (
            str(cuit_raw).strip() if cuit_raw not in (None, "") else None
        )
        denom = cell(row, c_denom)

        resultado.append({
            "fecha": fecha,
            "tipo_codigo": tipo_codigo,
            "tipo_desc": tipo_desc,
            "punto_venta": _to_int(cell(row, c_pv)),
            "numero": _to_int(cell(row, c_num)),
            "cuit_contraparte": cuit,
            "denominacion": (str(denom).strip() if denom is not None else None),
            "neto_gravado_total": _D(cell(row, c_neto_total)).quantize(_DOS),
            "total_iva": _D(cell(row, c_total_iva)).quantize(_DOS),
            "imp_total": _D(cell(row, c_imp_total)).quantize(_DOS),
            "detalle_alicuotas": detalle_alicuotas or None,
        })

    wb.close()
    return resultado
