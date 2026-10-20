"""Casos difíciles del lector de extractos PDF (regresiones de la revisión adversaria).

Cada PDF se dibuja texto por texto en coordenadas fijas (como los arman los
bancos): cuadros al pie de la tabla, pies legales con importes, filas de dos
renglones, cuadros de resumen con dos rótulos por renglón, transporte entre
hojas con saldo diario, descripciones que se pasan de su columna y membretes
contra descripciones que nombran otros bancos. La IA nunca se llama.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal as D

import pytest
from PIL import Image, ImageDraw
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from app.services.extracto_pdf import formatear_pesos, leer_extracto_pdf
from app.services.extracto_pdf import ia as ia_mod

HOY = date(2026, 10, 16)


@pytest.fixture(autouse=True)
def _sin_ia(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    def _prohibido(mime, contenido):  # pragma: no cover - si se llama, el test falla
        raise AssertionError("No se debía llamar a la IA")

    monkeypatch.setattr(ia_mod, "lector_ia", _prohibido)


def ar(v: D) -> str:
    return f"{abs(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


@dataclass
class T:
    """Un texto en la página: x, y, texto, alineación ("izq" | "der")."""
    x: float
    y: float
    texto: str
    alin: str = "izq"
    size: float = 8
    font: str = "Helvetica"


def pdf(paginas: list[list[T]]) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    for textos in paginas:
        for t in textos:
            c.setFont(t.font, t.size)
            (c.drawRightString if t.alin == "der" else c.drawString)(t.x, t.y, t.texto)
        c.showPage()
    c.save()
    return buf.getvalue()


@dataclass
class Mov:
    fecha: date
    descripcion: str
    monto: D
    saldo: D = D("0")
    extra: list[str] = field(default_factory=list)


def con_saldos(saldo_inicial: D, items: list[tuple]) -> list[Mov]:
    saldo, out = saldo_inicial, []
    for it in items:
        saldo += it[2]
        out.append(Mov(it[0], it[1], it[2], saldo, list(it[3]) if len(it) > 3 else []))
    return out


def encabezado(y: float, desc: str = "Descripción") -> list[T]:
    return [T(40, y, "Fecha", font="Helvetica-Bold"), T(90, y, desc, font="Helvetica-Bold"),
            T(420, y, "Débito", "der", font="Helvetica-Bold"), T(490, y, "Crédito", "der", font="Helvetica-Bold"),
            T(560, y, "Saldo", "der", font="Helvetica-Bold")]


def fila(y: float, m: Mov, *, con_saldo: bool = True, fecha: bool = True) -> list[T]:
    out = [T(90, y, m.descripcion), T(420 if m.monto < 0 else 490, y, ar(m.monto), "der")]
    if fecha:
        out.append(T(40, y, m.fecha.strftime("%d/%m/%Y")))
    if con_saldo:
        out.append(T(560, y, ar(m.saldo), "der"))
    return out


def assert_movs(r: dict, esperados: list[Mov], *, con_saldo: bool = True):
    leidos = r["movimientos"]
    assert [(m["fecha"], m["monto"]) for m in leidos] == [(e.fecha, e.monto) for e in esperados]
    if con_saldo:
        assert [m["saldo"] for m in leidos] == [e.saldo for e in esperados]


SI = D("200000.00")
MOVS_BASE = con_saldos(SI, [
    (date(2026, 9, 1), "TRANSFERENCIA RECIBIDA", D("150000.00")),
    (date(2026, 9, 2), "PAGO PROVEEDOR", D("-50000.00")),
    (date(2026, 9, 30), "COMISION MANT CTA", D("-2500.00")),
])


def extracto_base(pie: list[T], *, membrete: str = "BBVA") -> bytes:
    textos = [T(40, 800, membrete, size=20, font="Helvetica-Bold"),
              T(40, 775, "Resumen de cuenta - Período 01/09/2026 al 30/09/2026")]
    y = 750
    textos += encabezado(y)
    y -= 14
    textos += [T(90, y, "SALDO ANTERIOR"), T(560, y, ar(SI), "der")]
    for m in MOVS_BASE:
        y -= 12
        textos += fila(y, m)
    return pdf([textos + pie])


# ── Importes sueltos fuera de la tabla no son movimientos ──────────────────

@pytest.mark.parametrize("hueco", [24, 6])
def test_cuadro_de_retenciones_al_pie_no_suma_movimientos(hueco):
    """Cuadro informativo de retenciones debajo de la tabla, sin renglón de saldo
    final: sus importes caen en la columna Débito pero no son movimientos, y su
    título no se pega a la descripción del último movimiento."""
    movs = con_saldos(SI, [
        (date(2026, 9, 1), "TRANSFERENCIA RECIBIDA CUIT 20-12345678-9", D("150000.00")),
        (date(2026, 9, 2), "PAGO PROVEEDOR", D("-50000.00")),
        (date(2026, 9, 10), "PERCEPCION IVA RG 2408", D("-1500.00")),
        (date(2026, 9, 30), "COMISION MANT CTA", D("-2500.00")),
    ])
    textos = [T(40, 800, "BANCO SANTANDER ARGENTINA S.A.", size=13, font="Helvetica-Bold"),
              T(40, 785, "Resumen de cuenta corriente - Período 01/09/2026 al 30/09/2026")]
    y = 760
    textos += encabezado(y)
    y -= 14
    textos += [T(90, y, "Saldo Anterior"), T(560, y, ar(SI), "der")]
    for m in movs:
        y -= 12
        textos += fila(y, m)
    y -= 12 + hueco
    textos.append(T(90, y, "Régimen de información - Retenciones y percepciones del período",
                    font="Helvetica-Bold"))
    for texto, v in [("Impuesto Ley 25.413 sobre débitos", "300,00"), ("Percepción IVA RG 2408", "1.500,00")]:
        y -= 12
        textos += [T(90, y, texto), T(420, y, v, "der")]

    r = leer_extracto_pdf(pdf([textos]), hoy=HOY)

    assert_movs(r, movs)
    assert r["movimientos"][-1]["descripcion"] == "COMISION MANT CTA"
    assert r["cuadre"]["cierra"] and r["saldo_final"] == movs[-1].saldo


def test_pie_legal_con_importe_no_es_un_movimiento():
    pie = [T(40, 60, "Los depósitos en pesos cuentan con la garantía de hasta", size=6),
           T(378, 60, "$ 25.000.000,00", size=6), T(430, 60, "(Ley 24.485)", size=6)]
    r = leer_extracto_pdf(extracto_base(pie), hoy=HOY)
    assert_movs(r, MOVS_BASE)
    assert r["cuadre"]["cierra"]


def test_debitos_y_creditos_del_periodo_son_totales():
    pie = [T(90, 300, "Débitos del período"), T(420, 300, "52.500,00", "der"),
           T(90, 288, "Créditos del período"), T(490, 288, "150.000,00", "der")]
    r = leer_extracto_pdf(extracto_base(pie), hoy=HOY)
    assert_movs(r, MOVS_BASE)
    assert r["cuadre"]["cierra"]


def test_ultimo_movimiento_sin_saldo_no_inventa_el_saldo_final():
    """Si la última fila no trae saldo y no hay saldo final impreso, el extracto
    no se da por cerrado (antes se deducía el final de los mismos importes)."""
    textos = [T(40, 800, "BBVA", size=20, font="Helvetica-Bold"),
              T(40, 775, "Resumen de cuenta - Período 01/09/2026 al 30/09/2026")]
    y = 750
    textos += encabezado(y)
    y -= 14
    textos += [T(90, y, "SALDO ANTERIOR"), T(560, y, ar(SI), "der")]
    for i, m in enumerate(MOVS_BASE):
        y -= 12
        textos += fila(y, m, con_saldo=i < len(MOVS_BASE) - 1)
    r = leer_extracto_pdf(pdf([textos]), hoy=HOY)
    assert [m["monto"] for m in r["movimientos"]] == [m.monto for m in MOVS_BASE]
    assert r["cuadre"]["saldo_final"] is None and not r["cuadre"]["cierra"]
    assert "sin_saldo_final" in {a["codigo"] for a in r["alertas"]}


# ── Formas de fila y de resumen ─────────────────────────────────────────────

def test_fila_de_dos_renglones_con_el_importe_abajo():
    movs = con_saldos(D("10000.00"), [
        (date(2026, 9, 1), "TRANSFERENCIA RECIBIDA", D("5000.00"), ["DE GOMEZ ANA CUIT 27-11111111-3"]),
        (date(2026, 9, 4), "TRANSFERENCIA ENVIADA", D("-2000.00"), ["A PEREZ JUAN CUIT 20-22222222-3"]),
        (date(2026, 9, 9), "PAGO DE SERVICIOS", D("-300.00"), ["ENERGIA NRO CLIENTE 1234567"]),
        (date(2026, 9, 20), "DEPOSITO", D("700.00"), ["CAJERO 345"]),
    ])
    textos = [T(40, 800, "HSBC BANK ARGENTINA S.A.", size=13, font="Helvetica-Bold"),
              T(40, 785, "Período del 01/09/2026 al 30/09/2026")]
    y = 760
    textos += encabezado(y)
    y -= 14
    textos += [T(90, y, "SALDO ANTERIOR"), T(560, y, ar(D("10000.00")), "der")]
    for m in movs:
        y -= 14
        textos += [T(40, y, m.fecha.strftime("%d/%m/%Y")), T(90, y, m.descripcion)]
        y -= 10
        textos += [T(90, y, m.extra[0]), T(420 if m.monto < 0 else 490, y, ar(m.monto), "der"),
                   T(560, y, ar(m.saldo), "der")]
    y -= 14
    textos += [T(90, y, "SALDO FINAL"), T(560, y, ar(movs[-1].saldo), "der")]

    r = leer_extracto_pdf(pdf([textos]), hoy=HOY)

    assert_movs(r, movs)
    assert r["movimientos"][0]["descripcion"] == "TRANSFERENCIA RECIBIDA DE GOMEZ ANA CUIT 27-11111111-3"
    assert not any(m["dudosa"] for m in r["movimientos"])
    assert r["cuadre"]["cierra"]


def test_cuadro_de_resumen_con_dos_rotulos_por_renglon():
    """"Saldo anterior $ X   Total créditos $ Y" en el mismo renglón: cada importe
    va con su rótulo (antes se tomaba el último como saldo anterior)."""
    sf = MOVS_BASE[-1].saldo
    textos = [T(40, 800, "Banco de Galicia y Buenos Aires S.A.U.", size=12, font="Helvetica-Bold"),
              T(40, 785, "Resumen de cuenta - Período 01/09/2026 al 30/09/2026"),
              T(40, 765, "Saldo anterior"), T(200, 765, f"$ {ar(SI)}", "der"),
              T(300, 765, "Total créditos"), T(480, 765, f"$ {ar(D('150000.00'))}", "der"),
              T(40, 753, "Saldo actual"), T(200, 753, f"$ {ar(sf)}", "der"),
              T(300, 753, "Total débitos"), T(480, 753, f"$ {ar(D('52500.00'))}", "der")]
    y = 720
    textos += encabezado(y)
    for m in MOVS_BASE:
        y -= 12
        textos += fila(y, m)
    r = leer_extracto_pdf(pdf([textos]), hoy=HOY)
    assert r["saldo_inicial"] == SI and r["saldo_final"] == sf
    assert not r["cuadre"]["saldo_inicial_inferido"] and not r["cuadre"]["saldo_final_inferido"]
    assert_movs(r, MOVS_BASE)
    assert r["cuadre"]["cierra"]


def test_saldo_diario_con_transporte_en_cada_hoja_no_corta_la_cuenta():
    """Saldo solo en la última fila de cada día y "SALDO ANTERIOR" (transporte)
    arriba de cada hoja: la hoja puede cortar en el medio de un día, así que la
    fila de antes del transporte no trae saldo. No es otra cuenta."""
    si = D("900000.00")
    items = []
    for dia in range(1, 9):
        for k in range(3):
            v = D("15000.00") + dia * 7 + k
            items.append((date(2026, 9, dia), f"MOVIMIENTO {dia}-{k}", v if k != 2 else -D("100.00")))
    movs = con_saldos(si, items)
    ultimo_del_dia = {m.fecha: i for i, m in enumerate(movs)}
    paginas, saldo_corrido = [], si
    hojas = [list(enumerate(movs))[i:i + 8] for i in range(0, len(movs), 8)]
    for n, hoja in enumerate(hojas, start=1):
        textos = [T(40, 810, "BANCO CREDICOOP COOPERATIVO LIMITADO", size=11, font="Helvetica-Bold"),
                  T(40, 797, "Resumen de cuenta - Período 01/09/2026 al 30/09/2026"),
                  T(40, 25, f"Hoja {n} de {len(hojas)}")]
        y = 770
        textos += encabezado(y)
        y -= 14
        textos += [T(90, y, "SALDO ANTERIOR"), T(560, y, ar(saldo_corrido), "der")]
        for i, m in hoja:
            y -= 12
            textos += fila(y, m, con_saldo=ultimo_del_dia[m.fecha] == i)
            saldo_corrido = m.saldo
        if n == len(hojas):
            y -= 12
            textos += [T(90, y, "SALDO FINAL"), T(560, y, ar(movs[-1].saldo), "der")]
        paginas.append(textos)

    r = leer_extracto_pdf(pdf(paginas), hoy=HOY)

    assert_movs(r, movs, con_saldo=False)
    assert r["cuadre"]["cierra"] and r["saldo_final"] == movs[-1].saldo
    assert "varias_cuentas" not in {a["codigo"] for a in r["alertas"]}


def test_descripcion_larga_que_se_pasa_de_columna_no_pierde_palabras():
    """La descripción invade la columna "Origen": el CUIT del final no se pierde
    (es lo que usa la conciliación para puntuar)."""
    movs = con_saldos(D("1340.00"), [
        (date(2026, 9, 1), "TRANSF RECIBIDA GOMEZ ANA CUIT 27111111113", D("1500.00")),
        (date(2026, 9, 2), "PAGO SERVICIOS", D("-200.00")),
    ])
    textos = [T(40, 800, "Banco de Galicia y Buenos Aires S.A.U.", size=12, font="Helvetica-Bold"),
              T(40, 785, "Período: 01/09/2026 al 30/09/2026")]
    y = 760
    textos += [T(40, y, "Fecha"), T(90, y, "Descripción"), T(250, y, "Origen"),
               T(420, y, "Crédito", "der"), T(490, y, "Débito", "der"), T(560, y, "Saldo", "der")]
    y -= 14
    textos += [T(90, y, "SALDO ANTERIOR"), T(560, y, ar(D("1340.00")), "der")]
    for m in movs:
        y -= 12
        textos += [T(40, y, m.fecha.strftime("%d/%m/%y")), T(90, y, m.descripcion),
                   T(490 if m.monto < 0 else 420, y, ar(m.monto), "der"), T(560, y, ar(m.saldo), "der")]
    textos += [T(250, y, "Web")]

    r = leer_extracto_pdf(pdf([textos]), hoy=HOY)

    assert r["movimientos"][0]["descripcion"] == "TRANSF RECIBIDA GOMEZ ANA CUIT 27111111113"
    assert_movs(r, movs)


# ── Banco y renglones ilegibles ─────────────────────────────────────────────

@pytest.mark.parametrize("membrete,banco", [("Banco Macro S.A.", "macro"), ("BBVA", "bbva"), ("macro", "macro")])
def test_el_membrete_gana_a_las_descripciones_que_nombran_otro_banco(membrete, banco):
    movs = con_saldos(D("50000.00"), [
        (date(2026, 9, 1 + i), "TRANSF RECIBIDA", D("1000.00") + i, ["DESDE BANCO GALICIA CBU 0070999020000012345678"])
        for i in range(6)
    ])
    textos = [T(40, 800, membrete, size=26, font="Helvetica-Bold"),
              T(40, 780, "Resumen de cuenta - Período 01/09/2026 al 30/09/2026")]
    y = 760
    textos += encabezado(y, "Concepto")
    y -= 14
    textos += [T(90, y, "SALDO ANTERIOR"), T(560, y, ar(D("50000.00")), "der")]
    for m in movs:
        y -= 11
        textos += fila(y, m)
        y -= 11
        textos.append(T(90, y, m.extra[0]))
    r = leer_extracto_pdf(pdf([textos]), hoy=HOY)
    assert r["banco_clave"] == banco
    assert_movs(r, movs)


def test_renglon_con_fecha_e_importes_ilegibles_avisa_y_no_da_por_bueno_el_cierre():
    """El último movimiento tiene los importes pegados ("424,001.024,53"): no se
    puede leer. Sin saldo final impreso, el saldo de la fila anterior cerraría;
    por eso se avisa y la lectura no cuenta como buena (se pediría la IA)."""
    textos = [T(40, 800, "BBVA", size=20, font="Helvetica-Bold"),
              T(40, 775, "Resumen de cuenta - Período 01/09/2026 al 30/09/2026")]
    y = 750
    textos += encabezado(y)
    y -= 14
    textos += [T(90, y, "SALDO ANTERIOR"), T(560, y, ar(SI), "der")]
    for m in MOVS_BASE[:2]:
        y -= 12
        textos += fila(y, m)
    y -= 12
    textos += [T(40, y, "30/09/2026"), T(90, y, "COMISION MANT CTA"), T(560, y, "2.500,00297.500,00", "der")]

    r = leer_extracto_pdf(pdf([textos]), hoy=HOY)

    assert len(r["movimientos"]) == 2
    codigos = {a["codigo"] for a in r["alertas"]}
    assert "renglones_ilegibles" in codigos and "ia_no_disponible" in codigos


# ── Columna "Débito/Crédito" con el importe sin signo en otra columna ───────
# Formato de un PDF real de "Movimientos de cuenta" de home banking (datos
# inventados): orden descendente, columna "Débito/Crédito" que dice la palabra,
# "Monto" sin signo con "$", saldo por fila, el título "Débito/Crédito" partido
# en dos renglones desde la hoja 2 y un cuadro arriba con saldos y totales.

def _dc(m: Mov) -> str:
    return "Crédito" if m.monto > 0 else "Débito"


def extracto_debito_credito(
    movs: list[Mov], *, saldo_inicial_pdf: D, saldo_final_pdf: D, por_hoja: int = 6
) -> bytes:
    desc = list(reversed(movs))                     # el más nuevo primero
    hojas = [desc[i:i + por_hoja] for i in range(0, len(desc), por_hoja)]
    paginas = []
    for n, hoja in enumerate(hojas, 1):
        textos = [T(40, 760, "Movimientos de cuenta 0000003100099999990012", size=10),
                  T(40, 740, "Período: 01/09/2026 al 30/09/2026")]
        y = 700
        if n == 1:
            textos += [T(43, y, "Moneda:"), T(287.6, y, "$", "der"),
                       T(300.5, y, "Nro de cuenta:"), T(545.3, y, "00099999990", "der")]
            y -= 19
            textos += [T(43, y, "Saldo inicial:"), T(287.6, y, "$ " + ar(saldo_inicial_pdf), "der"),
                       T(300.5, y, "Saldo actual:"), T(545.3, y, "$ " + ar(saldo_final_pdf), "der")]
            y -= 19
            textos += [T(43, y, "Saldo disponible:"), T(287.6, y, "$ " + ar(saldo_final_pdf), "der"),
                       T(300.5, y, "Total débitos:"), T(545.3, y, "$ 1.234,56", "der")]
            y -= 19
            textos += [T(43, y, "Total créditos:"), T(287.6, y, "$ 7.890,12", "der")]
            y -= 60
            textos += [T(40, y, "Fecha"), T(110, y, "Tipo de transacción"), T(287, y, "Débito/Crédito"),
                       T(426.5, y, "Monto"), T(524.9, y, "Saldo")]
        else:
            textos += [T(40, y, "Fecha"), T(110, y, "Tipo de transacción"), T(310, y, "Débito/"),
                       T(423, y, "Monto"), T(524.9, y, "Saldo"), T(310, y - 14, "Crédito")]
            y -= 14
        y -= 27
        for m in hoja:
            textos += [T(40, y, m.fecha.strftime("%d/%m/%Y")), T(110, y, m.descripcion), T(310, y, _dc(m)),
                       T(457.6, y, "$ " + ar(m.monto), "der"), T(555.3, y, "$ " + ar(m.saldo), "der")]
            y -= 16.7
        textos.append(T(555.3, 40, f"{n}/{len(hojas)}", "der"))
        paginas.append(textos)
    return pdf(paginas)


SI_DC = D("880000.00")
MOVS_DC = con_saldos(SI_DC, [
    (date(2026, 9, 1), "CRÉDITO POR TRANSFERENCIA", D("76000.00")),
    (date(2026, 9, 1), "SIRCREB", D("-7.60")),
    (date(2026, 9, 1), "Imp. Ley 25413 s/créditos", D("-456.00")),
    (date(2026, 9, 2), "Debito Transf. HB", D("-400000.00")),
    (date(2026, 9, 2), "Imp. Ley 25413 s/débitos", D("-2400.00")),
    (date(2026, 9, 2), "Debito Transf. HB", D("400000.00")),          # transferencia devuelta
    (date(2026, 9, 2), "Imp. Ley 25413 s/débitos", D("2400.00")),
    (date(2026, 9, 3), "CRÉDITO POR CREDIN", D("123456.78")),
    (date(2026, 9, 3), "SIRCREB", D("-12.35")),
    (date(2026, 9, 3), "Imp. Ley 25413 s/créditos", D("-740.74")),
    (date(2026, 9, 4), "Debito Transf. HB", D("-250000.00")),
    (date(2026, 9, 4), "Imp. Ley 25413 s/débitos", D("-1500.00")),
    (date(2026, 9, 4), "CRÉDITO POR TRANSFERENCIA", D("19100.00")),
])


def test_columna_debito_credito_da_el_signo_del_monto():
    """El signo sale de la columna "Débito/Crédito" (también en las hojas donde
    el título viene partido en dos renglones), no se deduce del saldo, y la
    palabra no se pega a la descripción. La transferencia devuelta dice "Debito
    Transf. HB" en la descripción pero es un crédito."""
    contenido = extracto_debito_credito(MOVS_DC, saldo_inicial_pdf=SI_DC, saldo_final_pdf=MOVS_DC[-1].saldo)

    r = leer_extracto_pdf(contenido, hoy=HOY)

    assert r["orden"] == "desc"
    assert_movs(r, list(reversed(MOVS_DC)))
    assert [m["descripcion"] for m in r["movimientos"]] == [m.descripcion for m in reversed(MOVS_DC)]
    assert r["cuadre"]["cierra"] and r["saldo_inicial"] == SI_DC
    codigos = {a["codigo"] for a in r["alertas"]}
    assert "signo_deducido" not in codigos and "filas_dudosas" not in codigos
    layout = r["aprendizaje"]["layout"]
    assert "signo" in [c["campo"] for c in layout["columnas"]]

    # El formato aprendido (con la columna del signo) lee el mes siguiente.
    molde = {"id": 7, "banco_clave": r["aprendizaje"]["banco_clave"], "firma": r["aprendizaje"]["firma"],
             "layout": layout}
    r2 = leer_extracto_pdf(contenido, moldes=[molde], hoy=HOY)
    assert r2["metodo"] == "molde" and r2["molde_id"] == 7
    assert_movs(r2, list(reversed(MOVS_DC)))


