"""Generacion de archivos Excel para download (movimientos, historial)"""

import io
from typing import List
from datetime import datetime
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

THIN = Side(style="thin", color="CCCCCC")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
HDR_FONT = Font(color="FFFFFF", bold=True, size=11)
HDR_FILL = PatternFill("solid", fgColor="3483FA")
ML_YELLOW = PatternFill("solid", fgColor="FFE600")
TITLE_FONT = Font(bold=True, size=14, color="333333")


def _autosize(ws, max_col):
    """Ajustar ancho de columnas al contenido"""
    for col in range(1, max_col + 1):
        letter = get_column_letter(col)
        max_len = 8
        for row in ws[letter]:
            v = row.value
            if v is not None:
                length = len(str(v))
                if length > max_len:
                    max_len = length
        ws.column_dimensions[letter].width = min(max_len + 2, 50)


def _hdr(ws, row, headers):
    """Aplicar formato a fila de header"""
    for col, h in enumerate(headers, start=1):
        c = ws.cell(row=row, column=col, value=h)
        c.font = HDR_FONT
        c.fill = HDR_FILL
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = BORDER


def export_movimientos(extracto_nombre: str, movimientos: List[dict]) -> bytes:
    """Genera xlsx con la lista de movimientos filtrados"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Movimientos"

    # Titulo
    ws.cell(row=1, column=1, value="Movimientos del extracto").font = TITLE_FONT
    ws.cell(row=2, column=1, value=f"Extracto: {extracto_nombre}").font = Font(italic=True, color="666666")
    ws.cell(row=3, column=1, value=f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}").font = Font(italic=True, color="666666")

    headers = ["Orden", "Fecha", "Mes", "Titular", "Importe", "Saldo", "Cliente acreditado", "Fecha acred."]
    _hdr(ws, 5, headers)

    for i, m in enumerate(movimientos, start=6):
        ws.cell(row=i, column=1, value=m.get("orden"))
        f = m.get("fecha")
        ws.cell(row=i, column=2, value=f).number_format = "DD/MM/YYYY"
        ws.cell(row=i, column=3, value=m.get("mes"))
        ws.cell(row=i, column=4, value=m.get("titular"))
        ws.cell(row=i, column=5, value=m.get("monto")).number_format = '"$"#,##0.00'
        s = m.get("saldo")
        if s is not None:
            ws.cell(row=i, column=6, value=s).number_format = '"$"#,##0.00'
        ws.cell(row=i, column=7, value=m.get("cliente_acreditado"))
        fa = m.get("fecha_acred")
        ws.cell(row=i, column=8, value=fa).number_format = "DD/MM/YYYY"

        for col in range(1, 9):
            ws.cell(row=i, column=col).border = BORDER

    _autosize(ws, 8)
    ws.freeze_panes = "A6"

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


def export_planilla_conciliada(planilla_data: dict, movimientos_acreditados: List[dict]) -> bytes:
    """
    Genera un xlsx con 2 hojas:
      Hoja 1 - Planilla del cliente con columna de estado (ok / no esta / faltan datos / etc.)
      Hoja 2 - Movimientos bancarios acreditados a esta planilla
    """
    wb = openpyxl.Workbook()

    # ── HOJA 1: planilla del cliente con estado ──────────────────────────────
    ws1 = wb.active
    ws1.title = "Planilla cliente"

    ws1.cell(row=1, column=1, value=f"Cliente: {planilla_data['cliente_nombre']}").font = TITLE_FONT
    ws1.cell(row=2, column=1, value=f"Archivo: {planilla_data['nombre_archivo']}").font = Font(italic=True, color="666666")
    ws1.cell(row=3, column=1, value=f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}").font = Font(italic=True, color="666666")

    h1 = ["#", "Importe", "CUIT", "Titular", "Estado", "Orden mov.", "Titular extracto", "Fecha mov.", "Fecha acred."]
    _hdr(ws1, 5, h1)

    STATUS_COLORS = {
        "ok": "D4EDDA",
        "no está": "F8D7DA",
        "faltan datos": "D1ECF1",
        "duplicado": "FFF3CD",
    }

    for i, row in enumerate(planilla_data["rows"], start=6):
        ws1.cell(row=i, column=1, value=i - 5)
        ws1.cell(row=i, column=2, value=row["monto"]).number_format = '"$"#,##0.00'
        ws1.cell(row=i, column=3, value=row.get("cuit") or "")
        ws1.cell(row=i, column=4, value=row.get("titular") or "")
        status_cell = ws1.cell(row=i, column=5, value=row["status"])
        # Color de fondo segun status
        color = STATUS_COLORS.get(row["status"], "FFFFFF")
        if any(row["status"].startswith(p) for p in ["acreditado"]):
            color = STATUS_COLORS["duplicado"]
        status_cell.fill = PatternFill("solid", fgColor=color)
        ws1.cell(row=i, column=6, value=row.get("orden_movimiento_acreditado"))
        ws1.cell(row=i, column=7, value=row.get("mov_titular") or "")
        f = row.get("mov_fecha")
        ws1.cell(row=i, column=8, value=f).number_format = "DD/MM/YYYY"
        fa = row.get("mov_fecha_acred")
        ws1.cell(row=i, column=9, value=fa).number_format = "DD/MM/YYYY"
        for col in range(1, 10):
            ws1.cell(row=i, column=col).border = BORDER

    ws1.freeze_panes = "A6"
    _autosize(ws1, 9)

    # ── HOJA 2: movimientos del extracto acreditados ─────────────────────────
    ws2 = wb.create_sheet("Movimientos acreditados")

    ws2.cell(row=1, column=1, value="Movimientos bancarios acreditados a esta planilla").font = TITLE_FONT

    # Headers estilo extracto Macro (azul)
    h2 = [None, "Orden", "Fecha", "Mes", "Titular / CUIT", "Importe Pesos", "Saldo", "Cliente", "Fecha acred."]
    for col, h in enumerate(h2, 1):
        c = ws2.cell(row=3, column=col, value=h)
        if h:
            c.fill = HDR_FILL
            c.font = HDR_FONT
            c.alignment = Alignment(horizontal="center")

    for i, m in enumerate(movimientos_acreditados, start=4):
        ws2.cell(row=i, column=2, value=m.get("orden"))
        f = m.get("fecha")
        ws2.cell(row=i, column=3, value=f).number_format = "DD/MM/YYYY"
        ws2.cell(row=i, column=4, value=m.get("mes"))
        ws2.cell(row=i, column=5, value=m.get("titular"))
        ws2.cell(row=i, column=6, value=m.get("monto")).number_format = '"$"#,##0.00'
        s = m.get("saldo")
        if s is not None:
            ws2.cell(row=i, column=7, value=s).number_format = '"$"#,##0.00'
        ws2.cell(row=i, column=8, value=m.get("cliente_acreditado"))
        fa = m.get("fecha_acred")
        ws2.cell(row=i, column=9, value=fa).number_format = "DD/MM/YYYY"
        for col in range(2, 10):
            ws2.cell(row=i, column=col).border = BORDER

    ws2.freeze_panes = "B4"
    _autosize(ws2, 9)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


def export_historial_planillas(planillas: List[dict]) -> bytes:
    """Genera xlsx con el historial de planillas reconciliadas"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Historial"

    ws.cell(row=1, column=1, value="Historial de reconciliaciones").font = TITLE_FONT
    ws.cell(row=2, column=1, value=f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}").font = Font(italic=True, color="666666")

    headers = ["Cliente", "Archivo", "Fecha carga", "Usuario", "Total filas", "Acreditadas", "No encontradas", "Duplicadas", "Sin datos", "% acred."]
    _hdr(ws, 4, headers)

    for i, p in enumerate(planillas, start=5):
        ws.cell(row=i, column=1, value=p["cliente_nombre"])
        ws.cell(row=i, column=2, value=p["nombre_archivo"])
        ws.cell(row=i, column=3, value=p["fecha_carga"]).number_format = "DD/MM/YYYY HH:MM"
        ws.cell(row=i, column=4, value=p["usuario_nombre"])
        ws.cell(row=i, column=5, value=p["total_filas"])
        ws.cell(row=i, column=6, value=p["acreditadas"])
        ws.cell(row=i, column=7, value=p["no_encontradas"])
        ws.cell(row=i, column=8, value=p["duplicadas"])
        ws.cell(row=i, column=9, value=p["sin_datos"])
        pct = (p["acreditadas"] / p["total_filas"]) if p["total_filas"] > 0 else 0
        ws.cell(row=i, column=10, value=pct).number_format = "0%"

        for col in range(1, 11):
            ws.cell(row=i, column=col).border = BORDER

    _autosize(ws, 10)
    ws.freeze_panes = "A5"

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()
