"""Parser best-effort de liquidaciones de tarjetas de crédito (Visa/Mastercard/Amex).

Soporta Excel/CSV (prioridad) y PDF (vía pdfminer.six si está instalado).
SIEMPRE devuelve un dict con todos los campos; los no detectados quedan en
Decimal('0'). El usuario confirma/corrige en el UI antes de guardar.
Nunca lanza excepción hacia afuera: ante cualquier error retorna el dict base
con la advertencia en `parse_warnings`.

Campos devueltos:
    periodo, fecha_acreditacion, monto_bruto, aranceles, iva_df,
    percepciones_iibb, retenciones, neto, parse_warnings
"""

from __future__ import annotations

import io
import re
import logging
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

logger = logging.getLogger(__name__)

# Keywords por campo. Se buscan como substrings (case-insensitive, sin acentos).
_KEYWORDS = {
    "monto_bruto":       ["total bruto", "total presentado", "total liquidado",
                          "importe bruto", "total operaciones", "bruto"],
    "neto":              ["total acreditado", "neto a acreditar", "importe neto",
                          "neto acreditado", "total a acreditar", "neto", "acreditado"],
    "aranceles":         ["arancel", "comision", "comisión", "descuento comercio"],
    "iva_df":            ["i.v.a", "iva", "impuesto al valor agregado"],
    "percepciones_iibb": ["percepcion", "percepción", "ingresos brutos", "iibb", "i.i.b.b"],
    "retenciones":       ["retencion", "retención", "ret. ganancias", "ret iva"],
}


def _strip_accents(s: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def _norm(s: str) -> str:
    return _strip_accents(str(s)).lower().strip()


def _parse_decimal(raw) -> Optional[Decimal]:
    """Parsea montos en formato argentino ('1.234.567,89'), US o plano."""
    if raw is None:
        return None
    if isinstance(raw, (int, float, Decimal)):
        try:
            return Decimal(str(raw))
        except (InvalidOperation, ValueError):
            return None
    s = str(raw).strip()
    if not s:
        return None
    # Quitar símbolos de moneda y espacios
    s = re.sub(r"[^\d,.\-]", "", s)
    if not s or s in ("-", ".", ","):
        return None
    # Formato argentino: el último separador decimal es la coma
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            # 1.234,56 → coma decimal
            s = s.replace(".", "").replace(",", ".")
        else:
            # 1,234.56 → punto decimal
            s = s.replace(",", "")
    elif "," in s:
        # Solo coma → decimal argentino
        s = s.replace(".", "").replace(",", ".")
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None


def _parse_fecha(raw) -> Optional[date]:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    s = str(raw).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s[:10], fmt).date()
        except ValueError:
            continue
    # Buscar un patrón de fecha embebido
    m = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})", s)
    if m:
        d, mo, y = m.groups()
        y = int(y)
        if y < 100:
            y += 2000
        try:
            return date(y, int(mo), int(d))
        except ValueError:
            return None
    return None


def _periodo_de(fecha: Optional[date]) -> Optional[str]:
    return f"{fecha.year:04d}-{fecha.month:02d}" if fecha else None


def _base_result() -> dict:
    return {
        "periodo":            None,
        "fecha_acreditacion": None,
        "monto_bruto":        Decimal("0"),
        "aranceles":          Decimal("0"),
        "iva_df":             Decimal("0"),
        "percepciones_iibb":  Decimal("0"),
        "retenciones":        Decimal("0"),
        "neto":               Decimal("0"),
        "parse_warnings":     [],
    }


def _match_campo(texto_norm: str) -> Optional[str]:
    """Devuelve el primer campo cuya keyword aparece en el texto. Orden de
    prioridad: neto/monto_bruto primero (más específicos), luego impuestos."""
    for campo in ("neto", "monto_bruto", "percepciones_iibb", "retenciones", "iva_df", "aranceles"):
        for kw in _KEYWORDS[campo]:
            if _norm(kw) in texto_norm:
                return campo
    return None


def _scan_pares(pares, result: dict, encontrados: set) -> None:
    """Recorre pares (etiqueta, valor) y completa result según keywords."""
    for etiqueta, valor in pares:
        if etiqueta is None:
            continue
        campo = _match_campo(_norm(etiqueta))
        if campo and campo not in encontrados:
            monto = _parse_decimal(valor)
            if monto is not None:
                result[campo] = abs(monto)
                encontrados.add(campo)
        # Detección de fecha de acreditación
        et_n = _norm(etiqueta)
        if result["fecha_acreditacion"] is None and ("acredit" in et_n or "fecha de pago" in et_n or "fecha pago" in et_n):
            f = _parse_fecha(valor)
            if f:
                result["fecha_acreditacion"] = f