def test_saldos_del_cuadro_que_no_coinciden_con_los_movimientos():
    """El cuadro de arriba trae un saldo inicial y un saldo actual que no son los
    de los movimientos (pasó con un PDF real). Los movimientos se leen bien,
    con el signo del PDF (el más viejo no se da vuelta por el saldo inicial
    equivocado), no se da por cerrado, y el aviso dice qué saldo no coincide."""
    contenido = extracto_debito_credito(MOVS_DC, saldo_inicial_pdf=D("1000000.00"), saldo_final_pdf=SI_DC)

    r = leer_extracto_pdf(contenido, hoy=HOY)

    assert_movs(r, list(reversed(MOVS_DC)))
    assert not r["cuadre"]["cierra"]
    aviso = next(a["mensaje"] for a in r["alertas"] if a["codigo"] == "no_cierra")
    assert aviso.startswith("Los movimientos cierran entre sí")
    assert "saldo inicial que figura en el PDF ($ 1.000.000,00)" in aviso and "($ 880.000,00)" in aviso
    assert "saldo final que figura en el PDF ($ 880.000,00)" in aviso
    assert f"({formatear_pesos(MOVS_DC[-1].saldo)})" in aviso and "esos saldos" in aviso


def test_marca_d_o_c_al_lado_del_importe_sin_saldo_por_fila():
    """"1.500,00 D" en la columna Importe, sin saldo por fila: el signo sale de la
    marca (antes quedaba "Signo sin confirmar") y cierra con el saldo anterior
    y el final del PDF."""
    si = D("10000.00")
    movs = con_saldos(si, [
        (date(2026, 9, 1), "DEPOSITO EFECTIVO", D("2000.00")),
        (date(2026, 9, 2), "PAGO TARJETA", D("-1500.00")),
        (date(2026, 9, 5), "COMISION", D("-120.50")),
    ])
    textos = [T(40, 800, "Resumen de cuenta - Período 01/09/2026 al 30/09/2026"),
              T(40, 770, "Fecha", font="Helvetica-Bold"), T(110, 770, "Concepto", font="Helvetica-Bold"),
              T(470, 770, "Importe", "der", font="Helvetica-Bold"),
              T(110, 756, "SALDO ANTERIOR"), T(470, 756, ar(si), "der")]
    y = 756
    for m in movs:
        y -= 12
        textos += [T(40, y, m.fecha.strftime("%d/%m/%Y")), T(110, y, m.descripcion),
                   T(470, y, ar(m.monto), "der"), T(474, y, "C" if m.monto > 0 else "D")]
    y -= 14
    textos += [T(110, y, "SALDO FINAL"), T(470, y, ar(movs[-1].saldo), "der")]

    r = leer_extracto_pdf(pdf([textos]), hoy=HOY)

    assert_movs(r, movs, con_saldo=False)
    assert r["cuadre"]["cierra"]
    assert not any(m["dudosa"] for m in r["movimientos"])
    assert [m["descripcion"] for m in r["movimientos"]] == [m.descripcion for m in movs]


def test_columna_debito_credito_con_importes_con_signo_sigue_siendo_el_importe():
    """"Débito/Crédito" como única columna de importes (con signo): es el importe,
    como antes. Y si hay otra columna de importes ("Importe origen") pero los
    números están debajo de "Débito/Crédito", esa es la del importe."""
    si = D("5000.00")
    movs = con_saldos(si, [
        (date(2026, 9, 1), "TRANSFERENCIA RECIBIDA", D("1000.00")),
        (date(2026, 9, 3), "PAGO SERVICIO", D("-250.00")),
        (date(2026, 9, 8), "COMPRA DEBITO", D("-99.90")),
    ])

    def armar(con_origen: bool) -> bytes:
        enc = [T(40, 770, "Fecha"), T(110, 770, "Concepto"), T(430, 770, "Débito/Crédito", "der"),
               T(560, 770, "Saldo", "der")]
        if con_origen:
            enc.append(T(330, 770, "Importe origen", "der"))
        textos = [T(40, 800, "Resumen de cuenta - Período 01/09/2026 al 30/09/2026"), *enc,
                  T(110, 756, "SALDO ANTERIOR"), T(560, 756, ar(si), "der")]
        y = 756
        for m in movs:
            y -= 12
            signo = "-" if m.monto < 0 else ""
            textos += [T(40, y, m.fecha.strftime("%d/%m/%Y")), T(110, y, m.descripcion),
                       T(430, y, signo + ar(m.monto), "der"), T(560, y, ar(m.saldo), "der")]
            if con_origen:
                textos.append(T(330, y, "USD " + ar(m.monto / 1000), "der"))
        return pdf([textos])

    for con_origen in (False, True):
        r = leer_extracto_pdf(armar(con_origen), hoy=HOY)
        assert_movs(r, movs)
        assert r["cuadre"]["cierra"], con_origen


# ── Lo que la columna del signo no tiene que tocar (revisión adversaria) ────

def _sin_titulos(movs: list[Mov], si: D, *, con_signo: bool = False, canal: dict | None = None) -> bytes:
    """Tabla sin títulos reconocibles (lectura estructural): Fch | Texto libre |
    [canal] | Valor $ | Acum."""
    textos = [T(40, 800, "Cooperativa de Crédito Ejemplo", size=12),
              T(40, 785, "Período: 01/09/2026 al 30/09/2026"),
              T(40, 760, "Fch"), T(100, 760, "Texto libre"), T(450, 760, "Valor $", "der"), T(550, 760, "Acum.", "der"),
              T(100, 746, "SALDO ANTERIOR"), T(550, 746, ar(si), "der")]
    y = 746
    for i, m in enumerate(movs):
        y -= 12
        valor = ("-" if con_signo and m.monto < 0 else "") + ar(m.monto)
        textos += [T(40, y, m.fecha.strftime("%d/%m/%Y")), T(100, y, m.descripcion),
                   T(450, y, valor, "der"), T(550, y, ar(m.saldo), "der")]
        if canal:
            textos.append(T(370, y, canal[i]))
    return pdf([textos])


MOVS_DESC_DC = con_saldos(D("50000.00"), [
    (date(2026, 9, 1), "Compra con tarjeta de debito", D("-1500.00")),
    (date(2026, 9, 2), "Compra con tarjeta de debito", D("-2300.50")),
    (date(2026, 9, 3), "Transferencia recibida", D("50000.00")),
    (date(2026, 9, 4), "Compra con tarjeta de debito", D("-800.00")),
    (date(2026, 9, 5), "Devolucion compra tarjeta de debito", D("1500.00")),
    (date(2026, 9, 6), "Compra con tarjeta de debito", D("-950.25")),
    (date(2026, 9, 7), "PAGO TARJETA CREDITO", D("-150.00")),
    (date(2026, 9, 8), "Compra con tarjeta de debito", D("-430.00")),
])


@pytest.mark.parametrize("con_signo", [False, True])
def test_sin_titulos_la_palabra_debito_o_credito_de_la_descripcion_no_es_el_signo(con_signo):
    """Sin títulos, muchas descripciones terminan en "debito"/"credito": siguen
    enteras y el signo sale del saldo (o del "-" impreso), no de esa palabra."""
    r = leer_extracto_pdf(_sin_titulos(MOVS_DESC_DC, D("50000.00"), con_signo=con_signo), hoy=HOY)

    assert_movs(r, MOVS_DESC_DC)
    assert [m["descripcion"] for m in r["movimientos"]] == [m.descripcion for m in MOVS_DESC_DC]
    assert r["cuadre"]["cierra"]


