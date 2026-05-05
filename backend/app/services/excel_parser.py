"""
Parseo de archivos Excel para extractos bancarios y planillas de clientes.
Soporta Banco Macro, BBVA, Santander, Galicia, ICBC y formatos genericos.
"""

import re
from typing import Tuple, Optional, List, Dict
from datetime import date, datetime
import logging
import openpyxl

logger = logging.getLogger(__name__)

INDICADORES_BANCO = {
    "macro":     ["macro", "banco macro"],
    "bbva":      ["bbva", "frances", "banco frances"],
    "santander": ["santander", "rio", "santander rio"],
    "galicia":   ["galicia", "banco galicia"],
    "icbc":      ["icbc", "industrial"],
    "nacion":    ["nacion", "banco de la nacion"],
    "provincia": ["provincia", "bapro"],
    "ciudad":    ["ciudad", "banco ciudad"],
    "hsbc":      ["hsbc"],
}

def detectar_banco(ws) -> str:
    texto = ""
    for r in range(1, min(6, ws.max_row + 1)):
        for c in range(1, min(8, ws.max_column + 1)):
            v = ws.cell(r, c).value
            if v:
                texto += " " + str(v).lower()
    for banco, palabras in INDICADORES_BANCO.items():
        for p in palabras:
            if p in texto:
                return banco
    return "generico"

def listar_hojas(filepath: str) -> list:
    """Retorna los nombres de hojas de un Excel."""
    wb = openpyxl.load_workbook(filepath, data_only=True, read_only=True)
    hojas = list(wb.sheetnames)
    wb.close()
    return hojas

def _parse_fecha(v):
    if v is None:
        return None
    if isinstance(v, (date, datetime)):
        return v.date() if isinstance(v, datetime) else v
    s = str(v).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None

def _parse_monto(v):
    if isinstance(v, (int, float)):
        return round(float(v), 2)
    if isinstance(v, str):
        s = v.strip().replace("$","").replace("\xa0","").replace(" ","")
        if not s or s in ("-",""):
            return None
        if "," in s and "." in s:
            if s.rfind(",") > s.rfind("."):
                s = s.replace(".","").replace(",",".")
            else:
                s = s.replace(",","")
        elif "," in s:
            s = s.replace(",",".")
        try:
            return round(float(s), 2)
        except ValueError:
            return None
    return None

KEYWORDS_MONTO   = ["importe","monto","credito","debito","credit","debit","haber","debe","amount"]
KEYWORDS_FECHA   = ["fecha","date","vencimiento"]
KEYWORDS_TITULAR = ["titular","concepto","descripcion","descripcion","glosa","detalle","referencia","nombre","beneficiario","ordenante"]
KEYWORDS_REFERENCIA = ["referencia", "ref", "comprobante", "operacion", "movimiento", "nro op", "id transaccion"]
KEYWORDS_ORDEN   = ["orden","nro","numero","secuencia"]
KEYWORDS_SALDO   = ["saldo","balance"]
KEYWORDS_MES     = ["mes","period","periodo"]

def _match_kw(header, keywords):
    h = header.lower().strip()
    return any(k in h for k in keywords)

def detectar_columnas(ws):
    cols = {"hdr_row":1,"monto":None,"fecha":None,"titular":None,"referencia":None,"orden":None,"saldo":None,"mes":None}
    for r in range(1, 7):
        encontrados = {}
        for c in range(1, ws.max_column + 1):
            h = str(ws.cell(r, c).value or "").lower().strip()
            if not h:
                continue
            if _match_kw(h, KEYWORDS_MONTO):
                encontrados["monto"] = c
            elif _match_kw(h, KEYWORDS_FECHA):
                encontrados["fecha"] = c
            elif _match_kw(h, KEYWORDS_TITULAR):
                encontrados.setdefault("titular", c)
            elif _match_kw(h, KEYWORDS_REFERENCIA):
                encontrados.setdefault("referencia", c)
            elif _match_kw(h, KEYWORDS_ORDEN):
                encontrados.setdefault("orden", c)
            elif _match_kw(h, KEYWORDS_SALDO):
                encontrados.setdefault("saldo", c)
            elif _match_kw(h, KEYWORDS_MES):
                encontrados.setdefault("mes", c)
        if "monto" in encontrados:
            cols["hdr_row"] = r
            cols.update(encontrados)
            return cols
    # Fallback Banco Macro
    cols["hdr_row"] = 2
    cols["orden"]   = 2
    cols["fecha"]   = 3
    cols["mes"]     = 4
    cols["titular"] = 5
    cols["referencia"] = 5
    cols["monto"]   = 6
    cols["saldo"]   = 7
    return cols