def _parse_excel(content: bytes, result: dict, encontrados: set) -> None:
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    ws = wb.active
    for row in ws.iter_rows(values_only=True):
        cells = [c for c in row if c is not None]
        if not cells:
            continue
        # Estrategia: para cada celda de texto, mirar la siguiente celda de la fila
        for idx in range(len(row)):
            etiqueta = row[idx]
            if etiqueta is None or not isinstance(etiqueta, str):
                continue
            # buscar el primer valor numérico a la derecha en la misma fila
            valor = None
            for j in range(idx + 1, len(row)):
                if row[j] is not None:
                    valor = row[j]
                    break
            _scan_pares([(etiqueta, valor)], result, encontrados)


def _parse_csv(content: bytes, result: dict, encontrados: set) -> None:
    import csv
    text = content.decode("utf-8-sig", errors="replace")
    # autodetectar delimitador
    sample = text[:2048]
    delim = ";" if sample.count(";") > sample.count(",") else ","
    reader = csv.reader(io.StringIO(text), delimiter=delim)
    for row in reader:
        if not row:
            continue
        for idx, etiqueta in enumerate(row):
            valor = row[idx + 1] if idx + 1 < len(row) else None
            _scan_pares([(etiqueta, valor)], result, encontrados)


def _parse_pdf(content: bytes, result: dict, encontrados: set) -> None:
    try:
        from pdfminer.high_level import extract_text
    except ImportError:
        result["parse_warnings"].append(
            "pdfminer.six no instalado — el PDF no se pudo leer, cargá los datos manualmente"
        )
        return
    try:
        texto = extract_text(io.BytesIO(content)) or ""
    except Exception as ex:
        result["parse_warnings"].append(f"No se pudo extraer texto del PDF: {ex}")
        return
    # Buscar línea por línea: etiqueta + monto al final
    for linea in texto.splitlines():
        ln = linea.strip()
        if not ln:
            continue
        campo = _match_campo(_norm(ln))
        if campo and campo not in encontrados:
            # último número de la línea
            nums = re.findall(r"[-]?[\d.]+,\d{2}|[-]?[\d,]+\.\d{2}|[-]?\d+", ln)
            if nums:
                monto = _parse_decimal(nums[-1])
                if monto is not None:
                    result[campo] = abs(monto)
                    encontrados.add(campo)
        if result["fecha_acreditacion"] is None and ("acredit" in _norm(ln) or "fecha de pago" in _norm(ln)):
            f = _parse_fecha(ln)
            if f:
                result["fecha_acreditacion"] = f


def parse_liquidacion(filepath: str, marca: str) -> dict:
    """Parsea una liquidación de tarjeta desde un archivo en disco.

    Retorna un dict con los campos detectados. Los no encontrados quedan en
    Decimal('0') y se listan en `parse_warnings`. Nunca lanza excepción.
    """
    result = _base_result()
    encontrados: set = set()

    try:
        with open(filepath, "rb") as fh:
            content = fh.read()
    except Exception as ex:
        result["parse_warnings"].append(f"No se pudo abrir el archivo: {ex}")
        return result

    ext = filepath.lower().rsplit(".", 1)[-1] if "." in filepath else ""

    try:
        if ext in ("xlsx", "xls"):
            _parse_excel(content, result, encontrados)
        elif ext == "csv":
            _parse_csv(content, result, encontrados)
        elif ext == "pdf":
            _parse_pdf(content, result, encontrados)
        else:
            # intento best-effort: probar excel y caer a csv
            try:
                _parse_excel(content, result, encontrados)
            except Exception:
                _parse_csv(content, result, encontrados)
    except Exception as ex:
        logger.warning("Error parseando liquidación tarjeta (%s): %s", marca, ex)
        result["parse_warnings"].append(f"Error al parsear el archivo: {ex}")

    # Derivar período de la fecha de acreditación si la detectamos
    if result["fecha_acreditacion"]:
        result["periodo"] = _periodo_de(result["fecha_acreditacion"])

    # Si no detectamos neto pero sí bruto y componentes, lo calculamos
    bruto = result["monto_bruto"]
    componentes = (result["aranceles"] + result["iva_df"]
                   + result["percepciones_iibb"] + result["retenciones"])
    if result["neto"] == 0 and bruto > 0:
        derivado = bruto - componentes
        if derivado > 0:
            result["neto"] = derivado
            result["parse_warnings"].append("Neto calculado como bruto − componentes (no detectado en el archivo)")

    # Advertencias por campos clave faltantes
    if result["monto_bruto"] == 0:
        result["parse_warnings"].append("No se detectó el monto bruto — revisá y completá manualmente")
    if result["neto"] == 0:
        result["parse_warnings"].append("No se detectó el neto acreditado — revisá y completá manualmente")
    if result["fecha_acreditacion"] is None:
        result["parse_warnings"].append("No se detectó la fecha de acreditación — completala manualmente")

    return result