def test_sin_titulos_una_columna_de_letras_no_es_el_signo():
    """Una columna de canal (C caja, D depósito, I internet) antes del importe
    sin signo: el signo sigue saliendo del saldo."""
    movs = con_saldos(D("8000.00"), [
        (date(2026, 9, 1), "DEPOSITO", D("1200.00")),
        (date(2026, 9, 2), "IMPUESTO", D("-60.00")),
        (date(2026, 9, 3), "PAGO SERVICIO", D("-300.00")),
        (date(2026, 9, 4), "TRANSFERENCIA", D("900.00")),
        (date(2026, 9, 7), "COMISION", D("-45.00")),
    ])
    r = leer_extracto_pdf(_sin_titulos(movs, D("8000.00"), canal=dict(enumerate("DCCID"))), hoy=HOY)

    assert_movs(r, movs)
    assert r["cuadre"]["cierra"]


def test_descripciones_que_terminan_en_credito_bajo_el_titulo_debito():
    """Cuenta recaudadora: casi todo créditos, con descripciones largas que llegan
    hasta debajo del título "Débito" y terminan en "CREDITO". La columna Débito no
    pasa a ser la del signo: el débito que hay no se pierde y la palabra queda en
    la descripción."""
    items = [(date(2026, 9, 1 + i), f"TRANSFERENCIA RECIBIDA CLIENTE {i:02d} CREDITO", D("1000.00") + i)
             for i in range(10)]
    items.insert(5, (date(2026, 9, 6), "COMISION", D("-150.00")))
    movs = con_saldos(D("20000.00"), items)
    x_deb = 90 + stringWidth(items[0][1], "Helvetica", 8) + 2       # termina justo después de "CREDITO"
    textos = [T(40, 800, "Resumen de cuenta - Período 01/09/2026 al 30/09/2026"),
              T(40, 770, "Fecha"), T(90, 770, "Descripción"), T(x_deb, 770, "Débito", "der"),
              T(470, 770, "Crédito", "der"), T(560, 770, "Saldo", "der"),
              T(90, 756, "SALDO ANTERIOR"), T(560, 756, ar(D("20000.00")), "der")]
    y = 756
    for m in movs:
        y -= 12
        textos += [T(40, y, m.fecha.strftime("%d/%m/%Y")), T(90, y, m.descripcion),
                   T(x_deb if m.monto < 0 else 470, y, ar(m.monto), "der"), T(560, y, ar(m.saldo), "der")]

    r = leer_extracto_pdf(pdf([textos]), hoy=HOY)

    assert_movs(r, movs)
    assert [m["descripcion"] for m in r["movimientos"]] == [m.descripcion for m in movs]
    assert r["cuadre"]["cierra"]


def _tabla_signo(movs: list[Mov], si_pdf: D, *, titulo: str = "Débito/Crédito", marca=_dc,
                 pesos_suelto: bool = False, saldo_en: set | None = None) -> bytes:
    """Fecha | Concepto | <titulo> | Monto | Saldo, orden ascendente, con
    "Saldo inicial" arriba. `saldo_en`: filas que traen saldo (None = todas)."""
    textos = [T(40, 800, "Movimientos de cuenta", size=10), T(40, 785, "Período: 01/09/2026 al 30/09/2026"),
              T(43, 760, "Saldo inicial:"), T(287.6, 760, "$ " + ar(si_pdf), "der"),
              T(40, 740, "Fecha"), T(110, 740, "Concepto"), T(287, 740, titulo), T(426.5, 740, "Monto"),
              T(524.9, 740, "Saldo")]
    y = 740
    for i, m in enumerate(movs):
        y -= 16.7
        textos += [T(40, y, m.fecha.strftime("%d/%m/%Y")), T(110, y, m.descripcion)]
        if marca(m):
            textos.append(T(310, y, marca(m)))
        con_saldo = saldo_en is None or i in saldo_en
        if pesos_suelto:
            textos += [T(400, y, "$"), T(457.6, y, ar(m.monto), "der")]
            if con_saldo:
                textos += [T(500, y, "$"), T(555.3, y, ar(m.saldo), "der")]
        else:
            textos.append(T(457.6, y, "$ " + ar(m.monto), "der"))
            if con_saldo:
                textos.append(T(555.3, y, "$ " + ar(m.saldo), "der"))
    return pdf([textos])


def test_columna_de_signo_con_el_pesos_suelto_y_el_saldo_inicial_equivocado():
    """El "$" va como palabra suelta y el saldo inicial impreso está mal: gana la
    lectura con el signo de la columna, no una que lo deduce del saldo equivocado
    y por eso da una diferencia más chica."""
    r = leer_extracto_pdf(_tabla_signo(MOVS_DC, D("1000000.00"), pesos_suelto=True), hoy=HOY)

    assert_movs(r, MOVS_DC)
    aviso = next(a["mensaje"] for a in r["alertas"] if a["codigo"] == "no_cierra")
    assert aviso.startswith("Los movimientos cierran entre sí") and "borrá ese saldo y se usa el" in aviso


@pytest.mark.parametrize("titulo,marca", [
    ("D/C", lambda m: "C" if m.monto > 0 else "D"),
    ("Tipo", _dc),
])
def test_columna_de_signo_con_otro_titulo(titulo, marca):
    """La columna del signo titulada "D/C" (con letras) o con un título que no
    dice nada ("Tipo", con las palabras enteras)."""
    r = leer_extracto_pdf(_tabla_signo(MOVS_DC, SI_DC, titulo=titulo, marca=marca), hoy=HOY)

    assert_movs(r, MOVS_DC)
    assert [m["descripcion"] for m in r["movimientos"]] == [m.descripcion for m in MOVS_DC]
    assert r["cuadre"]["cierra"]
    assert "signo_deducido" not in {a["codigo"] for a in r["alertas"]}


def test_el_menos_impreso_manda_sobre_la_palabra_de_la_columna():
    """Si el importe trae un "-" impreso, ese es el signo aunque la columna diga
    "Crédito"; la fila queda para revisar."""
    movs = con_saldos(D("10000.00"), [
        (date(2026, 9, 1), "DEPOSITO", D("500.00")),
        (date(2026, 9, 2), "AJUSTE", D("-400.00")),
        (date(2026, 9, 3), "COMISION", D("-12.00")),
    ])
    textos = [T(40, 800, "Movimientos de cuenta", size=10), T(40, 785, "Período: 01/09/2026 al 30/09/2026"),
              T(43, 760, "Saldo inicial:"), T(287.6, 760, "$ " + ar(D("10000.00")), "der"),
              T(40, 740, "Fecha"), T(110, 740, "Concepto"), T(287, 740, "Débito/Crédito"), T(426.5, 740, "Monto"),
              T(524.9, 740, "Saldo")]
    y = 740
    for m in movs:
        y -= 16.7
        palabra, monto = ("Crédito", "-$ " + ar(m.monto)) if m.descripcion == "AJUSTE" else (_dc(m), "$ " + ar(m.monto))
        textos += [T(40, y, m.fecha.strftime("%d/%m/%Y")), T(110, y, m.descripcion), T(310, y, palabra),
                   T(457.6, y, monto, "der"), T(555.3, y, "$ " + ar(m.saldo), "der")]

    r = leer_extracto_pdf(pdf([textos]), hoy=HOY)

    assert_movs(r, movs)
    assert r["cuadre"]["cierra"]
    assert [m["dudosa"] for m in r["movimientos"]] == [False, True, False]


def test_fila_sin_marca_usa_los_signos_que_el_pdf_ya_dice():
    """Saldo solo al final de cada día y una fila sin la palabra: su signo sale
    del saldo del día descontando las filas que sí la traen (+100 −30 −70 = 0)."""
    movs = con_saldos(D("10000.00"), [
        (date(2026, 9, 1), "DEPOSITO", D("500.00")),
        (date(2026, 9, 2), "TRANSFERENCIA RECIBIDA", D("100.00")),
        (date(2026, 9, 2), "IMPUESTO LEY 25413", D("-30.00")),
        (date(2026, 9, 2), "PAGO PROVEEDOR", D("-70.00")),
        (date(2026, 9, 3), "COMISION", D("-12.00")),
    ])
    ultimo_del_dia = {i for i, m in enumerate(movs) if i == len(movs) - 1 or movs[i + 1].fecha != m.fecha}

    r = leer_extracto_pdf(_tabla_signo(movs, D("10000.00"), marca=lambda m: "" if m.monto == D("-30.00") else _dc(m),
                                       saldo_en=ultimo_del_dia), hoy=HOY)

    assert_movs(r, movs, con_saldo=False)
    assert r["cuadre"]["cierra"]
    assert not any(m["dudosa"] for m in r["movimientos"])


def test_un_solo_movimiento_bajo_el_titulo_partido():
    """Una sola fila debajo de "Débito/" + "Crédito" (partido en dos renglones):
    también es la columna del signo."""
    movs = con_saldos(D("5000.00"), [(date(2026, 9, 3), "PAGO SERVICIO", D("-1000.00"))])
    textos = [T(40, 800, "Movimientos de cuenta", size=10), T(40, 785, "Período: 01/09/2026 al 30/09/2026"),
              T(40, 740, "Fecha"), T(110, 740, "Tipo de transacción"), T(310, 740, "Débito/"), T(423, 740, "Monto"),
              T(524.9, 740, "Saldo"), T(310, 726, "Crédito")]
    textos += [T(40, 700, "03/09/2026"), T(110, 700, "PAGO SERVICIO"), T(310, 700, "Débito"),
               T(457.6, 700, "$ " + ar(D("1000.00")), "der"), T(555.3, 700, "$ " + ar(movs[0].saldo), "der")]

    r = leer_extracto_pdf(pdf([textos]), hoy=HOY)

    assert_movs(r, movs)


def test_descripcion_que_llega_a_la_columna_del_signo_con_el_formato_aprendido():
    """Con el formato aprendido de un mes, el mes siguiente trae descripciones más
    largas que se meten en la columna del signo: no pierden palabras y la que
    termina en "DEBITO" no da vuelta un crédito."""
    r1 = leer_extracto_pdf(extracto_debito_credito(MOVS_DC, saldo_inicial_pdf=SI_DC,
                                                   saldo_final_pdf=MOVS_DC[-1].saldo), hoy=HOY)
    molde = {"id": 7, "banco_clave": r1["aprendizaje"]["banco_clave"], "firma": r1["aprendizaje"]["firma"],
             "layout": r1["aprendizaje"]["layout"]}
    si = MOVS_DC[-1].saldo
    movs = con_saldos(si, [
        (date(2026, 10, 1), "CRÉDITO POR TRANSFERENCIA", D("5000.00")),
        (date(2026, 10, 2), "PAGO SERVICIOS AGUAS Y CLOACAS SA", D("-800.00")),
        (date(2026, 10, 3), "REINTEGRO COMPRA EXTERIOR TARJ DEBITO", D("250.00")),
        (date(2026, 10, 6), "Imp. Ley 25413 s/débitos", D("-4.80")),
    ])

    r = leer_extracto_pdf(extracto_debito_credito(movs, saldo_inicial_pdf=si, saldo_final_pdf=movs[-1].saldo),
                          moldes=[molde], hoy=HOY)

    assert r["metodo"] == "molde"
    assert_movs(r, list(reversed(movs)))
    assert [m["descripcion"] for m in r["movimientos"]] == [m.descripcion for m in reversed(movs)]


# El aviso "los movimientos cierran entre sí" solo cuando de verdad lo sabe.

def test_aviso_de_saldos_no_culpa_al_saldo_final_si_un_renglon_no_se_leyo():
    """El último movimiento no se pudo leer (importes pegados) y el saldo final
    impreso está bien: el aviso sigue siendo la diferencia, no "borrá ese saldo"."""
    textos = [T(40, 800, "BBVA", size=20, font="Helvetica-Bold"),
              T(40, 775, "Resumen de cuenta - Período 01/09/2026 al 30/09/2026"), *encabezado(750),
              T(90, 736, "SALDO ANTERIOR"), T(560, 736, ar(SI), "der")]
    y = 736
    for m in MOVS_BASE[:2]:
        y -= 12
        textos += fila(y, m)
    y -= 12
    textos += [T(40, y, "30/09/2026"), T(90, y, "COMISION MANT CTA"), T(560, y, "2.500,00297.500,00", "der")]
    y -= 14
    textos += [T(90, y, "SALDO FINAL"), T(560, y, ar(MOVS_BASE[-1].saldo), "der")]

    r = leer_extracto_pdf(pdf([textos]), hoy=HOY)

    aviso = next(a["mensaje"] for a in r["alertas"] if a["codigo"] == "no_cierra")
    assert aviso == "El saldo no cierra: hay una diferencia de -$ 2.500,00."


@pytest.mark.parametrize("formato", ["sin_signo", "saldo_por_dia"])
def test_aviso_de_saldos_no_culpa_al_saldo_inicial_si_la_primera_fila_no_se_controla(formato):
    """Saldo inicial impreso equivocado, pero sin forma de saber que la primera
    fila está bien: con el signo deducido del saldo (se eligió para llegar a ese
    saldo) o con la primera fila sin saldo propio. El aviso es la diferencia."""
    movs = con_saldos(D("880000.00"), [
        (date(2026, 9, 1), "CRÉDITO POR TRANSFERENCIA", D("76000.00")),
        (date(2026, 9, 1), "SIRCREB", D("-7.60")),
        (date(2026, 9, 2), "Debito Transf. HB", D("-400000.00")),
        (date(2026, 9, 3), "CRÉDITO POR CREDIN", D("123456.78")),
    ])
    if formato == "sin_signo":
        contenido = _tabla_signo(movs, D("1000000.00"), titulo="Origen", marca=lambda m: "")
    else:
        contenido = _tabla_signo(movs, D("1000000.00"), saldo_en={1, 2, 3})

    r = leer_extracto_pdf(contenido, hoy=HOY)

    aviso = next(a["mensaje"] for a in r["alertas"] if a["codigo"] == "no_cierra")
    assert aviso.startswith("El saldo no cierra: hay una diferencia de")


# ═══════════════════════════════════════════════════════════════════════════
# Columna del signo en formatos de otros bancos (revisión con un PDF real de
# home banking y formatos parecidos). Datos inventados.
# ═══════════════════════════════════════════════════════════════════════════

SIGNO_IMPRESO = "El signo impreso no coincide con la columna"
SIGNO_SUPUESTO = "Signo sin confirmar"


def _signo_con_menos(movs: list[Mov], si_pdf, *, menos: dict, sin_palabra: tuple = ()) -> bytes:
    """Fecha | Concepto | Débito/Crédito | Monto | Saldo (como `_tabla_signo`), con
    saldo en cada fila. Las filas de `menos` (descripción -> palabra) traen el
    importe impreso "-$ ..." y esa palabra; las de `sin_palabra` no traen nada en
    la columna del signo. Con `si_pdf=None` no hay renglón "Saldo inicial"."""
    textos = [T(40, 800, "Movimientos de cuenta", size=10), T(40, 785, "Período: 01/09/2026 al 30/09/2026"),
              T(40, 740, "Fecha"), T(110, 740, "Concepto"), T(287, 740, "Débito/Crédito"), T(426.5, 740, "Monto"),
              T(524.9, 740, "Saldo")]
    if si_pdf is not None:
        textos += [T(43, 760, "Saldo inicial:"), T(287.6, 760, "$ " + ar(si_pdf), "der")]
    y = 740
    for m in movs:
        y -= 16.7
        palabra = "" if m.descripcion in sin_palabra else menos.get(m.descripcion, _dc(m))
        textos += [T(40, y, m.fecha.strftime("%d/%m/%Y")), T(110, y, m.descripcion),
                   T(457.6, y, ("-$ " if m.descripcion in menos else "$ ") + ar(m.monto), "der"),
                   T(555.3, y, "$ " + ar(m.saldo), "der")]
        if palabra:
            textos.append(T(310, y, palabra))
    return pdf([textos])


