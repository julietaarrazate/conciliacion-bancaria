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
from reportlab.lib.pagesizes import A4
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