def parsear_generico(ws, cols):
    movimientos = []
    invalid_rows = []
    hdr = cols["hdr_row"]
    for row in range(hdr + 1, ws.max_row + 1):
        monto = _parse_monto(ws.cell(row, cols["monto"]).value) if cols["monto"] else None
        if monto is None or abs(monto) < 0.01:
            continue
        fecha   = _parse_fecha(ws.cell(row, cols["fecha"]).value)   if cols["fecha"]   else None
        titular = str(ws.cell(row, cols["titular"]).value or "")     if cols["titular"] else ""
        referencia = str(ws.cell(row, cols["referencia"]).value or "").strip() if cols["referencia"] else ""
        orden   = ws.cell(row, cols["orden"]).value                  if cols["orden"]   else None
        saldo   = _parse_monto(ws.cell(row, cols["saldo"]).value)    if cols["saldo"]   else None
        mes_val = str(ws.cell(row, cols["mes"]).value or "")         if cols["mes"]     else None
        if fecha is None:
            invalid_rows.append({"row": row, "reason": "fecha inválida o vacía"})
            continue
        referencia_final = referencia or titular.strip()
        if not referencia_final:
            invalid_rows.append({"row": row, "reason": "referencia/titular vacío"})
            continue
        movimientos.append({
            "orden":   int(orden) if isinstance(orden,(int,float)) else None,
            "fecha":   fecha,
            "mes":     mes_val or (fecha.strftime("%B %Y") if fecha else None),
            "titular": titular.strip() or None,
            "referencia": referencia_final,
            "monto":   abs(monto),
            "saldo":   saldo
        })
    return movimientos, invalid_rows

def parsear_extracto_bancario(filepath: str) -> dict:
    """
    Parsea un extracto bancario detectando automaticamente el banco y formato.
    Soporta Macro, BBVA, Santander, Galicia, ICBC y formato generico.
    Prueba todas las hojas del archivo y devuelve la que tiene mas movimientos.
    """
    wb = openpyxl.load_workbook(filepath, data_only=True)
    mejor_movs = []
    banco_detectado = "generico"
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        if ws.max_row < 3:
            continue
        banco = detectar_banco(ws)
        cols  = detectar_columnas(ws)
        movs, invalid_rows = parsear_generico(ws, cols)
        if invalid_rows:
            logger.warning("Se omitieron %s filas inválidas en hoja '%s': %s", len(invalid_rows), sheet_name, invalid_rows[:20])
        if len(movs) > len(mejor_movs):
            mejor_movs = movs
            banco_detectado = banco
    wb.close()
    return {"movimientos": mejor_movs, "total": len(mejor_movs), "banco_detectado": banco_detectado}

def detectar_header(ws):
    for r in range(1, 6):
        for c in range(1, ws.max_column + 1):
            h = str(ws.cell(r, c).value or '').lower().strip()
            if 'monto' in h or 'importe' in h:
                data_start = r + 1
                for test_col in [c, c + 1]:
                    hits = sum(
                        1 for dr in range(data_start, min(data_start + 6, ws.max_row + 1))
                        if isinstance(ws.cell(dr, test_col).value, (int, float))
                        and 0 < ws.cell(dr, test_col).value < 5_000_000
                    )
                    if hits >= 1:
                        return r, test_col
    return 2, 6

def detectar_cuit_col(ws, hdr_row):
    for c in range(1, ws.max_column + 1):
        h = str(ws.cell(hdr_row, c).value or '').lower().strip()
        if 'cuit' in h or 'cuil' in h:
            return c
    return None

def detectar_titular_col(ws, hdr_row):
    for c in range(1, ws.max_column + 1):
        h = str(ws.cell(hdr_row, c).value or '').lower().strip()
        if 'titular' in h or 'nombre' in h or 'cliente' in h:
            return c
    return None

def parsear_planilla_cliente(filepath: str, sheet_name: Optional[str] = None) -> dict:
    wb = openpyxl.load_workbook(filepath, data_only=True)
    if sheet_name and sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
    else:
        ws = wb.active
    hdr_row, imp_col = detectar_header(ws)
    cuit_col    = detectar_cuit_col(ws, hdr_row)
    titular_col = detectar_titular_col(ws, hdr_row)

    # Leer headers originales de la fila de encabezado
    headers_originales = []
    for c in range(1, ws.max_column + 1):
        v = ws.cell(hdr_row, c).value
        headers_originales.append(str(v).strip() if v is not None else f"Col{c}")

    filas = []
    for row in range(hdr_row + 1, ws.max_row + 1):
        monto = ws.cell(row, imp_col).value
        if monto is None:
            continue
        cuit    = ws.cell(row, cuit_col).value    if cuit_col    else None
        titular = ws.cell(row, titular_col).value if titular_col else None

        # Guardar todas las columnas originales como dict
        datos_originales = {}
        for c, h in enumerate(headers_originales, start=1):
            v = ws.cell(row, c).value
            if v is not None:
                datos_originales[h] = str(v) if not isinstance(v, (int, float)) else v

        filas.append({
            "monto": monto,
            "cuit": str(cuit) if cuit else None,
            "titular": str(titular) if titular else None,
            "datos_originales": datos_originales if datos_originales else None,
        })
    wb.close()
    return {
        "filas": filas,
        "total": len(filas),
        "headers_originales": headers_originales,
        "header_row": hdr_row,
        "imp_col": imp_col,
        "cuit_col": cuit_col,
        "titular_col": titular_col,
    }