def _motivos(r: dict) -> dict:
    return {m["descripcion"]: m["motivos"] for m in r["movimientos"]}


# ── El "-" impreso contra la palabra no es un signo supuesto ────────────────

@pytest.mark.parametrize("si_pdf,items", [
    (D("12500.00"), [(date(2026, 9, 4), "PAGO PROVEEDOR", D("-3000.00")),
                     (date(2026, 9, 5), "TRANSFERENCIA RECIBIDA", D("2000.00"))]),
    (D("12000.00"), [(date(2026, 9, 4), "PAGO PROVEEDOR", D("-3000.00")),
                     (date(2026, 9, 5), "TRANSFERENCIA ENVIADA", D("-1500.00")),
                     (date(2026, 9, 8), "IMPUESTO LEY 25413", D("-27.00"))]),
])
def test_menos_contra_la_palabra_y_saldo_inicial_equivocado_gana_la_columna_del_signo(si_pdf, items):
    """Columna "Débito/Crédito" con el AJUSTE impreso "-$ 400,00" junto a la palabra
    "Crédito", y el "Saldo inicial" del cuadro de arriba de otra fecha (el real es
    10.000): nada cierra. Gana la lectura con la columna del signo, que lee bien
    todos los importes: los débitos no pasan a créditos, la palabra no se pega a
    la descripción, y el AJUSTE queda marcado porque el signo impreso no coincide
    con la columna, no como un signo supuesto."""
    movs = con_saldos(D("10000.00"), [(date(2026, 9, 1), "DEPOSITO", D("500.00")),
                                      (date(2026, 9, 2), "AJUSTE", D("-400.00")),
                                      (date(2026, 9, 3), "COMISION", D("-12.00")), *items])

    r = leer_extracto_pdf(_signo_con_menos(movs, si_pdf, menos={"AJUSTE": "Crédito"}), hoy=HOY)

    assert_movs(r, movs)
    assert [m["descripcion"] for m in r["movimientos"]] == [m.descripcion for m in movs]
    assert not r["cuadre"]["cierra"] and r["cuadre"]["diferencia"] == D("10000.00") - si_pdf
    assert "no_cierra" in {a["codigo"] for a in r["alertas"]}
    assert _motivos(r)["AJUSTE"] == [SIGNO_IMPRESO]
    assert "signo" in [c["campo"] for c in r["aprendizaje"]["layout"]["columnas"]]


# ── Una fila sin la palabra saca el signo del saldo aunque haya un "-" ──────

@pytest.mark.parametrize("palabra_ajuste", ["Débito", "Crédito"])
def test_fila_sin_palabra_con_un_menos_impreso_en_otra_fila_sale_del_saldo(palabra_ajuste):
    """Columna "Débito/Crédito" y saldo en cada fila. El AJUSTE trae el importe
    impreso "-$ 400,00" (con "Débito", o con "Crédito" en contra) y el IMPUESTO
    LEY 25413 no trae la palabra. Ese único "-" no convierte en créditos las
    filas sin palabra: el impuesto sale del saldo (−30), sin marca, y cierra."""
    movs = con_saldos(D("10000.00"), [
        (date(2026, 9, 1), "DEPOSITO", D("500.00")),
        (date(2026, 9, 2), "AJUSTE", D("-400.00")),
        (date(2026, 9, 3), "IMPUESTO LEY 25413", D("-30.00")),
        (date(2026, 9, 4), "COMISION", D("-12.00")),
        (date(2026, 9, 5), "TRANSFERENCIA RECIBIDA", D("2000.00")),
    ])
    contenido = _signo_con_menos(movs, D("10000.00"), menos={"AJUSTE": palabra_ajuste},
                                 sin_palabra=("IMPUESTO LEY 25413",))

    r = leer_extracto_pdf(contenido, hoy=HOY)

    assert_movs(r, movs)
    assert [m["descripcion"] for m in r["movimientos"]] == [m.descripcion for m in movs]
    assert r["cuadre"]["cierra"]
    assert _motivos(r)["IMPUESTO LEY 25413"] == []
    assert [m["dudosa"] for m in r["movimientos"]] == [False, palabra_ajuste == "Crédito", False, False, False]


MOVS_PRIMERA_SIN_PALABRA = con_saldos(D("10000.00"), [
    (date(2026, 9, 1), "COMISION MANTENIMIENTO", D("-12.00")),
    (date(2026, 9, 2), "DEPOSITO", D("500.00")),
    (date(2026, 9, 3), "AJUSTE", D("-400.00")),
    (date(2026, 9, 4), "PAGO PROVEEDOR", D("-3000.00")),
])


@pytest.mark.parametrize("palabra_ajuste", ["Débito", "Crédito"])
def test_primera_fila_sin_palabra_sale_del_saldo_inicial_correcto(palabra_ajuste):
    """"Saldo inicial: $ 10.000,00" impreso y correcto. La primera fila (COMISION
    MANTENIMIENTO, un débito de 12) no trae la palabra y otro débito trae el "-"
    impreso. La comisión sale del saldo inicial (−12) y cierra: el aviso no le
    echa la culpa al saldo inicial bueno ni pide borrarlo."""
    contenido = _signo_con_menos(MOVS_PRIMERA_SIN_PALABRA, D("10000.00"), menos={"AJUSTE": palabra_ajuste},
                                 sin_palabra=("COMISION MANTENIMIENTO",))

    r = leer_extracto_pdf(contenido, hoy=HOY)

    assert_movs(r, MOVS_PRIMERA_SIN_PALABRA)
    assert r["cuadre"]["cierra"] and r["saldo_inicial"] == D("10000.00")
    assert _motivos(r)["COMISION MANTENIMIENTO"] == []
    assert "no_cierra" not in {a["codigo"] for a in r["alertas"]}
    assert not any("borrá" in a["mensaje"] for a in r["alertas"])


@pytest.mark.parametrize("palabra_ajuste", ["Débito", "Crédito"])
def test_primera_fila_sin_palabra_y_sin_saldo_inicial_queda_para_revisar(palabra_ajuste):
    """El mismo PDF sin renglón "Saldo inicial": el signo de la primera fila no
    se puede sacar de ningún lado. No se toma como crédito en silencio (antes
    cerraba sin ninguna marca, con un saldo inicial de 9.976): queda "Signo sin
    confirmar" y el aviso de filas para revisar lo dice; el resto sale bien."""
    contenido = _signo_con_menos(MOVS_PRIMERA_SIN_PALABRA, None, menos={"AJUSTE": palabra_ajuste},
                                 sin_palabra=("COMISION MANTENIMIENTO",))

    r = leer_extracto_pdf(contenido, hoy=HOY)

    primera = r["movimientos"][0]
    assert primera["descripcion"] == "COMISION MANTENIMIENTO" and primera["dudosa"]
    assert SIGNO_SUPUESTO in primera["motivos"]
    assert [m["monto"] for m in r["movimientos"][1:]] == [m.monto for m in MOVS_PRIMERA_SIN_PALABRA[1:]]
    assert {"signo_deducido", "filas_dudosas"} & {a["codigo"] for a in r["alertas"]}


def test_ultima_fila_sin_palabra_con_el_menos_en_contra_de_la_columna():
    """El formato del "-" que manda sobre la palabra (AJUSTE "-$ 400,00" con
    "Crédito") y además un PAGO SERVICIO de 300 con la columna del signo vacía:
    su saldo baja de 10.088 a 9.788, así que es −300 y no un crédito. Cierra, y
    la única fila para revisar es el AJUSTE, con el motivo del signo impreso."""
    movs = con_saldos(D("10000.00"), [
        (date(2026, 9, 1), "DEPOSITO", D("500.00")),
        (date(2026, 9, 2), "AJUSTE", D("-400.00")),
        (date(2026, 9, 3), "COMISION", D("-12.00")),
        (date(2026, 9, 4), "PAGO SERVICIO", D("-300.00")),
    ])
    contenido = _signo_con_menos(movs, D("10000.00"), menos={"AJUSTE": "Crédito"}, sin_palabra=("PAGO SERVICIO",))

    r = leer_extracto_pdf(contenido, hoy=HOY)

    assert_movs(r, movs)
    assert r["cuadre"]["cierra"] and r["cuadre"]["diferencia"] == D("0.00")
    assert [m["dudosa"] for m in r["movimientos"]] == [False, True, False, False]
    assert _motivos(r)["AJUSTE"] == [SIGNO_IMPRESO]


# ── Columnas con palabras de débito/crédito que no son el signo del movimiento ──

def _saldo_con_marca(movs: list[Mov], si: D, *, titulo: str, marca, importe_izq: bool = True,
                     con_signo: bool = False) -> bytes:
    """Fecha | Concepto | Importe | Saldo | <titulo>: la marca pegada al saldo dice
    si el saldo es acreedor o deudor, no el signo del movimiento."""
    def importe(y: float, texto: str) -> T:
        return T(400, y, texto) if importe_izq else T(470, y, texto, "der")
    textos = [T(40, 800, "Movimientos de la cuenta", size=12), T(40, 785, "Período: 01/09/2026 al 30/09/2026"),
              T(40, 760, "Fecha"), T(100, 760, "Concepto"), importe(760, "Importe"), T(545, 760, "Saldo", "der"),
              T(552, 760, titulo), T(100, 746, "SALDO ANTERIOR"), T(545, 746, ar(si), "der"), T(556, 746, marca(si))]
    y = 746
    for m in movs:
        y -= 12
        textos += [T(40, y, m.fecha.strftime("%d/%m/%Y")), T(100, y, m.descripcion),
                   importe(y, ("-" if con_signo and m.monto < 0 else "") + ar(m.monto)),
                   T(545, y, ar(m.saldo), "der"), T(556, y, marca(m.saldo))]
    return pdf([textos])


@pytest.mark.parametrize("titulo,marca,importe_izq", [
    ("D/C", lambda s: "C" if s >= 0 else "D", True),
    ("DB/CR", lambda s: "CR" if s >= 0 else "DB", True),
    ("D/H", lambda s: "H" if s >= 0 else "D", True),
    ("D/H", lambda s: "H" if s >= 0 else "D", False),
], ids=["dc", "dbcr", "dh", "dh_importe_der"])
def test_marca_de_saldo_deudor_o_acreedor_no_es_el_signo_del_movimiento(titulo, marca, importe_izq):
    """Cuenta corriente con "D/C" (o "DB/CR", "D/H") a la derecha del saldo: todas
    las filas dicen "C" (o "CR", "H") porque el saldo es acreedor, y el importe va
    sin signo. Esa columna no es la del signo: el signo sale del saldo, cierra, los
    débitos no se dan vuelta y la "H" no se pega a la descripción."""
    r = leer_extracto_pdf(_saldo_con_marca(MOVS_DC, SI_DC, titulo=titulo, marca=marca, importe_izq=importe_izq),
                          hoy=HOY)

    assert_movs(r, MOVS_DC)
    assert [m["descripcion"] for m in r["movimientos"]] == [m.descripcion for m in MOVS_DC]
    assert r["cuadre"]["cierra"]
    assert not any(m["dudosa"] for m in r["movimientos"])
    assert "signo_deducido" in {a["codigo"] for a in r["alertas"]}


def test_marca_de_saldo_con_importe_con_signo_no_deja_filas_dudosas():
    """Igual, pero el importe trae el "-" impreso en los débitos y la columna "D/C"
    del saldo dice "C" en todas las filas. El "-" no choca con esa "C": ningún
    débito queda como "Signo sin confirmar" ni aparece el aviso de filas para revisar."""
    r = leer_extracto_pdf(_saldo_con_marca(MOVS_DC, SI_DC, titulo="D/C", marca=lambda s: "C" if s >= 0 else "D",
                                           importe_izq=False, con_signo=True), hoy=HOY)

    assert_movs(r, MOVS_DC)
    assert r["cuadre"]["cierra"]
    assert not any(m["dudosa"] or m["motivos"] for m in r["movimientos"])
    assert "filas_dudosas" not in {a["codigo"] for a in r["alertas"]}


MOVS_MEDIO = con_saldos(D("150000.00"), [
    (date(2026, 9, 1), "VENTA POSNET LOTE 101", D("12500.00"), ["Débito"]),
    (date(2026, 9, 1), "VENTA POSNET LOTE 102", D("8300.50"), ["Crédito"]),
    (date(2026, 9, 2), "COMISION ADQUIRENTE", D("-410.25"), ["Crédito"]),
    (date(2026, 9, 3), "VENTA POSNET LOTE 103", D("121000.00"), ["Crédito"]),
    (date(2026, 9, 4), "TRANSFERENCIA A PROVEEDOR", D("-30000.00"), ["Dinero en cuenta"]),
    (date(2026, 9, 5), "VENTA POSNET LOTE 104", D("450.00"), ["Débito"]),
    (date(2026, 9, 6), "CONTRACARGO VENTA", D("-2500.00"), ["Débito"]),
    (date(2026, 9, 8), "VENTA POSNET LOTE 105", D("99999.99"), ["Crédito"]),
    (date(2026, 9, 9), "VENTA POSNET LOTE 106", D("1200.00"), ["Débito"]),
    (date(2026, 9, 10), "VENTA POSNET LOTE 107", D("6100.00"), ["Crédito"]),
    (date(2026, 9, 11), "PERCEPCION IIBB", D("-61.00"), ["Débito"]),
    (date(2026, 9, 12), "VENTA POSNET LOTE 108", D("310000.00"), ["Crédito"]),
])


def _medio_de_pago(movs: list[Mov], si: D, *, importe_izq: bool, con_signo: bool) -> bytes:
    """Fecha | Descripción | Medio de pago | Importe | Saldo de un comercio: el medio
    ("Débito", "Crédito", "Dinero en cuenta") es la tarjeta con la que se cobró."""
    x_medio = 270 if importe_izq else 300

    def importe(y: float, texto: str) -> T:
        return T(400, y, texto) if importe_izq else T(470, y, texto, "der")
    textos = [T(40, 800, "Resumen de cuenta", size=12), T(40, 785, "Período: 01/09/2026 al 30/09/2026"),
              T(40, 760, "Fecha"), T(100, 760, "Descripción"), T(x_medio, 760, "Medio de pago"),
              importe(760, "Importe"), T(560, 760, "Saldo", "der"),
              T(100, 746, "SALDO ANTERIOR"), T(560, 746, ar(si), "der")]
    y = 746
    for m in movs:
        y -= 12
        textos += [T(40, y, m.fecha.strftime("%d/%m/%Y")), T(100, y, m.descripcion), T(x_medio, y, m.extra[0]),
                   importe(y, ("-" if con_signo and m.monto < 0 else "") + ar(m.monto)), T(560, y, ar(m.saldo), "der")]
    return pdf([textos])


@pytest.mark.parametrize("importe_izq,con_signo", [(True, False), (True, True), (False, True)],
                         ids=["izq_sin_signo", "izq_con_signo", "der_con_signo"])
