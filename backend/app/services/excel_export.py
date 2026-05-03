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

    # Hoja 1: columnas del cliente + movimiento del extracto + Estado AL FINAL
    h1 = ["#", "Importe", "CUIT", "Titular planilla", "Orden mov.", "Titular extracto", "Fecha mov.", "Fecha acred.", "Estado"]
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
        ws1.cell(row=i, column=5, value=row.get("orden_movimiento_acreditado"))
        ws1.cell(row=i, column=6, value=row.get("mov_titular") or "")
        f = row.get("mov_fecha")
        ws1.cell(row=i, column=7, value=f).number_format = "DD/MM/YYYY"
        fa = row.get("mov_fecha_acred")
        ws1.cell(row=i, column=8, value=fa).number_format = "DD/MM/YYYY"
        # Estado ULTIMA columna con color
        st = row["status"]
        status_cell = ws1.cell(row=i, column=9, value=st)
        color = STATUS_COLORS.get(st, "FFFFFF")
        if isinstance(st, str) and st.startswith("acreditado"):
            color = STATUS_COLORS["duplicado"]
        status_cell.fill = PatternFill("solid", fgColor=color)
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


def export_extracto_contador(extracto_nombre: str, movimientos: List[dict]) -> bytes:
    """
    Export para el contador.
    Hoja 1: idéntica al extracto original (header azul Macro, orden descendente,
             filtros Excel activos, editable) + columnas cliente acreditado y fecha acred.
    Hoja 2: resumen estadístico.
    """
    # Colores Banco Macro (igual que en pantalla)
    MACRO_BLUE   = PatternFill("solid", fgColor="3483FA")
    MACRO_FONT   = Font(color="FFFFFF", bold=True, size=10)
    GREEN_FILL   = PatternFill("solid", fgColor="D4EDDA")
    GREEN_FONT   = Font(color="155724")
    TOTAL_FONT   = Font(bold=True, size=11)
    TOTAL_FILL   = PatternFill("solid", fgColor="E2EAF7")
    THIN_BLUE    = Side(style="thin", color="3483FA")
    BORDER_BLUE  = Border(bottom=THIN_BLUE)

    now_str = datetime.now().strftime('%d/%m/%Y %H:%M')

    # Ordenar: mayor orden primero (último movimiento arriba, como el original)
    movs_sorted = sorted(
        movimientos,
        key=lambda m: (m.get("orden") or 0),
        reverse=True
    )

    acreditados = [m for m in movimientos if m.get("cliente_acreditado")]
    libres      = [m for m in movimientos if not m.get("cliente_acreditado")]
    total_acred_monto = sum(m.get("monto", 0) for m in acreditados)

    wb = openpyxl.Workbook()

    # ── Hoja 1: extracto igual al original ───────────────────────────────────
    ws = wb.active
    ws.title = "Extracto conciliado"

    # Fila 1: título igual al banco
    ws.merge_cells("A1:H1")
    t = ws.cell(row=1, column=1, value=extracto_nombre)
    t.font = Font(bold=True, size=12, color="1B3F73")
    t.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 20

    # Fila 2: fecha de generación
    ws.merge_cells("A2:H2")
    ws.cell(row=2, column=1,
            value=f"Generado: {now_str}  ·  {len(acreditados)} acreditados  ·  {len(libres)} libres"
            ).font = Font(italic=True, size=9, color="666666")

    # Fila 3: headers azul Macro
    HDR_ROW = 3
    headers = ["Orden", "Fecha", "Mes", "Titular", "Importe", "Saldo", "Cliente acreditado", "Fecha acred."]
    for col, h in enumerate(headers, start=1):
        c = ws.cell(row=HDR_ROW, column=col, value=h)
        c.font   = MACRO_FONT
        c.fill   = MACRO_BLUE
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=False)
        c.border = Border(
            left=Side(style="thin", color="2968C8"),
            right=Side(style="thin", color="2968C8"),
            top=Side(style="thin", color="2968C8"),
            bottom=Side(style="thin", color="2968C8"),
        )
    ws.row_dimensions[HDR_ROW].height = 18

    # AutoFilter en fila 3 (para trabajarlo desde Excel)
    ws.auto_filter.ref = f"A{HDR_ROW}:H{HDR_ROW + len(movs_sorted)}"
    ws.freeze_panes = f"A{HDR_ROW + 1}"

    # Datos
    for i, m in enumerate(movs_sorted, start=HDR_ROW + 1):
        acred = bool(m.get("cliente_acreditado"))
        fill  = GREEN_FILL if acred else None

        def wr(col, value, fmt=None, align=None):
            c = ws.cell(row=i, column=col, value=value)
            if fill:
                c.fill = fill
            c.border = BORDER
            if fmt:
                c.number_format = fmt
            if align:
                c.alignment = Alignment(horizontal=align)
            return c

        wr(1, m.get("orden"), align="center")
        wr(2, m.get("fecha"), "DD/MM/YYYY")
        wr(3, m.get("mes"))
        wr(4, m.get("titular"))
        wr(5, m.get("monto"), '"$"#,##0.00', "right")
        saldo = m.get("saldo")
        wr(6, saldo if saldo is not None else None,
           '"$"#,##0.00' if saldo is not None else None, "right")
        c7 = wr(7, m.get("cliente_acreditado") or "")
        if acred:
            c7.font = GREEN_FONT
        wr(8, m.get("fecha_acred"), "DD/MM/YYYY")

    # Fila de totales al pie
    tot_row = HDR_ROW + len(movs_sorted) + 1
    ws.cell(row=tot_row, column=4, value="TOTAL ACREDITADO").font = TOTAL_FONT
    tc = ws.cell(row=tot_row, column=5, value=total_acred_monto)
    tc.font = TOTAL_FONT
    tc.number_format = '"$"#,##0.00'
    tc.fill = TOTAL_FILL
    tc.alignment = Alignment(horizontal="right")
    ws.cell(row=tot_row, column=7,
            value=f"{len(acreditados)} de {len(movimientos)} movimientos acreditados"
            ).font = Font(italic=True, size=9, color="3483FA")
    for col in [4, 5, 6, 7, 8]:
        ws.cell(row=tot_row, column=col).fill = TOTAL_FILL

    # Anchos fijos similares al original
    ws.column_dimensions["A"].width = 8   # Orden
    ws.column_dimensions["B"].width = 12  # Fecha
    ws.column_dimensions["C"].width = 10  # Mes
    ws.column_dimensions["D"].width = 38  # Titular
    ws.column_dimensions["E"].width = 14  # Importe
    ws.column_dimensions["F"].width = 14  # Saldo
    ws.column_dimensions["G"].width = 18  # Cliente acreditado
    ws.column_dimensions["H"].width = 14  # Fecha acred.

    # ── Hoja 2: resumen ───────────────────────────────────────────────────────
    ws2 = wb.create_sheet("Resumen")
    ws2.column_dimensions["A"].width = 28
    ws2.column_dimensions["B"].width = 20

    ws2.cell(row=1, column=1, value="Resumen del extracto").font = Font(bold=True, size=13, color="1B3F73")
    ws2.cell(row=2, column=1, value=f"Extracto: {extracto_nombre}").font = Font(italic=True, color="666666")
    ws2.cell(row=3, column=1, value=f"Generado: {now_str}").font = Font(italic=True, color="666666")

    pct = round(len(acreditados) / len(movimientos) * 100, 1) if movimientos else 0
    stats = [
        ("Total movimientos", len(movimientos)),
        ("Movimientos acreditados", len(acreditados)),
        ("Movimientos libres", len(libres)),
        ("% acreditado", f"{pct}%"),
        ("", ""),
        ("Total $ acreditado", total_acred_monto),
        ("Total $ libre", sum(m.get("monto", 0) for m in libres)),
    ]
    for j, (label, val) in enumerate(stats, start=5):
        ws2.cell(row=j, column=1, value=label).font = Font(bold=bool(label))
        c = ws2.cell(row=j, column=2, value=val)
        if isinstance(val, float):
            c.number_format = '"$"#,##0.00'
            c.font = TOTAL_FONT

    ws2.cell(row=13, column=1, value="Detalle por cliente").font = Font(bold=True, size=11, color="3483FA")
    clientes: dict = {}
    for m in acreditados:
        cl = m.get("cliente_acreditado", "")
        clientes[cl] = clientes.get(cl, 0) + 1
    for k, (cl, cnt) in enumerate(sorted(clientes.items()), start=14):
        ws2.cell(row=k, column=1, value=cl)
        ws2.cell(row=k, column=2, value=cnt)
        ws2.cell(row=k, column=2).number_format = '0" movimientos"'

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
