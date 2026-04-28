"""
Parseo de archivos Excel para extractos bancarios y planillas de clientes
Reutiliza la lógica de detección automática del watcher.py
"""

from typing import Tuple, Optional, List
import openpyxl
from pathlib import Path

def detectar_header(ws) -> Tuple[int, int]:
    """
    Busca 'monto' o 'importe' en filas 1-5.
    Verifica que la col (o col+1) tenga datos numéricos reales.
    Retorna (header_row, imp_col).
    """
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

def detectar_cuit_col(ws, hdr_row) -> Optional[int]:
    """Detecta columna de CUIT buscando 'cuit' en el header"""
    for c in range(1, ws.max_column + 1):
        h = str(ws.cell(hdr_row, c).value or '').lower().strip()
        if 'cuit' in h or 'cuil' in h:
            return c
    return None

def detectar_titular_col(ws, hdr_row) -> Optional[int]:
    """Detecta columna de titular buscando 'titular' o 'nombre'"""
    for c in range(1, ws.max_column + 1):
        h = str(ws.cell(hdr_row, c).value or '').lower().strip()
        if 'titular' in h or 'nombre' in h or 'cliente' in h:
            return c
    return None

def parsear_extracto_bancario(filepath: str) -> dict:
    """
    Parsea un archivo Excel de extracto bancario.
    Retorna dict con movimientos.
    """
    wb = openpyxl.load_workbook(filepath, data_only=True)
    ws = wb.active

    # Estructura esperada: fila 2 = headers, fila 3+ = datos
    movimientos = []
    for row in range(3, ws.max_row + 1):
        orden = ws.cell(row, 2).value  # Col B
        fecha = ws.cell(row, 3).value  # Col C
        mes = ws.cell(row, 4).value    # Col D
        titular = ws.cell(row, 5).value  # Col E
        monto = ws.cell(row, 6).value  # Col F
        saldo = ws.cell(row, 7).value  # Col G

        if monto is None:
            continue

        movimientos.append({
            "orden": orden,
            "fecha": fecha,
            "mes": mes,
            "titular": titular,
            "monto": float(monto),
            "saldo": saldo
        })

    wb.close()
    return {
        "movimientos": movimientos,
        "total": len(movimientos)
    }

def parsear_planilla_cliente(filepath: str) -> dict:
    """
    Parsea un archivo Excel de planilla de cliente.
    Detecta automáticamente headers y columnas.
    Retorna dict con filas y metadatos.
    """
    wb = openpyxl.load_workbook(filepath, data_only=True)
    ws = wb.active

    # Detectar header
    hdr_row, imp_col = detectar_header(ws)
    cuit_col = detectar_cuit_col(ws, hdr_row)
    titular_col = detectar_titular_col(ws, hdr_row)

    filas = []
    for row in range(hdr_row + 1, ws.max_row + 1):
        monto = ws.cell(row, imp_col).value
        if monto is None:
            continue

        cuit = ws.cell(row, cuit_col).value if cuit_col else None
        titular = ws.cell(row, titular_col).value if titular_col else None

        filas.append({
            "monto": monto,
            "cuit": str(cuit) if cuit else None,
            "titular": str(titular) if titular else None
        })

    wb.close()
    return {
        "filas": filas,
        "total": len(filas),
        "header_row": hdr_row,
        "imp_col": imp_col,
        "cuit_col": cuit_col,
        "titular_col": titular_col
    }