def test_columna_medio_de_pago_no_es_el_signo(importe_izq, con_signo):
    """Columna "Medio de pago" con "Débito"/"Crédito" (la tarjeta del cobro) entre
    la descripción y el importe: una venta con tarjeta de débito es un crédito en
    la cuenta. Esa columna no pasa a ser la del signo: el signo sale del saldo (o
    del "-" impreso), cierra, nada queda dudoso y el medio no se pega a la descripción."""
    r = leer_extracto_pdf(_medio_de_pago(MOVS_MEDIO, D("150000.00"), importe_izq=importe_izq, con_signo=con_signo),
                          hoy=HOY)

    assert_movs(r, MOVS_MEDIO)
    assert [m["descripcion"] for m in r["movimientos"]] == [m.descripcion for m in MOVS_MEDIO]
    assert r["cuadre"]["cierra"]
    assert not any(m["dudosa"] for m in r["movimientos"])
    assert ("signo_deducido" in {a["codigo"] for a in r["alertas"]}) == (not con_signo)


MOVS_TIPO = con_saldos(D("300000.00"), [       # extra: tipo, canal, tipo largo
    (date(2026, 9, 1), "TRANSFERENCIA RECIBIDA", D("80000.00"), ["Crédito", "CR", "Crédito inmediato"]),
    (date(2026, 9, 2), "PAGO PROVEEDOR", D("-45000.00"), ["Débito", "DB", "Débito automático"]),
    (date(2026, 9, 2), "IMPUESTO LEY 25413", D("-270.00"), ["Débito", "DB", "Débito automático"]),
    (date(2026, 9, 3), "DEBIN RECIBIDO", D("2400.00"), ["Crédito", "CR", "Crédito inmediato"]),
    (date(2026, 9, 5), "DEBITO AUTOMATICO LUZ", D("-12500.00"), ["Débito", "DB", "Débito automático"]),
    (date(2026, 9, 6), "REVERSO DEBITO AUTOMATICO", D("12500.00"), ["Reversa", "RV", "Transferencia"]),
    (date(2026, 9, 8), "DEPOSITO EFECTIVO", D("20000.00"), ["Crédito", "CR", "Crédito inmediato"]),
    (date(2026, 9, 9), "COMISION MANT CTA", D("-1500.00"), ["Débito", "DB", "Débito automático"]),
    (date(2026, 9, 12), "TRANSFERENCIA RECIBIDA", D("33000.00"), ["Crédito", "CR", "Crédito inmediato"]),
    (date(2026, 9, 15), "PAGO TARJETA", D("-61000.00"), ["Débito", "DB", "Débito automático"]),
    (date(2026, 9, 16), "INTERESES", D("120.33"), ["Ajuste", "AJ", "Transferencia"]),
])


def _con_tipo(movs: list[Mov], si: D, *, titulo: str, valor: int, tipo_izq: bool, importe: bool,
              con_signo: bool) -> bytes:
    """Fecha | Concepto | <titulo> | Débito | Crédito | Saldo (o un solo Importe);
    con `tipo_izq` la columna va antes del concepto. `valor`: qué extra se imprime."""
    xd, xt = (170, 100) if tipo_izq else (100, 280)
    importes = [T(470, 760, "Importe", "der")] if importe else [T(410, 760, "Débito", "der"),
                                                              T(480, 760, "Crédito", "der")]
    textos = [T(40, 800, "Resumen de cuenta", size=12), T(40, 785, "Período: 01/09/2026 al 30/09/2026"),
              T(40, 760, "Fecha"), T(xd, 760, "Concepto"), T(xt, 760, titulo), *importes, T(560, 760, "Saldo", "der"),
              T(xd, 746, "SALDO ANTERIOR"), T(560, 746, ar(si), "der")]
    y = 746
    for m in movs:
        y -= 12
        x = 470 if importe else (410 if m.monto < 0 else 480)
        textos += [T(40, y, m.fecha.strftime("%d/%m/%Y")), T(xd, y, m.descripcion), T(xt, y, m.extra[valor]),
                   T(x, y, ("-" if con_signo and m.monto < 0 else "") + ar(m.monto), "der"),
                   T(560, y, ar(m.saldo), "der")]
    return pdf([textos])


@pytest.mark.parametrize("titulo,valor,tipo_izq,importe,con_signo", [
    ("Tipo", 0, False, False, False),
    ("Tipo", 0, True, False, False),
    ("Tipo", 0, False, True, False),
    ("Tipo", 0, False, True, True),
    ("Canal", 1, False, True, False),
    ("Canal", 1, False, False, False),
    ("Tipo", 2, True, True, False),
    ("Tipo", 2, False, True, True),
], ids=["tipo_deb_cred", "tipo_a_la_izq", "tipo_importe", "tipo_importe_con_signo", "canal_importe",
        "canal_deb_cred", "tipo_largo_a_la_izq", "tipo_largo_con_signo"])
def test_columna_tipo_o_canal_no_se_pega_a_la_descripcion(titulo, valor, tipo_izq, importe, con_signo):
    """Columna "Tipo" (o "Canal") con casi todo "Débito"/"Crédito" (o "DB"/"CR") pero
    también "Reversa", "Ajuste", "RV", "AJ", o con valores de dos palabras ("Débito
    automático", "Crédito inmediato", "Transferencia"). Lo que dice esa columna no
    se pega ni antes ni después de la descripción, y los importes y el cierre siguen
    bien."""
    r = leer_extracto_pdf(_con_tipo(MOVS_TIPO, D("300000.00"), titulo=titulo, valor=valor, tipo_izq=tipo_izq,
                                    importe=importe, con_signo=con_signo), hoy=HOY)

    assert_movs(r, MOVS_TIPO)
    assert [m["descripcion"] for m in r["movimientos"]] == [m.descripcion for m in MOVS_TIPO]
    assert r["cuadre"]["cierra"]
    assert not any(m["dudosa"] for m in r["movimientos"])


# ── Letras de canal impresas justo después del importe (no son el signo) ────

MOVS_CANAL = con_saldos(D("50000.00"), [
    (date(2026, 9, 1), "DEPOSITO POR CAJA", D("12000.00")),
    (date(2026, 9, 2), "EXTRACCION POR CAJA", D("-4000.00")),
    (date(2026, 9, 3), "TRANSF RECIBIDA", D("8000.00")),
    (date(2026, 9, 4), "DEBITO AUTOMATICO SEGURO", D("-1500.00")),
    (date(2026, 9, 8), "PAGO TARJETA", D("-6200.00")),
    (date(2026, 9, 9), "DEPOSITO CHEQUE", D("3000.00")),
    (date(2026, 9, 10), "DEBITO AUTOMATICO LUZ", D("-900.00")),
])


def _canal_despues_del_importe(titulos: str, letras: str, hueco: float, titulo_canal: str = "") -> bytes:
    """Fecha | Detalle | Importe sin signo | canal | Saldo, con saldo en cada fila
    y la letra del canal `hueco` pt a la derecha del importe ("est": títulos que
    no se reconocen, lectura estructural; "enc": Fecha/Descripción/Importe/Saldo)."""
    tit = (["Dia", "Detalle", "Pesos", "Acumulado"] if titulos == "est"
           else ["Fecha", "Descripción", "Importe", "Saldo"])
    si = MOVS_CANAL[0].saldo - MOVS_CANAL[0].monto
    textos = [T(40, 800, "Resumen de cuenta - Período 01/09/2026 al 30/09/2026"),
              T(40, 770, tit[0]), T(110, 770, tit[1]), T(440, 770, tit[2], "der"), T(540, 770, tit[3], "der"),
              *([T(440 + hueco, 770, titulo_canal)] if titulo_canal else []),
              T(110, 756, "SALDO ANTERIOR"), T(540, 756, ar(si), "der")]
    y = 756
    for m, letra in zip(MOVS_CANAL, letras):
        y -= 12
        textos += [T(40, y, m.fecha.strftime("%d/%m/%Y")), T(110, y, m.descripcion), T(440, y, ar(m.monto), "der"),
                   T(440 + hueco, y, letra), T(540, y, ar(m.saldo), "der")]
    return pdf([textos])


@pytest.mark.parametrize("titulos", ["est", "enc"])
@pytest.mark.parametrize("letras,hueco,titulo_canal", [
    ("CCIDICD", 8, ""), ("CCIDICD", 2.2, ""), ("CCIDICD", 6, "Canal"), ("CCDDDCD", 4, ""),
])
def test_letra_de_canal_despues_del_importe_no_es_el_signo(titulos, letras, hueco, titulo_canal):
    """Importes sin signo con saldo en cada fila y una columna angosta de canal
    (C caja, D débito automático, I internet), sin título o titulada "Canal",
    impresa a pocos pt a la derecha del importe, con títulos que no se reconocen o
    con Fecha/Descripción/Importe/Saldo. Esas letras no son el signo (una
    extracción por caja dice "C", una transferencia recibida "D"; también con solo
    C y D): el signo sale del saldo de cada fila, como antes, la letra no se pega a
    la descripción y cierra sin filas para revisar."""
    r = leer_extracto_pdf(_canal_despues_del_importe(titulos, letras, hueco, titulo_canal), hoy=HOY)

    assert_movs(r, MOVS_CANAL)
    assert r["cuadre"]["cierra"]
    assert not any(m["dudosa"] for m in r["movimientos"])
    assert [m["descripcion"] for m in r["movimientos"]] == [m.descripcion for m in MOVS_CANAL]


# ── "D/H" (Debe/Haber): la "H" también es la marca del crédito ──────────────

def _marca_dh(m: Mov) -> str:
    return "H" if m.monto > 0 else "D"


def test_columna_d_h_lee_la_h_como_credito():
    """Columna del signo titulada "D/H" con las letras "D" (debe) y "H" (haber),
    como en algunas cooperativas, saldo en cada fila y el saldo inicial bien
    impreso: la "H" es el crédito, no se pega a la descripción, y el signo no
    se deduce del saldo."""
    r = leer_extracto_pdf(_tabla_signo(MOVS_DC, SI_DC, titulo="D/H", marca=_marca_dh), hoy=HOY)

    assert_movs(r, MOVS_DC)
    assert [m["descripcion"] for m in r["movimientos"]] == [m.descripcion for m in MOVS_DC]
    assert r["cuadre"]["cierra"]
    assert "signo_deducido" not in {a["codigo"] for a in r["alertas"]}


def test_columna_d_h_con_el_saldo_inicial_equivocado_no_da_vuelta_el_primer_credito():
    """La misma tabla "D/H" con el cuadro de arriba diciendo un saldo inicial que
    no es el de los movimientos: el crédito más viejo (marcado "H") sigue siendo
    crédito y ninguna fila queda con el signo sin confirmar (el signo lo dice el
    PDF, no se deduce contra ese saldo equivocado). No se da por cerrado y el aviso
    dice que lo que no coincide es el saldo inicial del PDF."""
    r = leer_extracto_pdf(_tabla_signo(MOVS_DC, D("1000000.00"), titulo="D/H", marca=_marca_dh), hoy=HOY)

    assert_movs(r, MOVS_DC)
    assert r["movimientos"][0]["descripcion"] == "CRÉDITO POR TRANSFERENCIA"
    assert not any("Signo sin confirmar" in m["motivos"] for m in r["movimientos"])
    assert not r["cuadre"]["cierra"]
    aviso = next(a["mensaje"] for a in r["alertas"] if a["codigo"] == "no_cierra")
    assert aviso.startswith("Los movimientos cierran entre sí")
    assert "saldo inicial que figura en el PDF ($ 1.000.000,00)" in aviso


# ── "Débito/Crédito" con importes "1.000,00 C" y otra columna "Importe origen" ─

def test_importes_con_sufijo_d_c_bajo_debito_credito_y_una_columna_importe_origen():
    """Encabezado Fecha | Concepto | Débito/Crédito | Saldo | Importe origen: bajo
    "Débito/Crédito" van los importes sin signo con la marca pegada ("1.000,00 C",
    "250,00 D") y a la derecha del saldo el importe en dólares ("USD 1,00"). El
    importe del movimiento es el de "Débito/Crédito" con el signo de su marca, no
    el de dólares, y el extracto cierra."""
    si = D("5000.00")
    movs = con_saldos(si, [
        (date(2026, 9, 1), "TRANSFERENCIA RECIBIDA", D("1000.00")),
        (date(2026, 9, 3), "PAGO SERVICIO", D("-250.00")),
        (date(2026, 9, 8), "COMPRA", D("-99.90")),
        (date(2026, 9, 9), "DEPOSITO", D("500.00")),
    ])
    textos = [T(40, 800, "Resumen de cuenta - Período 01/09/2026 al 30/09/2026"),
              T(40, 770, "Fecha"), T(110, 770, "Concepto"), T(400, 770, "Débito/Crédito", "der"),
              T(470, 770, "Saldo", "der"), T(560, 770, "Importe origen", "der"),
              T(110, 756, "SALDO ANTERIOR"), T(470, 756, ar(si), "der")]
    y = 756
    for m in movs:
        y -= 12
        textos += [T(40, y, m.fecha.strftime("%d/%m/%Y")), T(110, y, m.descripcion), T(400, y, ar(m.monto), "der"),
                   T(402, y, "C" if m.monto > 0 else "D"), T(470, y, ar(m.saldo), "der"),
                   T(560, y, "USD " + ar(m.monto / 1000), "der")]

    r = leer_extracto_pdf(pdf([textos]), hoy=HOY)

    assert [m["monto"] for m in r["movimientos"]] == [D("1000.00"), D("-250.00"), D("-99.90"), D("500.00")]
    assert_movs(r, movs)
    assert r["cuadre"]["cierra"]
    assert [m["descripcion"] for m in r["movimientos"]] == [m.descripcion for m in movs]


# ── Elegir entre lecturas que no cierran (revisión adversaria) ──────────────
# Entre layouts de filas distintas manda leer más filas y la diferencia más
# chica; "menos signos supuestos" solo desempata lecturas de las mismas filas.

def _tabla_importe(movs: list[Mov], si: D, *, arriba: list[T] = (), y: float = 710, importe_izq: bool = False,
                   saldo_anterior: bool = True, por_dia: bool = False, saldo_actual: D | None = None) -> bytes:
    """Fecha | Concepto | Importe (sin signo) | Saldo, ascendente, debajo de los
    textos `arriba` (un cuadro de resumen). `por_dia`: saldo solo en la última
    fila de cada día. `importe_izq`: el importe alineado a la izquierda."""
    x_imp, alin = (400, "izq") if importe_izq else (470, "der")
    textos = [T(40, 800, "Resumen de cuenta", size=12), T(40, 785, "Período: 01/09/2026 al 30/09/2026"), *arriba,
              T(40, y, "Fecha"), T(100, y, "Concepto"), T(x_imp, y, "Importe", alin), T(560, y, "Saldo", "der")]
    if saldo_anterior:
        y -= 14
        textos += [T(100, y, "SALDO ANTERIOR"), T(560, y, ar(si), "der")]
    for i, m in enumerate(movs):
        y -= 12
        textos += [T(40, y, m.fecha.strftime("%d/%m/%Y")), T(100, y, m.descripcion), T(x_imp, y, ar(m.monto), alin)]
        if not por_dia or i == len(movs) - 1 or movs[i + 1].fecha != m.fecha:
            textos.append(T(560, y, ar(m.saldo), "der"))
    if saldo_actual is not None:
        textos += [T(100, y - 14, "SALDO ACTUAL"), T(560, y - 14, ar(saldo_actual), "der")]
    return pdf([textos])


