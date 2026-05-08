"""
Parseo de archivos Excel para extractos bancarios y planillas de clientes.
Soporta .xlsx, .xls y .csv.
Soporta Banco Macro, BBVA, Santander, Galicia, ICBC y formatos genericos.
"""

import re
import os
import tempfile
from typing import Tuple, Optional, List, Dict
from datetime import date, datetime
import openpyxl


def _convertir_xls_a_xlsx(filepath: str) -> str:
    """Convierte .xls (formato viejo) a .xlsx para procesarlo con openpyxl."""
    import xlrd
    from openpyxl import Workbook

    xls = xlrd.open_workbook(filepath)
    wb = Workbook()
    wb.remove(wb.active)

    for sheet_name in xls.sheet_names():
        xls_sheet = xls.sheet_by_name(sheet_name)
        ws = wb.create_sheet(title=sheet_name)
        for row in range(xls_sheet.nrows):
            for col in range(xls_sheet.ncols):
                cell = xls_sheet.cell(row, col)
                val = cell.value
                if cell.ctype == xlrd.XL_CELL_DATE:
                    try:
                        val = datetime(*xlrd.xldate_as_tuple(val, xls.datemode))
                    except Exception:
                        pass
                ws.cell(row=row + 1, column=col + 1, value=val)

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
    wb.save(tmp.name)
    wb.close()
    xls.release_resources()
    return tmp.name


def _convertir_csv_a_xlsx(filepath: str) -> str:
    """Convierte .csv a .xlsx para procesarlo con openpyxl."""
    import csv
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active

    encodings = ['utf-8', 'latin-1', 'cp1252']
    for enc in encodings:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                content = f.read()
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    else:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()

    delimiter = ';' if content.count(';') > content.count(',') else ','
    reader = csv.reader(content.splitlines(), delimiter=delimiter)
    for row_idx, row in enumerate(reader, 1):
        for col_idx, val in enumerate(row, 1):
            val = val.strip()
            try:
                ws.cell(row=row_idx, column=col_idx, value=float(val.replace(',', '.')))
            except ValueError:
                ws.cell(row=row_idx, column=col_idx, value=val)

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
    wb.save(tmp.name)
    wb.close()
    return tmp.name


def preparar_archivo(filepath: str) -> Tuple[str, bool]:
    """
    Si el archivo es .xls o .csv, lo convierte a .xlsx.
    Retorna (ruta_xlsx, necesita_cleanup).
    """
    ext = os.path.splitext(filepath)[1].lower()
    if ext == '.xls':
        return _convertir_xls_a_xlsx(filepath), True
    if ext in ('.csv', '.tsv'):
        return _convertir_csv_a_xlsx(filepath), True
    return filepath, False

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
KEYWORDS_ORDEN   = ["orden","nro","numero","secuencia"]
KEYWORDS_SALDO   = ["saldo","balance"]
KEYWORDS_MES     = ["mes","period","periodo"]

def _match_kw(header, keywords):
    h = header.lower().strip()
    return any(k in h for k in keywords)

def detectar_columnas(ws):
    cols = {"hdr_row":1,"monto":None,"fecha":None,"titular":None,"orden":None,"saldo":None,"mes":None}
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
    cols["monto"]   = 6
    cols["saldo"]   = 7
    return cols

def parsear_generico(ws, cols):
    movimientos = []
    hdr = cols["hdr_row"]
    for row in range(hdr + 1, ws.max_row + 1):
        monto = _parse_monto(ws.cell(row, cols["monto"]).value) if cols["monto"] else None
        if monto is None or abs(monto) < 0.01:
            continue
        fecha   = _parse_fecha(ws.cell(row, cols["fecha"]).value)   if cols["fecha"]   else None
        titular = str(ws.cell(row, cols["titular"]).value or "")     if cols["titular"] else ""
        orden   = ws.cell(row, cols["orden"]).value                  if cols["orden"]   else None
        saldo   = _parse_monto(ws.cell(row, cols["saldo"]).value)    if cols["saldo"]   else None
        mes_val = str(ws.cell(row, cols["mes"]).value or "")         if cols["mes"]     else None
        movimientos.append({
            "orden":   int(orden) if isinstance(orden,(int,float)) else None,
            "fecha":   fecha,
            "mes":     mes_val or (fecha.strftime("%B %Y") if fecha else None),
            "titular": titular.strip() or None,
            "monto":   abs(monto),
            "saldo":   saldo
        })
    return movimientos

def parsear_extracto_bancario(filepath: str) -> dict:
    """
    Parsea un extracto bancario detectando automaticamente el banco y formato.
    Soporta .xlsx, .xls y .csv.
    Prueba todas las hojas del archivo y devuelve la que tiene mas movimientos.
    """
    xlsx_path, necesita_cleanup = preparar_archivo(filepath)
    try:
        wb = openpyxl.load_workbook(xlsx_path, data_only=True)
        mejor_movs = []
        banco_detectado = "generico"
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            if ws.max_row < 3:
                continue
            banco = detectar_banco(ws)
            cols  = detectar_columnas(ws)
            movs  = parsear_generico(ws, cols)
            if len(movs) > len(mejor_movs):
                mejor_movs = movs
                banco_detectado = banco
        wb.close()
        return {"movimientos": mejor_movs, "total": len(mejor_movs), "banco_detectado": banco_detectado}
    finally:
        if necesita_cleanup and os.path.exists(xlsx_path):
            os.remove(xlsx_path)

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

def parsear_planilla_cliente(filepath: str) -> dict:
    xlsx_path, necesita_cleanup = preparar_archivo(filepath)
    try:
        wb = openpyxl.load_workbook(xlsx_path, data_only=True)
        ws = wb.active
        hdr_row, imp_col = detectar_header(ws)
        cuit_col    = detectar_cuit_col(ws, hdr_row)
        titular_col = detectar_titular_col(ws, hdr_row)
        filas = []
        for row in range(hdr_row + 1, ws.max_row + 1):
            monto = ws.cell(row, imp_col).value
            if monto is None:
                continue
            cuit    = ws.cell(row, cuit_col).value    if cuit_col    else None
            titular = ws.cell(row, titular_col).value if titular_col else None
            filas.append({"monto": monto, "cuit": str(cuit) if cuit else None, "titular": str(titular) if titular else None})
        wb.close()
        return {"filas": filas, "total": len(filas), "header_row": hdr_row, "imp_col": imp_col, "cuit_col": cuit_col, "titular_col": titular_col}
    finally:
        if necesita_cleanup and os.path.exists(xlsx_path):
            os.remove(xlsx_path)