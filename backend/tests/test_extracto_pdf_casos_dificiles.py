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
from reportlab.pdfgen import canvas

from app.services.extracto_pdf import leer_extracto_pdf
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