def _assert_salvo_el_par_ambiguo(r: dict, movs: list[Mov], par: tuple[int, int]):
    """Todas las filas de la tabla con su fecha e importe; el signo exacto en
    todas menos el par del mismo día que va y vuelve (queda para revisar)."""
    leidos = r["movimientos"]
    assert [(m["fecha"], abs(m["monto"]), m["descripcion"]) for m in leidos] == \
        [(e.fecha, abs(e.monto), e.descripcion) for e in movs]
    assert [i for i, m in enumerate(leidos) if m["dudosa"]] == list(par)
    seguras = [i for i in range(len(movs)) if i not in par]
    assert_movs({"movimientos": [leidos[i] for i in seguras]}, [movs[i] for i in seguras], con_saldo=False)
    assert [c["campo"] for c in r["aprendizaje"]["layout"]["columnas"]] == ["fecha", "descripcion", "importe", "saldo"]


def test_cuadro_de_resumen_arriba_no_le_gana_a_la_tabla_con_saldo_por_dia():
    """Arriba un cuadro "Fecha | Saldo anterior | Créditos | Débitos | Saldo actual"
    con una fila de valores; abajo la tabla con el importe sin signo y el saldo
    solo al final de cada día, con 2.400 que salen y vuelven el mismo día (ese par
    no se puede deducir). Gana la tabla con sus 10 filas, no la fila del cuadro;
    solo el par queda para revisar y el aviso es la diferencia de ese par."""
    si = D("150000.00")
    movs = con_saldos(si, [
        (date(2026, 9, 1), "TRANSFERENCIA RECIBIDA", D("80000.00")),
        (date(2026, 9, 2), "PAGO PROVEEDOR", D("-45000.00")), (date(2026, 9, 2), "IMPUESTO LEY 25413", D("-270.00")),
        (date(2026, 9, 3), "TRANSF A TERCEROS", D("-2400.00")), (date(2026, 9, 3), "TRANSF DEVUELTA", D("2400.00")),
        (date(2026, 9, 5), "DEBITO AUTOMATICO EDENOR", D("-12500.00")),
        (date(2026, 9, 8), "DEPOSITO EFECTIVO", D("20000.00")), (date(2026, 9, 9), "COMISION MANT CTA", D("-1500.00")),
        (date(2026, 9, 12), "TRANSFERENCIA RECIBIDA", D("33000.00")),
        (date(2026, 9, 15), "PAGO TARJETA VISA", D("-61000.00")),
    ])
    cuadro = [T(40, 760, "Fecha"), T(130, 760, "Saldo anterior"), T(250, 760, "Créditos"), T(350, 760, "Débitos"),
              T(450, 760, "Saldo actual"), T(40, 748, "30/09/2026"), T(180, 748, ar(si), "der"),
              T(290, 748, "135.400,00", "der"), T(390, 748, "122.670,00", "der"),
              T(500, 748, ar(movs[-1].saldo), "der")]

    r = leer_extracto_pdf(_tabla_importe(movs, si, arriba=cuadro, por_dia=True), hoy=HOY)

    _assert_salvo_el_par_ambiguo(r, movs, (3, 4))
    avisos = {a["codigo"]: a["mensaje"] for a in r["alertas"]}
    assert avisos["no_cierra"] == "El saldo no cierra: hay una diferencia de -$ 4.800,00."
    assert "renglones_ilegibles" not in avisos


def test_importe_alineado_a_la_izquierda_no_se_parte_en_debito_y_credito():
    """Home banking con la columna Importe alineada a la izquierda, saldo solo al
    final de cada día y 400.000 que salen y vuelven el mismo día. La lectura
    estructural parte los importes en un "Débito" y un "Crédito" falsos y no
    supone ningún signo, pero lee los créditos como débitos: gana la lectura del
    título "Importe", con el signo de cada fila deducido del saldo del día."""
    si = D("880000.00")
    movs = con_saldos(si, [
        (date(2026, 9, 1), "CREDITO POR TRANSFERENCIA", D("76000.00")), (date(2026, 9, 1), "SIRCREB", D("-7.60")),
        (date(2026, 9, 1), "IMP LEY 25413 S/CREDITOS", D("-456.00")),
        (date(2026, 9, 2), "TRANSFERENCIA HB A TERCEROS", D("-400000.00")),
        (date(2026, 9, 2), "TRANSFERENCIA DEVUELTA", D("400000.00")),
        (date(2026, 9, 3), "CREDITO POR CREDIN", D("123456.78")), (date(2026, 9, 3), "SIRCREB", D("-12.35")),
        (date(2026, 9, 3), "IMP LEY 25413 S/CREDITOS", D("-740.74")),
        (date(2026, 9, 4), "TRANSFERENCIA HB A TERCEROS", D("-250000.00")),
        (date(2026, 9, 4), "IMP LEY 25413 S/DEBITOS", D("-1500.00")),
        (date(2026, 9, 7), "CREDITO POR TRANSFERENCIA", D("19100.00")),
        (date(2026, 9, 8), "PAGO SERVICIO EDENOR", D("-35210.40")),
        (date(2026, 9, 9), "DEPOSITO EFECTIVO", D("5000.00")),
    ])

    r = leer_extracto_pdf(_tabla_importe(movs, si, y=760, importe_izq=True, por_dia=True), hoy=HOY)

    _assert_salvo_el_par_ambiguo(r, movs, (3, 4))
    assert r["saldo_final"] == movs[-1].saldo and not r["cuadre"]["cierra"]
    aviso = next(a["mensaje"] for a in r["alertas"] if a["codigo"] == "no_cierra")
    assert aviso == "El saldo no cierra: hay una diferencia de -$ 800.000,00."


def test_cuadro_con_titulos_y_valores_abajo_no_le_gana_a_los_movimientos():
    """Cuadro "Fecha cierre | Saldo anterior | Débitos | Créditos | Saldo actual"
    con los valores en el renglón de abajo, y la tabla sin renglón de saldo
    anterior (el signo del primer movimiento se supone) y con un "SALDO ACTUAL" de
    home banking que difiere en 12.000. Se leen los 5 movimientos, no una fila
    armada con los números del cuadro, y el aviso es la diferencia de 12.000."""
    si = D("200000.00")
    movs = con_saldos(si, [
        (date(2026, 9, 1), "TRANSFERENCIA RECIBIDA", D("150000.00")),
        (date(2026, 9, 2), "PAGO PROVEEDOR", D("-50000.00")), (date(2026, 9, 10), "PERCEPCION IVA", D("-1500.00")),
        (date(2026, 9, 20), "DEPOSITO", D("30000.00")), (date(2026, 9, 30), "COMISION MANT CTA", D("-2500.00")),
    ])
    sf = movs[-1].saldo + D("12000.00")
    cuadro = [T(40, 770, "Fecha cierre"), T(200, 770, "Saldo anterior", "der"), T(300, 770, "Débitos", "der"),
              T(400, 770, "Créditos", "der"), T(520, 770, "Saldo actual", "der"), T(40, 758, "30/09/2026"),
              T(200, 758, ar(si), "der"), T(300, 758, "54.000,00", "der"), T(400, 758, "180.000,00", "der"),
              T(520, 758, ar(sf), "der")]

    r = leer_extracto_pdf(_tabla_importe(movs, si, arriba=cuadro, y=720, saldo_anterior=False, saldo_actual=sf),
                          hoy=HOY)

    assert_movs(r, movs)
    assert [m["descripcion"] for m in r["movimientos"]] == [m.descripcion for m in movs]
    assert [m["dudosa"] for m in r["movimientos"]] == [True, False, False, False, False]
    assert r["saldo_inicial"] == si and r["saldo_final"] == sf and not r["cuadre"]["cierra"]
    aviso = next(a["mensaje"] for a in r["alertas"] if a["codigo"] == "no_cierra")
    assert aviso == "El saldo no cierra: hay una diferencia de $ 12.000,00."


@pytest.mark.parametrize("si_pdf", [D("10000.00"), D("12500.00")])
def test_fila_sin_palabra_con_un_menos_impreso_no_pierde_la_columna_del_signo(si_pdf):
    """Columna "Débito/Crédito" y Monto sin signo, salvo un AJUSTE impreso "-$"
    al lado de "Crédito" (el "-" manda), y un PAGO SERVICIO sin la palabra, todos
    con saldo; el saldo inicial impreso está bien o es de otra fecha (12.500 en
    vez de 10.000). Gana la lectura con la columna del signo: COMISION es débito,
    el pago sale del saldo, las palabras no se pegan a las descripciones, la
    diferencia es solo la del saldo inicial y el AJUSTE queda para revisar por el
    conflicto, no como un signo supuesto."""
    si = D("10000.00")
    movs = con_saldos(si, [
        (date(2026, 9, 1), "DEPOSITO", D("500.00")), (date(2026, 9, 2), "AJUSTE", D("-400.00")),
        (date(2026, 9, 3), "COMISION", D("-12.00")), (date(2026, 9, 4), "PAGO SERVICIO", D("-300.00")),
    ])
    textos = [T(40, 800, "Movimientos de cuenta", size=10), T(40, 785, "Período: 01/09/2026 al 30/09/2026"),
              T(43, 760, "Saldo inicial:"), T(287.6, 760, "$ " + ar(si_pdf), "der"),
              T(40, 740, "Fecha"), T(110, 740, "Concepto"), T(287, 740, "Débito/Crédito"), T(426.5, 740, "Monto"),
              T(524.9, 740, "Saldo")]
    palabras = {"AJUSTE": "Crédito", "PAGO SERVICIO": ""}
    y = 740
    for m in movs:
        y -= 16.7
        palabra = palabras.get(m.descripcion, _dc(m))
        textos += [T(40, y, m.fecha.strftime("%d/%m/%Y")), T(110, y, m.descripcion),
                   T(457.6, y, ("-$ " if m.descripcion == "AJUSTE" else "$ ") + ar(m.monto), "der"),
                   T(555.3, y, "$ " + ar(m.saldo), "der")] + ([T(310, y, palabra)] if palabra else [])

    r = leer_extracto_pdf(pdf([textos]), hoy=HOY)

    assert_movs(r, movs)
    assert [m["descripcion"] for m in r["movimientos"]] == [m.descripcion for m in movs]
    assert r["cuadre"]["cierra"] == (si_pdf == si) and r["cuadre"]["diferencia"] == si - si_pdf
    assert [m["dudosa"] for m in r["movimientos"]] == [si_pdf != si, True, False, False]
    assert not any("Signo sin confirmar" in m["motivos"] for m in r["movimientos"])
    assert "signo" in [c["campo"] for c in r["aprendizaje"]["layout"]["columnas"]]


# ── El aviso "borrá ese saldo" solo cuando se leyó todo el PDF ──────────────

def _dibujar(c, textos):
    for t in textos:
        c.setFont(t.font, t.size)
        (c.drawRightString if t.alin == "der" else c.drawString)(t.x, t.y, t.texto)


