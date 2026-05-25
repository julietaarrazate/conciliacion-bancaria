"""Generacion de reportes PDF — estado de cuenta y cierre mensual.

Usa reportlab. Sin imagenes externas (todo SVG/texto) para que no
dependa de assets del filesystem del servidor.
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
)

# Paleta visual (alineada con la UI ML-style)
_GREEN = colors.HexColor("#00C853")
_RED = colors.HexColor("#E53935")
_DARK = colors.HexColor("#1A1A1A")
_GRAY = colors.HexColor("#6B7280")
_LIGHT_GRAY = colors.HexColor("#F3F4F6")
_BORDER = colors.HexColor("#E5E7EB")

MESES_ES = [
    "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]


def _fmt_ars(n: float) -> str:
    return f"$ {n:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title", parent=base["Heading1"],
            fontName="Helvetica-Bold", fontSize=18, textColor=_DARK,
            spaceAfter=6,
        ),
        "subtitle": ParagraphStyle(
            "subtitle", parent=base["Normal"],
            fontName="Helvetica", fontSize=10, textColor=_GRAY,
            spaceAfter=18,
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"],
            fontName="Helvetica-Bold", fontSize=12, textColor=_DARK,
            spaceBefore=14, spaceAfter=8,
        ),
        "body": ParagraphStyle(
            "body", parent=base["Normal"],
            fontName="Helvetica", fontSize=9, textColor=_DARK,
        ),
        "small": ParagraphStyle(
            "small", parent=base["Normal"],
            fontName="Helvetica", fontSize=8, textColor=_GRAY,
        ),
    }


def _kpi_grid(items: list[tuple[str, str, Any]]) -> Table:
    """items: lista de (label, valor, color_valor o None)."""
    cells = []
    for label, valor, color_v in items:
        color_v = color_v or _DARK
        cells.append([
            Paragraph(f'<font color="{_GRAY.hexval()}" size="8">{label.upper()}</font>', _styles()["small"]),
            Paragraph(f'<font color="{color_v.hexval()}" size="13"><b>{valor}</b></font>', _styles()["body"]),
        ])
    n = len(cells)
    rows = []
    for i in range(0, n, 2):
        left = cells[i]
        right = cells[i + 1] if i + 1 < n else [Paragraph("", _styles()["body"]), Paragraph("", _styles()["body"])]
        rows.append([left[0], right[0]])
        rows.append([left[1], right[1]])

    t = Table(rows, colWidths=[85 * mm, 85 * mm], hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _LIGHT_GRAY),
        ("BOX", (0, 0), (-1, -1), 0.5, _BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, _BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def _footer(generado_por: str = "Julieta Arrazate") -> Paragraph:
    fecha = datetime.now().strftime("%d/%m/%Y %H:%M")
    txt = (
        f'<font color="{_GRAY.hexval()}" size="8">'
        f"Generado el {fecha} - {generado_por} - Conciliacion Bancaria"
        "</font>"
    )
    return Paragraph(txt, _styles()["small"])


# ---------------------------------------------------------------------------
# Estado de cuenta por cliente
# ---------------------------------------------------------------------------
def estado_cuenta_pdf(data: dict, generado_por: str = "Julieta Arrazate") -> bytes:
    """Recibe el dict que devuelve /analisis/cliente/{id}/estado-cuenta."""
    s = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=18 * mm, bottomMargin=15 * mm,
        title=f"Estado de cuenta - {data['cliente']['nombre']}",
    )

    cliente = data["cliente"]
    periodo = data["periodo"]
    resumen = data["resumen"]

    story = []
    story.append(Paragraph("Estado de cuenta", s["title"]))
    sub = f"<b>{cliente['nombre']}</b>"
    if cliente.get("cuit"):
        sub += f" - CUIT {cliente['cuit']}"
    sub += f"<br/>Periodo: {periodo['desde']} a {periodo['hasta']}"
    story.append(Paragraph(sub, s["subtitle"]))

    story.append(_kpi_grid([
        ("Conciliado", _fmt_ars(resumen["conciliado_periodo"]), _GREEN),
        ("Pendiente", _fmt_ars(resumen["pendiente_periodo"]), _RED),
        ("Cheques pendientes", _fmt_ars(resumen["cheques_pendientes_monto"]), None),
        ("Pagos realizados", _fmt_ars(resumen["pagos_realizados_monto"]), None),
    ]))

    planillas = data.get("planillas") or []
    if planillas:
        story.append(Paragraph(f"Planillas ({len(planillas)})", s["h2"]))
        rows = [["Fecha", "Archivo", "Filas", "Conciliado", "Pendiente"]]
        for p in planillas:
            fecha = (p.get("fecha_carga") or "")[:10]
            rows.append([
                fecha,
                p.get("nombre_archivo") or "-",
                str(len(p.get("filas") or [])),
                _fmt_ars(p.get("subtotal_ok") or 0),
                _fmt_ars(p.get("subtotal_pendiente") or 0),
            ])
        t = Table(rows, colWidths=[22 * mm, 70 * mm, 14 * mm, 32 * mm, 32 * mm], repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), _DARK),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (3, 0), (-1, -1), "RIGHT"),
            ("ALIGN", (2, 0), (2, -1), "CENTER"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _LIGHT_GRAY]),
            ("BOX", (0, 0), (-1, -1), 0.5, _BORDER),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, _BORDER),
            ("TEXTCOLOR", (3, 1), (3, -1), _GREEN),
            ("TEXTCOLOR", (4, 1), (4, -1), _RED),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t)

    cheques = data.get("cheques") or []
    if cheques:
        story.append(Paragraph(f"Cheques ({len(cheques)})", s["h2"]))
        rows = [["Numero", "Banco", "Emision", "Deposito", "Monto", "Estado"]]
        for c in cheques:
            rows.append([
                c.get("numero") or "-",
                (c.get("banco_origen") or "-")[:18],
                (c.get("fecha_emision") or "-")[:10],
                (c.get("fecha_deposito") or "-")[:10],
                _fmt_ars(c.get("monto") or 0),
                (c.get("estado") or "").upper(),
            ])
        t = Table(rows, colWidths=[24 * mm, 32 * mm, 22 * mm, 22 * mm, 30 * mm, 22 * mm], repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), _DARK),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (4, 0), (4, -1), "RIGHT"),
            ("ALIGN", (5, 0), (5, -1), "CENTER"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _LIGHT_GRAY]),
            ("BOX", (0, 0), (-1, -1), 0.5, _BORDER),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, _BORDER),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t)

    pagos = data.get("pagos") or []
    if pagos:
        story.append(Paragraph(f"Pagos al cliente ({len(pagos)})", s["h2"]))
        rows = [["Fecha", "Concepto", "Medio", "Monto"]]
        for p in pagos:
            rows.append([
                (p.get("fecha") or "-")[:10],
                (p.get("concepto") or "-")[:45],
                p.get("medio") or "-",
                _fmt_ars(p.get("monto") or 0),
            ])
        t = Table(rows, colWidths=[22 * mm, 88 * mm, 28 * mm, 32 * mm], repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), _DARK),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (3, 0), (3, -1), "RIGHT"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _LIGHT_GRAY]),
            ("BOX", (0, 0), (-1, -1), 0.5, _BORDER),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, _BORDER),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t)

    if not planillas and not cheques and not pagos:
        story.append(Spacer(1, 12))
        story.append(Paragraph(
            '<font color="' + _GRAY.hexval() + '" size="10"><i>Sin movimientos en el periodo seleccionado.</i></font>',
            s["body"],
        ))

    story.append(Spacer(1, 16))
    story.append(_footer(generado_por))

    doc.build(story)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Cierre mensual (KPIs del dashboard)
# ---------------------------------------------------------------------------
def cierre_mensual_pdf(
    data: dict, anio: int, mes: int, org_nombre: str | None = None,
    generado_por: str = "Julieta Arrazate",
) -> bytes:
    """Recibe el dict de /analisis/dashboard?periodo=mes&anio&mes."""
    s = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=18 * mm, bottomMargin=15 * mm,
        title=f"Cierre mensual {MESES_ES[mes]} {anio}",
    )

    story = []
    titulo = f"Cierre mensual - {MESES_ES[mes]} {anio}"
    story.append(Paragraph(titulo, s["title"]))
    if org_nombre:
        story.append(Paragraph(f"<b>{org_nombre}</b>", s["subtitle"]))
    else:
        story.append(Spacer(1, 6))

    pa = data.get("periodo_actual") or {}
    conciliado = (pa.get("conciliado") or {}).get("total") or 0
    pendiente = (pa.get("pendiente") or {}).get("total") or 0
    tasa = pa.get("tasa_conciliacion_pct") or 0
    movs = (pa.get("movimientos_banco") or {}).get("cantidad") or 0

    story.append(_kpi_grid([
        ("Conciliado", _fmt_ars(conciliado), _GREEN),
        ("Pendiente", _fmt_ars(pendiente), _RED),
        ("Tasa de conciliacion", f"{tasa:.1f}%", None),
        ("Movimientos del banco", str(movs), None),
    ]))

    pagos_total = (pa.get("pagos") or {}).get("total") or 0
    gastos_total = (pa.get("gastos") or {}).get("total") or 0
    cheques_count = (pa.get("cheques_cargados") or {}).get("cantidad") or 0

    story.append(_kpi_grid([
        ("Cheques cargados", str(cheques_count), None),
        ("Pagos", _fmt_ars(pagos_total), None),
        ("Gastos", _fmt_ars(gastos_total), None),
        ("Diferencia neta", _fmt_ars(pagos_total - gastos_total), None),
    ]))

    top = data.get("top_clientes") or []
    if top:
        story.append(Paragraph(f"Top {len(top)} clientes del mes", s["h2"]))
        rows = [["#", "Cliente", "Conciliado"]]
        for i, c in enumerate(top, 1):
            rows.append([
                str(i),
                (c.get("nombre") or "-")[:60],
                _fmt_ars(c.get("total") or 0),
            ])
        t = Table(rows, colWidths=[10 * mm, 120 * mm, 40 * mm], repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), _DARK),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("ALIGN", (2, 0), (2, -1), "RIGHT"),
            ("TEXTCOLOR", (2, 1), (2, -1), _GREEN),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _LIGHT_GRAY]),
            ("BOX", (0, 0), (-1, -1), 0.5, _BORDER),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, _BORDER),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t)

    ch_resumen = ((data.get("cheques") or {}).get("resumen") or {})
    if ch_resumen:
        story.append(Paragraph("Cheques en cartera", s["h2"]))
        rows = [["Estado", "Cantidad", "Monto"]]
        for estado in ("pendiente", "acreditado", "rechazado"):
            info = ch_resumen.get(estado) or {}
            rows.append([
                estado.capitalize(),
                str(info.get("cantidad") or 0),
                _fmt_ars(info.get("total") or 0),
            ])
        t = Table(rows, colWidths=[60 * mm, 40 * mm, 70 * mm], repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), _DARK),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (1, 0), (1, -1), "CENTER"),
            ("ALIGN", (2, 0), (2, -1), "RIGHT"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _LIGHT_GRAY]),
            ("BOX", (0, 0), (-1, -1), 0.5, _BORDER),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, _BORDER),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t)

    proximos = (data.get("cheques") or {}).get("proximos_a_vencer") or []
    if proximos:
        story.append(Paragraph(f"Cheques proximos a vencer ({len(proximos)})", s["h2"]))
        rows = [["Numero", "Cliente / Titular", "Deposito", "Dias", "Monto"]]
        for c in proximos:
            who = c.get("cliente_nombre") or c.get("titular") or "-"
            rows.append([
                c.get("numero") or "-",
                who[:30],
                (c.get("fecha_deposito") or "-")[:10],
                str(c.get("dias_para_vencer") or "-"),
                _fmt_ars(c.get("monto") or 0),
            ])
        t = Table(rows, colWidths=[26 * mm, 60 * mm, 24 * mm, 18 * mm, 42 * mm], repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), _DARK),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (3, 0), (3, -1), "CENTER"),
            ("ALIGN", (4, 0), (4, -1), "RIGHT"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _LIGHT_GRAY]),
            ("BOX", (0, 0), (-1, -1), 0.5, _BORDER),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, _BORDER),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t)

    story.append(Spacer(1, 16))
    story.append(_footer(generado_por))

    doc.build(story)
    return buf.getvalue()
