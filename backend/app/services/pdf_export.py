"""Generacion de reportes PDF — estado de cuenta y cierre mensual.

Usa reportlab. Sin imagenes externas (todo texto/formas dibujadas en canvas)
para que no dependa de assets del filesystem del servidor.

Diseño profesional: banda de encabezado de marca, tarjetas KPI tipo dashboard,
tablas modernas (solo líneas horizontales), caja de totales destacada y footer
con numeración de página.
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import Any, Optional
from app.services.tz import now_art

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether,
)

# ── Paleta de marca Cuadra (negro + verde) ───────────────────────────────────
_BRAND = colors.HexColor("#111827")        # primario negro (header, tablas)
_BRAND_DARK = colors.HexColor("#00C853")   # acento verde Cuadra
_BRAND_TINT = colors.HexColor("#F1FDF6")   # fondo suave verde claro (tarjetas/box)
_GREEN = colors.HexColor("#00C853")        # positivo / conciliado (verde Cuadra)
_RED = colors.HexColor("#DC2626")          # pendiente / negativo
_AMBER = colors.HexColor("#D97706")        # alerta / comisión
_DARK = colors.HexColor("#111827")         # texto principal
_GRAY = colors.HexColor("#6B7280")         # texto secundario
_ROW_ALT = colors.HexColor("#F9FAFB")      # zebra sutil
_BORDER = colors.HexColor("#E5E7EB")       # líneas

# Márgenes (mm)
_ML = 16
_MR = 16
_MT = 18
_MB = 20
_CONTENT_W = (210 - _ML - _MR) * mm        # ancho útil del contenido

MESES_ES = [
    "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]


def _fmt_ars(n: float) -> str:
    try:
        n = float(n or 0)
    except (TypeError, ValueError):
        n = 0.0
    return f"$ {n:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "band": ParagraphStyle(
            "band", parent=base["Normal"],
            fontName="Helvetica-Bold", fontSize=17, textColor=colors.white,
            leading=20,
        ),
        "band_right": ParagraphStyle(
            "band_right", parent=base["Normal"],
            fontName="Helvetica", fontSize=8, textColor=colors.white,
            alignment=TA_RIGHT, leading=12,
        ),
        "subtitle": ParagraphStyle(
            "subtitle", parent=base["Normal"],
            fontName="Helvetica", fontSize=9.5, textColor=_GRAY,
            spaceBefore=8, spaceAfter=4, leading=14,
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"],
            fontName="Helvetica-Bold", fontSize=11.5, textColor=_DARK,
            spaceBefore=2, spaceAfter=4,
        ),
        "kpi": ParagraphStyle(
            "kpi", parent=base["Normal"],
            fontName="Helvetica", fontSize=9, textColor=_DARK, leading=15,
        ),
        "body": ParagraphStyle(
            "body", parent=base["Normal"],
            fontName="Helvetica", fontSize=9, textColor=_DARK, leading=12,
        ),
        "cell": ParagraphStyle(
            "cell", parent=base["Normal"],
            fontName="Helvetica", fontSize=8.5, textColor=_DARK, leading=11,
        ),
        "small": ParagraphStyle(
            "small", parent=base["Normal"],
            fontName="Helvetica", fontSize=8, textColor=_GRAY, leading=11,
        ),
        "empty": ParagraphStyle(
            "empty", parent=base["Normal"],
            fontName="Helvetica-Oblique", fontSize=10, textColor=_GRAY,
        ),
    }


# ── Componentes de diseño ─────────────────────────────────────────────────────
def _header_band(titulo: str, etiqueta_der: str, valor_der: str) -> Table:
    s = _styles()
    left = Paragraph(titulo, s["band"])
    right = Paragraph(
        f'<font color="#DDE1F7" size="8">{etiqueta_der}</font><br/>'
        f'<font color="white" size="9.5"><b>{valor_der}</b></font>',
        s["band_right"],
    )
    t = Table([[left, right]], colWidths=[_CONTENT_W * 0.62, _CONTENT_W * 0.38])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _BRAND),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
        ("RIGHTPADDING", (0, 0), (-1, -1), 14),
        ("TOPPADDING", (0, 0), (-1, -1), 13),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 13),
        ("LINEBELOW", (0, 0), (-1, -1), 3, _BRAND_DARK),
    ]))
    return t


def _kpi_cards(items: list[tuple[str, str, Any]]) -> Table:
    """items: (label, valor, color_valor|None). Hasta 4 por fila."""
    s = _styles()
    n = max(1, len(items))
    cells, accents = [], []
    for label, valor, color_v in items:
        col = color_v or _BRAND
        cells.append(Paragraph(
            f'<font color="{_GRAY.hexval()}" size="7">{label.upper()}</font><br/>'
            f'<font color="{col.hexval()}" size="13"><b>{valor}</b></font>',
            s["kpi"],
        ))
        accents.append(col)
    colW = _CONTENT_W / n
    t = Table([cells], colWidths=[colW] * n)
    style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (-1, -1), _BRAND_TINT),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ("LEFTPADDING", (0, 0), (-1, -1), 11),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]
    for i, col in enumerate(accents):
        style.append(("LINEABOVE", (i, 0), (i, 0), 2.5, col))
    for i in range(1, n):  # separación blanca entre tarjetas
        style.append(("LINEBEFORE", (i, 0), (i, 0), 4, colors.white))
    t.setStyle(TableStyle(style))
    return t


def _section(texto: str) -> list:
    s = _styles()
    p = Paragraph(texto, s["h2"])
    rule = Table([[""]], colWidths=[_CONTENT_W], rowHeights=[1.4])
    rule.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), _BRAND)]))
    return [Spacer(1, 10), p, rule, Spacer(1, 5)]


def _tabla(
    headers: list[str],
    rows: list[list[str]],
    col_widths: list[float],
    *,
    aligns: Optional[dict[int, str]] = None,
    money_cols: Optional[list[int]] = None,
    color_cols: Optional[dict[int, Any]] = None,
    font_size: float = 8.5,
) -> Table:
    """Tabla moderna: header de marca, zebra sutil, solo líneas horizontales."""
    data = [headers] + rows
    t = Table(data, colWidths=col_widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), _BRAND),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), font_size),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), font_size),
        ("TEXTCOLOR", (0, 1), (-1, -1), _DARK),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _ROW_ALT]),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, _BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
    ]
    if aligns:
        for col, al in aligns.items():
            style.append(("ALIGN", (col, 0), (col, -1), al))
    if money_cols:
        for col in money_cols:
            style.append(("ALIGN", (col, 0), (col, -1), "RIGHT"))
            style.append(("FONTNAME", (col, 1), (col, -1), "Helvetica-Bold"))
    if color_cols:
        for col, color in color_cols.items():
            style.append(("TEXTCOLOR", (col, 1), (col, -1), color))
    t.setStyle(TableStyle(style))
    return t


def _totales_box(items: list[tuple[str, str, Any, bool]]) -> Table:
    """Caja destacada de totales. items: (label, valor, color|None, resaltado)."""
    s = _styles()
    rows = []
    for label, valor, color_v, fuerte in items:
        col = color_v or _DARK
        lbl = Paragraph(
            (f"<b>{label}</b>" if fuerte else label), s["body"],
        )
        size = 12 if fuerte else 9
        val = Paragraph(
            f'<para align="right"><font color="{col.hexval()}" size="{size}"><b>{valor}</b></font></para>',
            s["body"],
        )
        rows.append([lbl, val])
    t = Table(rows, colWidths=[_CONTENT_W * 0.62, _CONTENT_W * 0.38], hAlign="LEFT")
    style = [
        ("BACKGROUND", (0, 0), (-1, -1), _BRAND_TINT),
        ("LINEABOVE", (0, 0), (-1, 0), 2.5, _BRAND),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]
    # separador antes de la última fila (neto)
    if len(rows) >= 2:
        style.append(("LINEABOVE", (0, len(rows) - 1), (-1, len(rows) - 1), 0.6, _BORDER))
        style.append(("TOPPADDING", (0, len(rows) - 1), (-1, len(rows) - 1), 9))
        style.append(("BOTTOMPADDING", (0, len(rows) - 1), (-1, len(rows) - 1), 9))
    t.setStyle(TableStyle(style))
    return t


def _page_decorator(generado_por: str):
    """Footer dibujado en canvas: línea + datos + número de página."""
    def _draw(canvas, doc):
        canvas.saveState()
        w, _h = A4
        canvas.setStrokeColor(_BORDER)
        canvas.setLineWidth(0.5)
        canvas.line(_ML * mm, 14 * mm, (210 - _MR) * mm, 14 * mm)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(_GRAY)
        fecha = now_art().strftime("%d/%m/%Y %H:%M")
        canvas.drawString(_ML * mm, 9.5 * mm, f"Generado {fecha}  ·  {generado_por}")
        canvas.drawCentredString(w / 2, 9.5 * mm, "Conciliación Bancaria")
        canvas.drawRightString((210 - _MR) * mm, 9.5 * mm, f"Página {doc.page}")
        canvas.restoreState()
    return _draw


def _empty_note(texto: str) -> Paragraph:
    return Paragraph(texto, _styles()["empty"])


# ---------------------------------------------------------------------------
# Estado de cuenta por cliente
# ---------------------------------------------------------------------------
def estado_cuenta_pdf(data: dict, generado_por: str = "Julieta Arrazate") -> bytes:
    """Recibe el dict que devuelve /analisis/cliente/{id}/estado-cuenta."""
    s = _styles()
    buf = io.BytesIO()
    cliente = data["cliente"]
    periodo = data["periodo"]
    resumen = data["resumen"]

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=_ML * mm, rightMargin=_MR * mm,
        topMargin=_MT * mm, bottomMargin=_MB * mm,
        title=f"Estado de cuenta - {cliente['nombre']}",
        author=generado_por,
    )

    story: list = []
    # Encabezado de marca
    story.append(_header_band(
        "Estado de cuenta",
        "Período",
        f"{periodo['desde']}  a  {periodo['hasta']}",
    ))
    # Datos del cliente
    sub = f"<b>{cliente['nombre']}</b>"
    if cliente.get("cuit"):
        sub += f'  ·  CUIT {cliente["cuit"]}'
    pct = resumen.get("porcentaje_comision")
    if pct:
        sub += f'  ·  Comisión {float(pct):.2f}%'
    story.append(Paragraph(sub, s["subtitle"]))

    # KPIs
    story.append(Spacer(1, 4))
    story.append(_kpi_cards([
        ("Conciliado", _fmt_ars(resumen.get("conciliado_periodo")), _GREEN),
        ("Pendiente", _fmt_ars(resumen.get("pendiente_periodo")), _RED),
        ("Cheques pend.", _fmt_ars(resumen.get("cheques_pendientes_monto")), None),
        ("Pagos al cliente", _fmt_ars(resumen.get("pagos_realizados_monto")), None),
    ]))

    # Caja de totales (comisión / neto) si hay datos
    comision = resumen.get("comision_monto")
    neto = resumen.get("neto_calculado")
    if comision is not None or neto is not None:
        story.append(Spacer(1, 12))
        items = [
            ("Total conciliado", _fmt_ars(resumen.get("conciliado_periodo")), _DARK, False),
        ]
        if comision is not None:
            pct_txt = f' ({float(pct):.2f}%)' if pct else ""
            items.append((f"Comisión{pct_txt}", "- " + _fmt_ars(comision), _AMBER, False))
        if neto is not None:
            items.append(("Neto a liquidar", _fmt_ars(neto), _BRAND_DARK, True))
        story.append(_totales_box(items))

    # Planillas
    planillas = data.get("planillas") or []
    if planillas:
        block = _section(f"Planillas ({len(planillas)})")
        rows = []
        for p in planillas:
            fecha = (p.get("fecha_carga") or "")[:10]
            rows.append([
                fecha,
                Paragraph((p.get("nombre_archivo") or "-"), s["cell"]),
                str(len(p.get("filas") or [])),
                _fmt_ars(p.get("subtotal_ok") or 0),
                _fmt_ars(p.get("subtotal_pendiente") or 0),
            ])
        block.append(_tabla(
            ["Fecha", "Archivo", "Filas", "Conciliado", "Pendiente"],
            rows,
            [22 * mm, 68 * mm, 14 * mm, 32 * mm, 32 * mm],
            aligns={2: "CENTER"},
            money_cols=[3, 4],
            color_cols={3: _GREEN, 4: _RED},
        ))
        story.append(KeepTogether(block))

    # Cheques
    cheques = data.get("cheques") or []
    if cheques:
        block = _section(f"Cheques ({len(cheques)})")
        rows = []
        for c in cheques:
            rows.append([
                c.get("numero") or "-",
                Paragraph((c.get("banco_origen") or "-"), s["cell"]),
                (c.get("fecha_emision") or "-")[:10],
                (c.get("fecha_deposito") or "-")[:10],
                _fmt_ars(c.get("monto") or 0),
                (c.get("estado") or "").upper(),
            ])
        block.append(_tabla(
            ["Número", "Banco", "Emisión", "Depósito", "Monto", "Estado"],
            rows,
            [24 * mm, 32 * mm, 22 * mm, 22 * mm, 30 * mm, 22 * mm],
            aligns={5: "CENTER"},
            money_cols=[4],
        ))
        story.append(KeepTogether(block))

    # Pagos
    pagos = data.get("pagos") or []
    if pagos:
        block = _section(f"Pagos al cliente ({len(pagos)})")
        rows = []
        for p in pagos:
            rows.append([
                (p.get("fecha") or "-")[:10],
                Paragraph((p.get("concepto") or "-"), s["cell"]),
                p.get("medio") or "-",
                _fmt_ars(p.get("monto") or 0),
            ])
        block.append(_tabla(
            ["Fecha", "Concepto", "Medio", "Monto"],
            rows,
            [22 * mm, 88 * mm, 28 * mm, 32 * mm],
            money_cols=[3],
        ))
        story.append(KeepTogether(block))

    if not planillas and not cheques and not pagos:
        story.append(Spacer(1, 18))
        story.append(_empty_note("Sin movimientos en el período seleccionado."))

    deco = _page_decorator(generado_por)
    doc.build(story, onFirstPage=deco, onLaterPages=deco)
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
        leftMargin=_ML * mm, rightMargin=_MR * mm,
        topMargin=_MT * mm, bottomMargin=_MB * mm,
        title=f"Cierre mensual {MESES_ES[mes]} {anio}",
        author=generado_por,
    )

    pa = data.get("periodo_actual") or {}
    rango = pa.get("rango") or {}
    story: list = []

    # Encabezado
    story.append(_header_band(
        f"Cierre mensual · {MESES_ES[mes]} {anio}",
        "Organización" if org_nombre else "Período",
        org_nombre or f"{rango.get('desde', '')} a {rango.get('hasta', '')}",
    ))
    if org_nombre and (rango.get("desde") or rango.get("hasta")):
        story.append(Paragraph(
            f"Período: {rango.get('desde', '')} a {rango.get('hasta', '')}",
            s["subtitle"],
        ))

    conciliado = (pa.get("conciliado") or {}).get("total") or 0
    pendiente = (pa.get("pendiente") or {}).get("total") or 0
    tasa = pa.get("tasa_conciliacion_pct") or 0
    movs = (pa.get("movimientos_banco") or {}).get("cantidad") or 0

    story.append(Spacer(1, 6))
    story.append(_kpi_cards([
        ("Conciliado", _fmt_ars(conciliado), _GREEN),
        ("Pendiente", _fmt_ars(pendiente), _RED),
        ("Tasa conciliación", f"{tasa:.1f}%", _BRAND),
        ("Movimientos banco", str(movs), None),
    ]))

    pagos_total = (pa.get("pagos") or {}).get("total") or 0
    gastos_total = (pa.get("gastos") or {}).get("total") or 0
    cheques_count = (pa.get("cheques_cargados") or {}).get("cantidad") or 0
    neto = pagos_total - gastos_total

    story.append(Spacer(1, 8))
    story.append(_kpi_cards([
        ("Cheques cargados", str(cheques_count), None),
        ("Pagos", _fmt_ars(pagos_total), None),
        ("Gastos", _fmt_ars(gastos_total), None),
        ("Diferencia neta", _fmt_ars(neto), _GREEN if neto >= 0 else _RED),
    ]))

    # Top clientes
    top = data.get("top_clientes") or []
    if top:
        block = _section(f"Top {len(top)} clientes del mes")
        rows = []
        for i, c in enumerate(top, 1):
            rows.append([
                str(i),
                Paragraph((c.get("nombre") or "-"), s["cell"]),
                _fmt_ars(c.get("total") or 0),
            ])
        block.append(_tabla(
            ["#", "Cliente", "Conciliado"],
            rows,
            [12 * mm, 118 * mm, 40 * mm],
            aligns={0: "CENTER"},
            money_cols=[2],
            color_cols={2: _GREEN},
            font_size=9,
        ))
        story.append(KeepTogether(block))

    # Cheques en cartera
    ch_resumen = ((data.get("cheques") or {}).get("resumen") or {})
    if ch_resumen:
        block = _section("Cheques en cartera")
        rows = []
        for estado in ("pendiente", "acreditado", "rechazado"):
            info = ch_resumen.get(estado) or {}
            rows.append([
                estado.capitalize(),
                str(info.get("cantidad") or 0),
                _fmt_ars(info.get("total") or 0),
            ])
        block.append(_tabla(
            ["Estado", "Cantidad", "Monto"],
            rows,
            [60 * mm, 40 * mm, 70 * mm],
            aligns={1: "CENTER"},
            money_cols=[2],
            font_size=9,
        ))
        story.append(KeepTogether(block))

    # Próximos a vencer
    proximos = (data.get("cheques") or {}).get("proximos_a_vencer") or []
    if proximos:
        block = _section(f"Cheques próximos a vencer ({len(proximos)})")
        rows = []
        for c in proximos:
            who = c.get("cliente_nombre") or c.get("titular") or "-"
            rows.append([
                c.get("numero") or "-",
                Paragraph(who, s["cell"]),
                (c.get("fecha_deposito") or "-")[:10],
                str(c.get("dias_para_vencer") if c.get("dias_para_vencer") is not None else "-"),
                _fmt_ars(c.get("monto") or 0),
            ])
        block.append(_tabla(
            ["Número", "Cliente / Titular", "Depósito", "Días", "Monto"],
            rows,
            [26 * mm, 60 * mm, 24 * mm, 18 * mm, 42 * mm],
            aligns={3: "CENTER"},
            money_cols=[4],
        ))
        story.append(KeepTogether(block))

    deco = _page_decorator(generado_por)
    doc.build(story, onFirstPage=deco, onLaterPages=deco)
    return buf.getvalue()