def _pdf_hoja2_sin_texto(hoja1: list, hoja2: list, forma: str) -> bytes:
    """Dos hojas: la 1 normal; la 2 con el texto girado 90° o con la tabla como
    imagen (sin texto seleccionable). Las dos con su pie "Hoja N de 2"."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    _dibujar(c, hoja1 + [T(500, 40, "Hoja 1 de 2")])
    c.showPage()
    c.saveState()
    if forma == "girada":
        c.translate(595, 0)
        c.rotate(90)
        _dibujar(c, hoja2)
    else:
        img = Image.new("RGB", (1100, 300), "white")
        lapiz = ImageDraw.Draw(img)
        for i, y in enumerate(sorted({t.y for t in hoja2}, reverse=True)):
            renglon = "   ".join(t.texto for t in sorted(hoja2, key=lambda t: t.x) if t.y == y)
            lapiz.text((10, 20 + 30 * i), renglon, fill="black")
        c.drawImage(ImageReader(img), 40, 500, width=520, height=140)
    c.restoreState()
    _dibujar(c, [T(500, 40, "Hoja 2 de 2")])
    c.showPage()
    c.save()
    return buf.getvalue()


@pytest.mark.parametrize("forma", ["girada", "imagen"])
def test_hoja_sin_texto_no_hace_borrar_el_saldo_final_que_esta_bien(forma):
    """Resumen de dos hojas: la 1 trae el cuadro "Saldo anterior / Saldo final"
    (los dos bien impresos) y 6 movimientos; la 2 trae los últimos 3, pero
    girada o dibujada como imagen, así que no se lee. Los 6 de la hoja 1 cierran
    entre sí, pero el aviso no puede decir "borrá ese saldo" (el PDF está
    completo y el saldo final es el bueno): da la diferencia y avisa que la
    hoja 2 casi no tiene texto."""
    si = D("320000.00")
    movs = con_saldos(si, [
        (date(2026, 9, 1), "TRANSFERENCIA RECIBIDA", D("150000.00")),
        (date(2026, 9, 2), "PAGO PROVEEDOR", D("-50000.00")),
        (date(2026, 9, 4), "DEB AUT SEGURO", D("-12800.00")),
        (date(2026, 9, 8), "DEPOSITO EFECTIVO", D("40000.00")),
        (date(2026, 9, 12), "IMPUESTO LEY 25413", D("-1220.00")),
        (date(2026, 9, 15), "PAGO TARJETA", D("-88000.00")),
        (date(2026, 9, 20), "TRANSFERENCIA RECIBIDA", D("70000.00")),
        (date(2026, 9, 25), "PAGO PROVEEDOR", D("-31000.00")),
        (date(2026, 9, 30), "COMISION MANT CTA", D("-2500.00")),
    ])
    hoja1 = [T(40, 800, "BANCO EJEMPLO S.A.", size=16, font="Helvetica-Bold"),
             T(40, 780, "Resumen de cuenta corriente - Período 01/09/2026 al 30/09/2026"),
             T(40, 765, "Saldo anterior"), T(300, 765, ar(si), "der"),
             T(330, 765, "Saldo final"), T(560, 765, ar(movs[-1].saldo), "der"), *encabezado(735)]
    hoja2 = [*encabezado(560)]
    for i, m in enumerate(movs):
        (hoja1 if i < 6 else hoja2).extend(fila((723 if i < 6 else 548) - 12 * (i % 6), m))

    r = leer_extracto_pdf(_pdf_hoja2_sin_texto(hoja1, hoja2, forma), hoy=HOY)

    assert_movs(r, movs[:6])
    assert not r["cuadre"]["cierra"] and r["saldo_final"] == movs[-1].saldo
    avisos = {a["codigo"]: a["mensaje"] for a in r["alertas"]}
    assert avisos["no_cierra"] == "El saldo no cierra: hay una diferencia de $ 36.500,00."
    assert avisos["paginas_sin_texto"].startswith("La página 2 casi no tiene texto")


# ── Lecturas con IA: los importes son del modelo, no del PDF ────────────────

SI_IA = D("150000.00")
MOVS_IA = con_saldos(SI_IA, [
    (date(2026, 9, 1), "DEB AUT SEGURO", D("-48500.00")),
    (date(2026, 9, 2), "TRANSFERENCIA RECIBIDA", D("90000.00")),
    (date(2026, 9, 10), "PAGO PROVEEDOR", D("-25000.00")),
    (date(2026, 9, 30), "COMISION MANT CTA", D("-2500.00")),
])
_LEE_MAL = Mov(MOVS_IA[0].fecha, MOVS_IA[0].descripcion, D("-45800.00"), MOVS_IA[0].saldo)
_SALDO_COMO_MOV = Mov(None, "SALDO ANTERIOR", SI_IA, SI_IA)


@pytest.mark.parametrize("devueltos,diferencia,dudosas", [
    (MOVS_IA[1:], "-$ 48.500,00", [True, False, False]),            # se saltea el primero
    ([_LEE_MAL] + MOVS_IA[1:], "-$ 2.700,00", [True, False, False, False]),  # 48.500 leído 45.800
    (MOVS_IA[:-1], "-$ 2.500,00", [False, False, False]),           # se saltea el último
    ([_SALDO_COMO_MOV] + MOVS_IA, "-$ 150.000,00", [True, False, False, False, False]),
], ids=["omite_primero", "lee_mal_el_primero", "omite_ultimo", "saldo_anterior_como_movimiento"])
def test_lectura_con_ia_no_culpa_al_saldo_del_pdf(monkeypatch, devueltos, diferencia, dudosas):
    """PDF escaneado que lee la IA: devuelve el saldo inicial y el final bien,
    pero se saltea un movimiento de una punta, lee mal el importe del primero o
    devuelve el "SALDO ANTERIOR" como un movimiento sin fecha. Los demás cierran
    entre sí, pero el signo y los importes los dice el modelo, no el PDF: el
    aviso es la diferencia, nunca "borrá ese saldo"."""
    resultado = {
        "movimientos": [{"fecha": m.fecha, "descripcion": m.descripcion, "monto": m.monto, "saldo": m.saldo}
                        for m in devueltos],
        "saldo_inicial": SI_IA, "saldo_final": MOVS_IA[-1].saldo,
        "periodo": (date(2026, 9, 1), date(2026, 9, 30)), "banco": None,
    }
    monkeypatch.setattr(ia_mod, "ia_disponible", lambda: True)
    monkeypatch.setattr(ia_mod, "leer_con_ia", lambda doc, contenido, ctx, *, escaneado: (resultado, [], True))

    r = leer_extracto_pdf(pdf([[T(40, 800, "x")]]), hoy=HOY)

    assert r["metodo"] == "ia" and r["escaneado"] and not r["cuadre"]["cierra"]
    assert_movs(r, devueltos)
    assert [m["dudosa"] for m in r["movimientos"]] == dudosas
    aviso = next(a["mensaje"] for a in r["alertas"] if a["codigo"] == "no_cierra")
    assert aviso == f"El saldo no cierra: hay una diferencia de {diferencia}."
    assert not any("borrá" in a["mensaje"] for a in r["alertas"])


# ── Un solo movimiento no se controla contra nada ───────────────────────────

def test_un_solo_movimiento_no_dice_que_los_movimientos_cierran_entre_si():
    """"SALDO ANTERIOR" 10.000, una sola fila (PAGO SERVICIO −1.000, saldo 9.000)
    y "SALDO FINAL" 8.500. Con una fila no hay nada que controlar entre
    movimientos: el aviso es la diferencia (−$ 500), sin "cierran entre sí" ni
    "borrá ese saldo"."""
    si = D("10000.00")
    movs = con_saldos(si, [(date(2026, 9, 3), "PAGO SERVICIO", D("-1000.00"))])
    textos = [T(40, 800, "Resumen de cuenta - Período 01/09/2026 al 30/09/2026"), *encabezado(750),
              T(90, 736, "SALDO ANTERIOR"), T(560, 736, ar(si), "der"), *fila(724, movs[0]),
              T(90, 710, "SALDO FINAL"), T(560, 710, ar(D("8500.00")), "der")]

    r = leer_extracto_pdf(pdf([textos]), hoy=HOY)

    assert_movs(r, movs)
    assert r["movimientos"][0]["descripcion"] == "PAGO SERVICIO" and not r["movimientos"][0]["dudosa"]
    assert not r["cuadre"]["cierra"] and r["saldo_final"] == D("8500.00")
    aviso = next(a["mensaje"] for a in r["alertas"] if a["codigo"] == "no_cierra")
    assert aviso == f"El saldo no cierra: hay una diferencia de {formatear_pesos(D('-500.00'))}."
    assert not any("cierran entre sí" in a["mensaje"] or "borrá" in a["mensaje"] for a in r["alertas"])


def _una_hoja(movs: list[Mov], si: D, sf: D | None = None, *, primera_sin_fecha: bool = False) -> bytes:
    """Fecha | Descripción | Débito | Crédito | Saldo en una hoja, con "SALDO
    ANTERIOR" arriba y "SALDO FINAL" abajo (por defecto, el de la última fila)."""
    textos = [T(40, 800, "Resumen de cuenta corriente - Período 01/09/2026 al 30/09/2026"),
              *encabezado(750), T(90, 736, "SALDO ANTERIOR"), T(560, 736, ar(si), "der")]
    y = 736
    for i, m in enumerate(movs):
        y -= 12
        textos += fila(y, m, fecha=not (primera_sin_fecha and i == 0))
    sf = movs[-1].saldo if sf is None else sf
    return pdf([textos + [T(90, y - 14, "SALDO FINAL"), T(560, y - 14, ar(sf), "der")]])


def _hojas(movs: list[Mov], si: D, por_hoja: int, *, abajo: str = "SALDO A TRANSPORTAR",
           arriba: str = "SALDO ANTERIOR", fechada: bool = False) -> list[list[T]]:
    """Las hojas (sin armar el PDF) de un extracto con el cuadro "Saldo anterior /
    Saldo final" arriba de la primera, `abajo` al pie de cada hoja y `arriba` al
    comienzo de la siguiente, las dos con el saldo de ese punto (el transporte).
    Con `fechada`, la línea de abajo trae la fecha y los totales de la hoja."""
    grupos = [movs[i:i + por_hoja] for i in range(0, len(movs), por_hoja)]
    paginas, previo = [], si
    for n, hoja in enumerate(grupos, 1):
        textos = [T(40, 810, "Resumen de cuenta corriente - Período 01/09/2026 al 30/09/2026"),
                  T(40, 25, f"Hoja {n} de {len(grupos)}"), *encabezado(760)]
        if n == 1:
            textos += [T(40, 790, "Saldo anterior"), T(300, 790, ar(si), "der"),
                       T(330, 790, "Saldo final"), T(560, 790, ar(movs[-1].saldo), "der")]
        else:
            textos += [T(90, 746, arriba), T(560, 746, ar(previo), "der")]
        y = 746
        for m in hoja:
            y -= 12
            textos += fila(y, m)
        if n < len(grupos):
            textos += [T(90, y - 14, abajo), T(560, y - 14, ar(hoja[-1].saldo), "der")]
            if fechada:
                textos += [T(40, y - 14, hoja[-1].fecha.strftime("%d/%m/%Y")),
                           T(420, y - 14, ar(sum(-m.monto for m in hoja if m.monto < 0)), "der"),
                           T(490, y - 14, ar(sum(m.monto for m in hoja if m.monto > 0)), "der")]
        previo = hoja[-1].saldo
        paginas.append(textos)
    return paginas


# ── "TRANSPORTE..." en la descripción no es el transporte entre hojas ───────

@pytest.mark.parametrize("donde,item", [
    (0, (date(2026, 9, 1), "TRANSPORTES DEL SUR SRL", D("-48500.00"))),
    (2, (date(2026, 9, 30), "TRANSPORTE DE CAUDALES SEPTIEMBRE", D("-18150.00"))),
])
def test_movimiento_que_empieza_con_transporte_es_un_movimiento(donde, item):
    """El primer o el último movimiento es un débito a "TRANSPORTES DEL SUR SRL"
    o el servicio de "TRANSPORTE DE CAUDALES SEPTIEMBRE", con fecha e importe, y
    el saldo anterior y el final impresos están bien. Es un movimiento, no la
    línea que repite el saldo entre hojas: se lee con su descripción, el extracto
    cierra y no aparece el aviso de "borrá ese saldo"."""
    items = [(date(2026, 9, 2), "TRANSFERENCIA RECIBIDA", D("90000.00")),
             (date(2026, 9, 10), "PAGO PROVEEDOR", D("-25000.00"))]
    items.insert(donde, item)
    movs = con_saldos(D("150000.00"), items)

    r = leer_extracto_pdf(_una_hoja(movs, D("150000.00")), hoy=HOY)

    assert_movs(r, movs)
    assert r["movimientos"][donde]["descripcion"] == item[1]
    assert r["cuadre"]["cierra"] and r["saldo_inicial"] == D("150000.00") and r["saldo_final"] == movs[-1].saldo
    assert not any(m["dudosa"] for m in r["movimientos"])
    assert "no_cierra" not in {a["codigo"] for a in r["alertas"]}


MOVS_HOJAS = con_saldos(D("500000.00"), [
    (date(2026, 9, 1), "TRANSFERENCIA RECIBIDA", D("150000.00")),
    (date(2026, 9, 2), "PAGO PROVEEDOR", D("-50000.00")),
    (date(2026, 9, 4), "DEB AUT SEGURO", D("-12800.00")),
    (date(2026, 9, 8), "TRANSPORTES LOPEZ SRL", D("-40000.00")),       # última fila de la hoja 1
    (date(2026, 9, 12), "IMPUESTO LEY 25413", D("-1220.00")),
    (date(2026, 9, 15), "PAGO TARJETA", D("-88000.00")),
    (date(2026, 9, 20), "TRANSFERENCIA RECIBIDA", D("70000.00")),
    (date(2026, 9, 30), "COMISION MANT CTA", D("-2500.00")),
])


@pytest.mark.parametrize("abajo,arriba,fechada", [
    ("SALDO A TRANSPORTAR", "SALDO ANTERIOR", False),
    ("Transporte", "Transporte", False),
    ("Saldo a transportar", "Viene de hoja 1", False),
    ("TRANSPORTE", "TRANSPORTE", True),
])
def test_transportes_srl_al_pie_de_la_hoja_no_corta_el_pdf_como_otra_cuenta(abajo, arriba, fechada):
    """Dos hojas. La última fila de la hoja 1 es un débito a "TRANSPORTES LOPEZ
    SRL"; debajo va la línea de transporte de verdad ("Saldo a transportar",
    "Transporte", a veces con la fecha y los totales de la hoja) y arriba de la
    hoja 2 se repite el saldo. El proveedor es un movimiento y las líneas de
    transporte no: se leen los 8 movimientos, cierra con el saldo final del
    cuadro y la hoja 2 no se corta como si fuera otra cuenta."""
    paginas = _hojas(MOVS_HOJAS, D("500000.00"), 4, abajo=abajo, arriba=arriba, fechada=fechada)

    r = leer_extracto_pdf(pdf(paginas), hoy=HOY)

    assert_movs(r, MOVS_HOJAS)
    assert r["movimientos"][3]["descripcion"] == "TRANSPORTES LOPEZ SRL"
    assert r["cuadre"]["cierra"] and r["saldo_final"] == MOVS_HOJAS[-1].saldo
    codigos = {a["codigo"] for a in r["alertas"]}
    assert "varias_cuentas" not in codigos and "no_cierra" not in codigos


def test_aviso_de_saldos_no_culpa_al_saldo_final_si_el_resto_se_corto_como_otra_cuenta():
    """Falta la hoja 2 de 3: el transporte de arriba de la hoja 3 no repite el
    saldo de la hoja 1 y el resto se corta como otra cuenta. Lo que se leyó
    cierra entre sí, pero no es todo el PDF y el saldo final del cuadro está
    bien: el aviso es la diferencia, no "borrá ese saldo"."""
    movs = con_saldos(D("500000.00"), [
        (date(2026, 9, 1), "TRANSFERENCIA RECIBIDA", D("150000.00")),
        (date(2026, 9, 2), "PAGO PROVEEDOR", D("-50000.00")),
        (date(2026, 9, 4), "DEB AUT SEGURO", D("-12800.00")),
        (date(2026, 9, 8), "PAGO TARJETA", D("-40000.00")),
        (date(2026, 9, 12), "IMPUESTO LEY 25413", D("-1220.00")),
        (date(2026, 9, 15), "PAGO TARJETA", D("-88000.00")),
        (date(2026, 9, 20), "TRANSFERENCIA RECIBIDA", D("70000.00")),
        (date(2026, 9, 25), "DEPOSITO", D("5000.00")),
        (date(2026, 9, 28), "PAGO SERVICIO", D("-3000.00")),
        (date(2026, 9, 30), "COMISION MANT CTA", D("-2500.00")),
    ])
    hoja1, _, hoja3 = _hojas(movs, D("500000.00"), 4)

    r = leer_extracto_pdf(pdf([hoja1, hoja3]), hoy=HOY)

    assert not r["cuadre"]["cierra"]
    aviso = next(a["mensaje"] for a in r["alertas"] if a["codigo"] == "no_cierra")
    assert aviso.startswith("El saldo no cierra: hay una diferencia de")
    assert not any("borrá" in a["mensaje"] for a in r["alertas"])


# ── Una fila dudosa en el extremo: el aviso no culpa al saldo impreso ───────

@pytest.mark.parametrize("caso,motivo,diferencia", [
    ("agosto", "Fecha fuera del período", "$ 20.000,00"),
    ("sin_fecha", "Sin fecha", "$ 20.000,00"),
    ("octubre", "Fecha fuera del período", "$ 30.000,00"),
])
def test_aviso_de_saldos_no_culpa_al_saldo_impreso_si_la_fila_del_extremo_es_dudosa(caso, motivo, diferencia):
    """Los saldos impresos están bien, pero en un extremo hay una fila que sobra:
    un pago del 20/08 que el "SALDO ANTERIOR" (al 31/08) ya incluye, ese mismo
    pago sin fecha, o un pago del 12/10 que el "SALDO FINAL" (al 30/09) no
    incluye. La fila queda para revisar con su motivo y el aviso es la
    diferencia, no "borrá ese saldo": lo que hay que borrar es la fila."""
    items = [(date(2026, 9, 2), "TRANSFERENCIA RECIBIDA", D("90000.00")),
             (date(2026, 9, 10), "PAGO PROVEEDOR", D("-25000.00")),
             (date(2026, 9, 30), "COMISION MANT CTA", D("-2500.00"))]
    if caso == "octubre":
        movs = con_saldos(D("100000.00"), items + [(date(2026, 10, 12), "PAGO TARJETA", D("-30000.00"))])
        si, sf, extremo = D("100000.00"), movs[-2].saldo, -1
    else:
        movs = con_saldos(D("100000.00"), [(date(2026, 8, 20), "PAGO PROVEEDOR", D("-20000.00"))] + items)
        si, sf, extremo = movs[0].saldo, movs[-1].saldo, 0

    r = leer_extracto_pdf(_una_hoja(movs, si, sf, primera_sin_fecha=caso == "sin_fecha"), hoy=HOY)

    assert [(m["monto"], m["saldo"]) for m in r["movimientos"]] == [(m.monto, m.saldo) for m in movs]
    assert r["movimientos"][extremo]["dudosa"] and motivo in r["movimientos"][extremo]["motivos"]
    aviso = next(a["mensaje"] for a in r["alertas"] if a["codigo"] == "no_cierra")
    assert aviso == f"El saldo no cierra: hay una diferencia de {diferencia}."


# ── Tercera revisión: un solo día, reversos, medio de pago sin saldo, CUIT,
#    marcas a dos espacios y códigos DB/CR. Datos inventados. ─────────────────

