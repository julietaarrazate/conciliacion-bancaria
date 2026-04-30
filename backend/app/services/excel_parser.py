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
    Parsea un archivo Excel de extracto bancario o de Ultimos Movimientos.

    Detecta automaticamente la columna del importe buscando 'importe' o 'monto'
    en filas 1-3 (igual que las planillas de cliente). Si no encuentra el
    header, usa el layout default: B=orden, C=fecha, D=mes, E=titular,
    F=importe, G=saldo.
    """
    wb = openpyxl.load_workbook(filepath, data_only=True)
    ws = wb.active

    # Buscar header en filas 1-3
    hdr_row, imp_col = 2, 6  # default
    for r in range(1, 4):
        for c in range(1, ws.max_column + 1):
            h = str(ws.cell(r, c).value or '').lower().strip()
            if 'importe' in h or 'monto' in h:
                # Verificar que la columna tenga datos numericos
                hits = sum(
                    1 for dr in range(r + 1, min(r + 6, ws.max_row + 1))
                    if isinstance(ws.cell(dr, c).value, (int, float))
                )
                if hits >= 1:
                    hdr_row, imp_col = r, c
                    break
        if hdr_row != 2 or imp_col != 6:
            break

    movimientos = []
    for row in range(hdr_row + 1, ws.max_row + 1):
        # Layout estandar: -1 orden, +1 fecha, +2 mes, +3 titular, importe, +1 saldo
        # Pero como no siempre coinciden las columnas, usamos offsets relativos al imp_col
        orden = ws.cell(row, max(2, imp_col - 4)).value
        fecha = ws.cell(row, max(3, imp_col - 3)).value
        mes = ws.cell(row, max(4, imp_col - 2)).value
        titular = ws.cell(row, max(5, imp_col - 1)).value
        monto = ws.cell(row, imp_col).value
        saldo = ws.cell(row, imp_col + 1).value

        if monto is None or not isinstance(monto, (int, float)):
            continue

        movimientos.append({
            "orden": orden if isinstance(orden, (int, float)) else None,
            "fecha": fecha,
            "mes": mes,
            "titular": titular,
            "monto": float(monto),
            "saldo": float(saldo) if isinstance(saldo, (int, float)) else None
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