def _movimientos_de_un_resumen(movs: list[Mov], si_pdf: D, sf_pdf: D, *, periodo: str,
                               sub: dict | None = None) -> bytes:
    """"Movimientos de cuenta" de home banking (el más nuevo arriba): Fecha | Tipo de
    transacción | Débito/Crédito | Monto | Saldo. `sub`: descripción -> texto de un
    subcampo (CUIT) alineado aparte, que termina justo antes de la palabra."""
    textos = [T(40, 760, "Movimientos de cuenta 0000003100099999990012", size=10), T(40, 740, f"Período: {periodo}"),
              T(43, 700, "Saldo inicial:"), T(287.6, 700, "$ " + ar(si_pdf), "der"),
              T(300.5, 700, "Saldo actual:"), T(545.3, 700, "$ " + ar(sf_pdf), "der"),
              T(40, 640, "Fecha"), T(110, 640, "Tipo de transacción"), T(287, 640, "Débito/Crédito"),
              T(426.5, 640, "Monto"), T(524.9, 640, "Saldo")]
    y = 613
    for m in reversed(movs):
        textos += [T(40, y, m.fecha.strftime("%d/%m/%Y")), T(110, y, m.descripcion), T(310, y, _dc(m)),
                   T(457.6, y, "$ " + ar(m.monto), "der"), T(555.3, y, "$ " + ar(m.saldo), "der")]
        if sub and m.descripcion in sub:
            textos.append(T(236, y, sub[m.descripcion]))
        y -= 16.7
    return pdf([textos])


UN_DIA = date(2026, 9, 15)


@pytest.mark.parametrize("items", [
    [("CRÉDITO POR TRANSFERENCIA", D("50000.00")), ("Debito Transf. HB", D("-10000.00")),
     ("Debito Transf. HB", D("-10000.00")), ("Imp. Ley 25413 s/débitos", D("-120.00")),
     ("PAGO SERVICIOS", D("-3500.00"))],
    [("CRÉDITO POR TRANSFERENCIA", D("5000.00")), ("CRÉDITO POR TRANSFERENCIA", D("5000.00")),
     ("Debito Transf. HB", D("-12000.00")), ("Imp. Ley 25413 s/débitos", D("-72.00"))],
], ids=["debitos_iguales", "creditos_iguales"])
@pytest.mark.parametrize("si_bien", [True, False], ids=["saldo_inicial_bien", "saldo_inicial_de_otra_fecha"])
def test_resumen_de_un_solo_dia_con_dos_importes_iguales_seguidos(items, si_bien):
    """Los "Últimos movimientos" de un día del home banking: todas las filas con la
    misma fecha, el más nuevo arriba, la columna Débito/Crédito y saldo en cada
    fila, con dos importes iguales seguidos. Las fechas no dicen el orden: lo dice
    cómo se mueve el saldo. Se lee al revés de arriba, la columna da el signo y
    ninguna fila se da vuelta (antes se leía de arriba a abajo y la palabra se
    tiraba por "no seguir" al saldo). Con el saldo inicial del cuadro de otra
    fecha, lo que no coincide es ese saldo: solo la fila más vieja queda marcada."""
    si = D("250000.00")
    movs = con_saldos(si, [(UN_DIA, d, m) for d, m in items])
    si_pdf = si if si_bien else si + D("15000.00")

    r = leer_extracto_pdf(_movimientos_de_un_resumen(movs, si_pdf, movs[-1].saldo,
                                                     periodo="15/09/2026 al 15/09/2026"), hoy=HOY)

    assert r["orden"] == "desc"
    assert_movs(r, list(reversed(movs)))
    assert r["cuadre"]["cierra"] is si_bien
    assert [m["motivos"] for m in r["movimientos"]] == [[]] * (len(movs) - 1) + [[] if si_bien else ["El saldo no sigue"]]
    if not si_bien:
        aviso = next(a["mensaje"] for a in r["alertas"] if a["codigo"] == "no_cierra")
        assert aviso.startswith("Los movimientos cierran entre sí, pero el saldo inicial")


def test_dos_reversos_con_el_menos_y_credito_no_tiran_la_columna_que_el_saldo_confirma():
    """Columna Débito/Crédito con el importe sin signo y saldo en cada fila; el
    banco imprime dos anulaciones de transferencias recibidas como "-$ X" con la
    palabra "Crédito". El saldo de cada fila confirma lo que dice la columna
    (también en los débitos sin "-"): la columna sigue siendo el signo, los dos
    reversos quedan como débitos para revisar y ningún débito pasa a crédito."""
    movs = con_saldos(D("50000.00"), [
        (date(2026, 9, 1), "CREDITO POR TRANSFERENCIA", D("15000.00")),
        (date(2026, 9, 2), "ANULACION TRANSFERENCIA RECIBIDA", D("-15000.00")),
        (date(2026, 9, 3), "COMISION MANTENIMIENTO", D("-1200.00")),
        (date(2026, 9, 4), "PAGO PROVEEDOR", D("-8000.00")),
        (date(2026, 9, 5), "CREDITO POR TRANSFERENCIA", D("4000.00")),
        (date(2026, 9, 8), "ANULACION TRANSFERENCIA RECIBIDA ", D("-4000.00")),
        (date(2026, 9, 9), "DEBITO AUTOMATICO SEGURO", D("-2100.00")),
        (date(2026, 9, 10), "DEPOSITO EFECTIVO", D("30000.00")),
    ])
    anulaciones = {"ANULACION TRANSFERENCIA RECIBIDA": "Crédito", "ANULACION TRANSFERENCIA RECIBIDA ": "Crédito"}

    r = leer_extracto_pdf(_signo_con_menos(movs, D("50000.00"), menos=anulaciones), hoy=HOY)

    assert_movs(r, movs)
    assert r["cuadre"]["cierra"]
    assert [m["dudosa"] for m in r["movimientos"]] == [False, True, False, False, False, True, False, False]
    assert r["movimientos"][1]["motivos"] == [SIGNO_IMPRESO]


def _medio_de_pago_sin_saldo_por_fila(movs: list[Mov], si: D | None) -> bytes:
    """Fecha | Descripción | Medio de pago | Importe (el "-" en los débitos), sin
    saldo por fila: con `si`, solo "SALDO ANTERIOR" y "SALDO FINAL"; sin `si`,
    ningún saldo."""
    textos = [T(40, 800, "Detalle de movimientos", size=12), T(40, 785, "Período: 01/09/2026 al 30/09/2026"),
              T(40, 760, "Fecha"), T(100, 760, "Descripción"), T(270, 760, "Medio de pago"),
              T(470, 760, "Importe", "der")]
    y = 760
    if si is not None:
        y -= 14
        textos += [T(100, y, "SALDO ANTERIOR"), T(470, y, ar(si), "der")]
    for m in movs:
        y -= 12
        textos += [T(40, y, m.fecha.strftime("%d/%m/%Y")), T(100, y, m.descripcion), T(270, y, m.extra[0]),
                   T(470, y, ("-" if m.monto < 0 else "") + ar(m.monto), "der")]
    if si is not None:
        y -= 14
        textos += [T(100, y, "SALDO FINAL"), T(470, y, ar(movs[-1].saldo), "der")]
    return pdf([textos])


@pytest.mark.parametrize("si", [D("150000.00"), None], ids=["saldo_anterior_y_final", "sin_ningun_saldo"])
@pytest.mark.parametrize("medio_comision", ["Crédito", "Dinero en cuenta"])
def test_medio_de_pago_sin_saldo_por_fila_no_es_el_signo(si, medio_comision):
    """Listado de cobros de un comercio sin saldo por fila: los débitos traen el
    "-" impreso y la columna "Medio de pago" dice con qué tarjeta se cobró
    ("Débito" en ventas, que son créditos). Sin saldo con qué comparar, manda el
    "-": la columna no es el signo, las ventas con débito no se dan vuelta, nada
    queda dudoso por el medio y el medio no se pega a la descripción."""
    movs = [Mov(m.fecha, m.descripcion, m.monto, m.saldo, list(m.extra)) for m in MOVS_MEDIO]
    movs[2].extra[0] = medio_comision                  # la comisión: "Crédito" o "Dinero en cuenta"

    r = leer_extracto_pdf(_medio_de_pago_sin_saldo_por_fila(movs, si), hoy=HOY)

    assert_movs(r, movs, con_saldo=False)
    assert [m["descripcion"] for m in r["movimientos"]] == [m.descripcion for m in movs]
    assert not any(m["dudosa"] for m in r["movimientos"])
    assert r["cuadre"]["cierra"] is (si is not None)


@pytest.mark.parametrize("con_molde", [False, True], ids=["automatico", "formato_aprendido"])
def test_cuit_entre_la_descripcion_y_la_palabra_debito_credito_queda_en_la_descripcion(con_molde):
    """Algunas descripciones traen el CUIT de la contraparte alineado aparte, con
    un hueco ancho, y termina justo antes de "Débito"/"Crédito": cae en la columna
    del signo. No es la marca, pero es de la descripción (y es lo que más pesa al
    conciliar): no se pierde, con la lectura automática ni con el formato aprendido
    el mes anterior."""
    moldes = []
    if con_molde:
        mes1 = con_saldos(D("880000.00"), [
            (date(2026, 9, 1), "CRÉDITO POR TRANSFERENCIA", D("76000.00")),
            (date(2026, 9, 2), "Debito Transf. HB", D("-400000.00")),
            (date(2026, 9, 3), "CRÉDITO POR CREDIN", D("123456.78")),
            (date(2026, 9, 4), "Imp. Ley 25413 s/débitos", D("-1500.00")),
        ])
        r1 = leer_extracto_pdf(_movimientos_de_un_resumen(mes1, D("880000.00"), mes1[-1].saldo,
                                                          periodo="01/09/2026 al 30/09/2026"), hoy=HOY)
        moldes = [{"id": 7, "banco_clave": r1["aprendizaje"]["banco_clave"], "firma": r1["aprendizaje"]["firma"],
                   "layout": r1["aprendizaje"]["layout"]}]
    si = D("677949.18")
    movs = con_saldos(si, [
        (date(2026, 10, 1), "Transf. recibida", D("5000.00")),
        (date(2026, 10, 2), "Debito Transf. HB", D("-800.00")),
        (date(2026, 10, 3), "SIRCREB", D("-0.50")),
        (date(2026, 10, 6), "Transf. recibida ", D("250.00")),
    ])
    sub = {"Transf. recibida": "20-11111111-2", "Debito Transf. HB": "30-22222222-3", "Transf. recibida ": "27-33333333-4"}

    r = leer_extracto_pdf(_movimientos_de_un_resumen(movs, si, movs[-1].saldo, periodo="01/10/2026 al 31/10/2026",
                                                     sub=sub), moldes=moldes, hoy=date(2026, 11, 16))

    assert r["metodo"] == ("molde" if con_molde else "automatico")
    assert_movs(r, list(reversed(movs)))
    assert [m["descripcion"] for m in r["movimientos"]] == [
        f"{m.descripcion.strip()} {sub[m.descripcion]}" if m.descripcion in sub else m.descripcion
        for m in reversed(movs)
    ]
    assert r["cuadre"]["cierra"]


@pytest.mark.parametrize("font,espacios,letras", [
    ("Courier", 2, ("C", "D")), ("Courier", 2, ("CR", "DB")), ("Helvetica", 3, ("C", "D")),
    ("Helvetica", 4, ("C", "D")),
], ids=["courier_2", "courier_2_crdb", "helvetica_3", "helvetica_4"])
def test_marca_d_o_c_a_unos_espacios_del_importe_sin_saldo_por_fila(font, espacios, letras):
    """Resumen con la marca en una columna fija a dos o más espacios del importe
    ("1.500,00  D", letra monoespaciada o no), sin saldo por fila: la marca sigue
    siendo la del importe, da el signo y cierra con el saldo anterior y el final
    (antes solo se aceptaba pegada y todas las filas quedaban sin confirmar)."""
    si = D("10000.00")
    movs = con_saldos(si, [
        (date(2026, 9, 1), "DEPOSITO EFECTIVO", D("2000.00")),
        (date(2026, 9, 2), "PAGO TARJETA", D("-1500.00")),
        (date(2026, 9, 5), "COMISION", D("-120.50")),
        (date(2026, 9, 7), "TRANSFERENCIA RECIBIDA", D("830.00")),
        (date(2026, 9, 9), "PAGO SERVICIO", D("-640.00")),
    ])

    def t(x, y, texto, alin="izq"):
        return T(x, y, texto, alin, font=font)
    textos = [t(40, 800, "Resumen de cuenta - Período 01/09/2026 al 30/09/2026"), t(40, 770, "Fecha"),
              t(110, 770, "Concepto"), t(470, 770, "Importe", "der"), t(110, 756, "SALDO ANTERIOR"),
              t(470, 756, ar(si), "der")]
    y = 756
    for m in movs:
        y -= 12
        letra = letras[0] if m.monto > 0 else letras[1]
        hueco = " " * espacios + letra
        textos += [t(40, y, m.fecha.strftime("%d/%m/%Y")), t(110, y, m.descripcion),
                   t(470 + stringWidth(hueco, font, 8), y, ar(m.monto) + hueco, "der")]
    y -= 14
    textos += [t(110, y, "SALDO FINAL"), t(470, y, ar(movs[-1].saldo), "der")]

    r = leer_extracto_pdf(pdf([textos]), hoy=HOY)

    assert_movs(r, movs, con_saldo=False)
    assert r["cuadre"]["cierra"]
    assert not any(m["dudosa"] for m in r["movimientos"])


@pytest.mark.parametrize("titulo", ["Tipo", "Mov."])
def test_columna_sin_titulo_de_signo_con_codigos_db_cr_es_el_signo(titulo):
    """Columna "Tipo" (o "Mov.") que solo dice "DB" o "CR", importe sin signo y sin
    saldo por fila (solo saldo anterior y final): los códigos son el signo (no
    hay otra cosa en la columna, como pasa con un canal que también dice "RV" o
    "AJ") y cierra."""
    si = D("10000.00")
    movs = con_saldos(si, [
        (date(2026, 9, 1), "DEPOSITO EFECTIVO", D("2000.00")),
        (date(2026, 9, 2), "PAGO TARJETA", D("-1500.00")),
        (date(2026, 9, 5), "COMISION", D("-120.50")),
        (date(2026, 9, 7), "TRANSFERENCIA RECIBIDA", D("830.00")),
        (date(2026, 9, 9), "PAGO SERVICIO", D("-640.00")),
        (date(2026, 9, 12), "INTERESES", D("15.30")),
    ])
    textos = [T(40, 800, "Resumen de cuenta - Período 01/09/2026 al 30/09/2026"), T(40, 770, "Fecha"),
              T(100, 770, "Concepto"), T(330, 770, titulo), T(470, 770, "Importe", "der"),
              T(100, 756, "SALDO ANTERIOR"), T(470, 756, ar(si), "der")]
    y = 756
    for m in movs:
        y -= 12
        textos += [T(40, y, m.fecha.strftime("%d/%m/%Y")), T(100, y, m.descripcion),
                   T(330, y, "CR" if m.monto > 0 else "DB"), T(470, y, ar(m.monto), "der")]
    y -= 14
    textos += [T(100, y, "SALDO FINAL"), T(470, y, ar(movs[-1].saldo), "der")]

    r = leer_extracto_pdf(pdf([textos]), hoy=HOY)

    assert_movs(r, movs, con_saldo=False)
    assert r["cuadre"]["cierra"]
    assert not any(m["dudosa"] for m in r["movimientos"])
    assert [m["descripcion"] for m in r["movimientos"]] == [m.descripcion for m in movs]
