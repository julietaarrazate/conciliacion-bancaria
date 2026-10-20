"""Tests del lector de extractos PDF (`app.services.extracto_pdf`).

Los PDF se generan en el momento con reportlab, dibujando cada celda en una
posición fija (como los arman los bancos), así no se versionan binarios. La IA
nunca se llama de verdad: se reemplaza `ia.lector_ia` con monkeypatch.
"""

from __future__ import annotations

import io
import random
import secrets
import time
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal as D
from typing import Optional

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from app.services.extracto_pdf import ExtractoPdfError, leer_extracto_pdf, validar_saldos
from app.services.extracto_pdf import ia as ia_mod
from app.services.extracto_pdf.bancos import detectar_banco_texto, detectar_banco_zonas
from app.services.extracto_pdf.fechas import armar_contexto, detectar_periodo, parsear_fecha
from app.services.extracto_pdf.saldos import formatear_pesos, marcar_dudosas
from app.services.extracto_pdf.tabla import es_importe

HOY = date(2026, 10, 16)


@pytest.fixture(autouse=True)
def _sin_ia(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    def _prohibido(mime, contenido):  # pragma: no cover - si se llama, el test falla
        raise AssertionError("No se debía llamar a la IA")

    monkeypatch.setattr(ia_mod, "lector_ia", _prohibido)


# ── Generación de PDF ───────────────────────────────────────────────────────

def ar(v: D, estilo: str = "menos") -> str:
    """Decimal → "1.234,56" con el estilo de signo pedido para negativos."""
    s = f"{abs(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if v >= 0:
        return s
    return {"menos": "-" + s, "atras": s + "-", "parentesis": f"({s})", "sin": s}[estilo]


@dataclass
class Col:
    titulo: str
    x: float
    alin: str = "izq"            # "izq": x es el borde izquierdo; "der": el derecho; "centro"
    titulo_x: Optional[float] = None       # el título puede ir en otro lugar (p. ej. centrado)
    titulo_alin: Optional[str] = None


@dataclass
class Fila:
    celdas: list[str]
    extra: list[str] = field(default_factory=list)   # renglones de continuación (columna descripción)


def _dibujar(c, x: float, y: float, texto: str, alin: str, size: float, por_palabra: bool):
    if not texto:
        return
    if not por_palabra:
        {"der": c.drawRightString, "centro": c.drawCentredString}.get(alin, c.drawString)(x, y, texto)
        return
    # Cada palabra en su posición, sin caracteres de espacio (como muchos PDF de bancos).
    palabras = texto.split(" ")
    hueco = 0.28 * size
    ancho = sum(stringWidth(p, "Helvetica", size) for p in palabras) + hueco * (len(palabras) - 1)
    cx = x - ancho if alin == "der" else x
    for p in palabras:
        c.drawString(cx, y, p)
        cx += stringWidth(p, "Helvetica", size) + hueco


def pdf_extracto(
    columnas: list[Col],
    filas: list[Fila],
    *,
    membrete: tuple[str, ...] = (),
    por_pagina: int = 40,
    repetir_encabezado: bool = True,
    cabecera: Optional[str] = None,
    pie: bool = True,
    transporte: bool = False,
    col_desc: int = 1,
    col_saldo: int = -1,
    size: float = 9,
    por_palabra: bool = False,
    encrypt=None,
    rotulo_transporte: str = "TRANSPORTE",
) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4, encrypt=encrypt)
    paginas = [filas[i:i + por_pagina] for i in range(0, len(filas), por_pagina)] or [[]]
    total = len(paginas)
    ultimo_saldo = ""
    for n, pagina in enumerate(paginas, start=1):
        c.setFont("Helvetica", size)
        y = 805.0
        if cabecera:
            c.drawString(40, 820, cabecera)
        if n == 1:
            for i, t in enumerate(membrete):
                c.setFont("Helvetica-Bold" if i == 0 else "Helvetica", size + (3 if i == 0 else 0))
                c.drawString(40, y, t)
                y -= 15
            c.setFont("Helvetica", size)
            y -= 10
        if n == 1 or repetir_encabezado:
            c.setFont("Helvetica-Bold", size)
            for col in columnas:
                _dibujar(c, col.titulo_x if col.titulo_x is not None else col.x, y, col.titulo,
                         col.titulo_alin or col.alin, size, por_palabra and col.titulo_alin != "centro")
            c.setFont("Helvetica", size)
            y -= 16
        if transporte and n > 1:
            _dibujar(c, columnas[col_desc].x, y, rotulo_transporte, "izq", size, por_palabra)
            _dibujar(c, columnas[col_saldo].x, y, ultimo_saldo, columnas[col_saldo].alin, size, por_palabra)
            y -= 12
        for fila in pagina:
            for col, texto in zip(columnas, fila.celdas):
                _dibujar(c, col.x, y, texto, col.alin, size, por_palabra)
            if fila.celdas[col_saldo]:
                ultimo_saldo = fila.celdas[col_saldo]
            y -= 12
            for extra in fila.extra:
                _dibujar(c, columnas[col_desc].x, y, extra, "izq", size, por_palabra)
                y -= 12
        if transporte and n < total:
            _dibujar(c, columnas[col_desc].x, y, "SUBTOTAL A TRANSPORTAR", "izq", size, por_palabra)
            _dibujar(c, columnas[col_saldo].x, y, ultimo_saldo, columnas[col_saldo].alin, size, por_palabra)
        if pie:
            c.drawString(40, 30, f"Página {n} de {total}")
            c.drawString(300, 30, "Los depósitos en pesos están garantizados hasta $ 25.000.000.")
        c.showPage()
    c.save()
    return buf.getvalue()


@dataclass
class Mov:
    fecha: date
    descripcion: str
    monto: D
    saldo: D
    extra: list[str] = field(default_factory=list)


def con_saldos(saldo_inicial: D, items: list[tuple]) -> list[Mov]:
    """items = [(fecha, descripcion, monto[, extra])] en orden cronológico."""
    saldo = saldo_inicial
    out = []
    for it in items:
        saldo += it[2]
        out.append(Mov(it[0], it[1], it[2], saldo, list(it[3]) if len(it) > 3 else []))
    return out


def movimientos_generados(n: int, desde: date, saldo_inicial: D = D("100000.00")) -> list[Mov]:
    items = []
    for i in range(n):
        fecha = desde + timedelta(days=i * 28 // max(n, 1))
        monto = D(1000 + (i * 7919) % 90000) / 100 * (1 if i % 3 else -1) + (D("1234.00") if i % 5 == 0 else 0)
        items.append((fecha, f"TRANSFERENCIA {i:04d} CLIENTE SA", monto.quantize(D("0.01"))))
    return con_saldos(saldo_inicial, items)


def assert_movs(resultado: dict, esperados: list[Mov], *, con_saldo: bool = True):
    leidos = resultado["movimientos"]
    assert len(leidos) == len(esperados), [(m["fecha"], m["monto"]) for m in leidos]
    for m, e in zip(leidos, esperados):
        assert m["fecha"] == e.fecha
        assert m["monto"] == e.monto
        if con_saldo:
            assert m["saldo"] == e.saldo
        assert isinstance(m["monto"], D)


def cols_galicia() -> list[Col]:
    return [Col("Fecha", 40), Col("Descripción", 90), Col("Origen", 300),
            Col("Crédito", 420, "der"), Col("Débito", 490, "der"), Col("Saldo", 560, "der")]


def filas_galicia(movs: list[Mov], saldo_inicial: Optional[D]) -> list[Fila]:
    filas = []
    if saldo_inicial is not None:
        filas.append(Fila(["", "SALDO ANTERIOR", "", "", "", ar(saldo_inicial)]))
    for m in movs:
        filas.append(Fila(
            [m.fecha.strftime("%d/%m/%y"), m.descripcion, "Web",
             ar(m.monto) if m.monto > 0 else "", ar(-m.monto) if m.monto < 0 else "", ar(m.saldo)],
            m.extra,
        ))
    return filas


MEMBRETE_GALICIA = (
    "Banco de Galicia y Buenos Aires S.A.U.",
    "Tte. Gral. Perón 430 - Ciudad Autónoma de Buenos Aires - Provincia de Buenos Aires",
    "Resumen de cuenta corriente en pesos - CBU 0070999020000012345678",
    "Período: 01/09/2026 al 30/09/2026",
)


def galicia_sep(saldo_inicial: D = D("150000.00")) -> list[Mov]:
    return con_saldos(saldo_inicial, [
        (date(2026, 9, 1), "TRANSFERENCIA RECIBIDA", D("25000.50"), ["DE PEREZ JUAN CUIT 20123456789"]),
        (date(2026, 9, 2), "PAGO SERVICIOS ELECTRICIDAD", D("-12345.67")),
        (date(2026, 9, 2), "COMISION MANTENIMIENTO CUENTA", D("-1500.00")),
        (date(2026, 9, 5), "DEPOSITO EN EFECTIVO", D("100000.00"), ["SUCURSAL 123", "CAJA 4"]),
        (date(2026, 9, 10), "IMP. LEY 25413 DEBITO", D("-74.07")),
        (date(2026, 9, 15), "TRANSFERENCIA A TERCEROS", D("-1234567.89"), ["A BANCO NACION CBU 0110599520000001234567"]),
        (date(2026, 9, 20), "ACREDITACION HABERES", D("1300000.00")),
        (date(2026, 9, 30), "INTERESES", D("0.99")),
    ])


# ── (a) Galicia: Crédito antes que Débito, "Saldo anterior", multi-renglón ──

def test_galicia_lectura_automatica_cierra():
    movs = galicia_sep()
    contenido = pdf_extracto(cols_galicia(), filas_galicia(movs, D("150000.00")), membrete=MEMBRETE_GALICIA)
    r = leer_extracto_pdf(contenido, hoy=HOY)

    assert r["metodo"] == "automatico"
    assert r["banco_clave"] == "galicia"
    assert r["orden"] == "asc"
    assert r["paginas"] == 1 and r["escaneado"] is False
    assert (r["periodo_desde"], r["periodo_hasta"]) == (date(2026, 9, 1), date(2026, 9, 30))
    assert_movs(r, movs)
    assert r["saldo_inicial"] == D("150000.00")
    assert r["cuadre"]["saldo_inicial_inferido"] is False
    assert r["cuadre"]["cierra"] is True
    assert r["cuadre"]["diferencia"] == D("0.00")
    assert r["saldo_final"] == movs[-1].saldo
    assert r["cuadre"]["total_creditos"] == sum((m.monto for m in movs if m.monto > 0), D("0"))
    assert r["cuadre"]["total_debitos"] == -sum((m.monto for m in movs if m.monto < 0), D("0"))
    assert not any(m["dudosa"] for m in r["movimientos"])
    # Los renglones de continuación se suman a la descripción (CUIT/CBU para conciliar).
    assert r["movimientos"][0]["descripcion"] == "TRANSFERENCIA RECIBIDA DE PEREZ JUAN CUIT 20123456789"
    assert r["movimientos"][3]["descripcion"] == "DEPOSITO EN EFECTIVO SUCURSAL 123 CAJA 4"
    assert "0110599520000001234567" in r["movimientos"][5]["descripcion"]
    # "Origen" (canal) no ensucia la descripción.
    assert "Web" not in r["movimientos"][1]["descripcion"]
    assert r["aprendizaje"] is not None
    assert r["aprendizaje"]["banco_clave"] == "galicia"
    assert len(r["aprendizaje"]["firma"]) == 64
    assert r["ia_usada"] is False and r["ia_disponible"] is False
    assert [a for a in r["alertas"] if a["nivel"] != "info"] == []


def test_galicia_palabras_sin_espacios():
    """PDF que posiciona cada palabra suelta (sin caracteres de espacio)."""
    movs = galicia_sep()
    contenido = pdf_extracto(cols_galicia(), filas_galicia(movs, D("150000.00")), membrete=MEMBRETE_GALICIA,
                             por_palabra=True)
    r = leer_extracto_pdf(contenido, hoy=HOY)
    assert r["metodo"] == "automatico"
    assert_movs(r, movs)
    assert r["cuadre"]["cierra"]
    assert r["movimientos"][1]["descripcion"] == "PAGO SERVICIOS ELECTRICIDAD"


# ── (b) Santander: Fecha | Comprobante | Movimiento | Débito | Crédito | Saldo ──

def test_santander_comprobante_y_fechas_dd_mm_yy():
    movs = con_saldos(D("5000.00"), [
        (date(2026, 8, 3), "Transferencia recibida de Gomez Ana", D("15000.00")),
        (date(2026, 8, 4), "Pago tarjeta Visa", D("-7500.25")),
        (date(2026, 8, 4), "Debito automatico seguro", D("-3210.00")),
        (date(2026, 8, 18), "Deposito de cheque", D("42000.00")),
        (date(2026, 8, 31), "Impuesto ley 25.413", D("-252.00")),
    ])
    columnas = [Col("Fecha", 40), Col("Comprobante", 90), Col("Movimiento", 170),
                Col("Débito", 400, "der"), Col("Crédito", 470, "der"), Col("Saldo en cuenta", 560, "der")]
    filas = [Fila(["03/08/26", "", "Saldo Inicial", "", "", ar(D("5000.00"))])]
    for i, m in enumerate(movs):
        filas.append(Fila([m.fecha.strftime("%d/%m/%y"), f"{4512300 + i}", m.descripcion,
                           ar(-m.monto) if m.monto < 0 else "", ar(m.monto) if m.monto > 0 else "",
                           ar(m.saldo)]))
    contenido = pdf_extracto(columnas, filas, col_desc=2, membrete=(
        "Banco Santander Argentina S.A.", "Av. Juan de Garay 151 - Ciudad Autónoma de Buenos Aires",
        "Cuenta Corriente en $ Nro 123-456789/0 - Desde: 01/08/2026 Hasta: 31/08/2026",
    ))
    r = leer_extracto_pdf(contenido, hoy=HOY)
    assert r["banco_clave"] == "santander"
    assert r["metodo"] == "automatico"
    assert_movs(r, movs)
    assert r["cuadre"]["cierra"] and r["cuadre"]["saldo_inicial"] == D("5000.00")
    # El número de comprobante queda en la descripción (puntaje de referencia del motor).
    assert r["movimientos"][0]["descripcion"] == "Transferencia recibida de Gomez Ana 4512300"
    assert (r["periodo_desde"], r["periodo_hasta"]) == (date(2026, 8, 1), date(2026, 8, 31))


def test_titulos_centrados_sobre_columnas_anchas():
    """Los títulos de texto centrados (Jasper/Crystal) no corren las columnas."""
    movs = con_saldos(D("5000.00"), [
        (date(2026, 8, 3), "Transferencia recibida de Gomez Ana", D("15000.00")),
        (date(2026, 8, 4), "Pago tarjeta Visa", D("-7500.25")),
        (date(2026, 8, 18), "Deposito de cheque en sucursal", D("42000.00")),
    ])
    columnas = [Col("Fecha", 40, titulo_x=58, titulo_alin="centro"),
                Col("Comprobante", 92, titulo_x=125, titulo_alin="centro"),
                Col("Movimiento", 165, titulo_x=280, titulo_alin="centro"),
                Col("Débito", 420, "der", titulo_x=395, titulo_alin="centro"),
                Col("Crédito", 490, "der", titulo_x=465, titulo_alin="centro"),
                Col("Saldo", 560, "der", titulo_x=535, titulo_alin="centro")]
    filas = [Fila([m.fecha.strftime("%d/%m/%y"), f"{4512300 + i}", m.descripcion,
                   ar(-m.monto) if m.monto < 0 else "", ar(m.monto) if m.monto > 0 else "", ar(m.saldo)])
             for i, m in enumerate(movs)]
    contenido = pdf_extracto(columnas, filas, col_desc=2, membrete=("Banco Santander Argentina S.A.",))
    r = leer_extracto_pdf(contenido, hoy=HOY)
    assert r["metodo"] == "automatico"
    assert_movs(r, movs)
    assert [m["descripcion"] for m in r["movimientos"]] == [
        f"{m.descripcion} {4512300 + i}" for i, m in enumerate(movs)
    ]


# ── (c) Importe único con signo explícito (3 estilos) + Saldo, más nuevo primero ──

def test_importe_con_signos_explicitos_orden_descendente():
    movs = con_saldos(D("80000.00"), [
        (date(2026, 9, 1), "CREDITO TRANSFERENCIA", D("1000.00")),
        (date(2026, 9, 3), "DEBITO TARJETA", D("-2345.67")),
        (date(2026, 9, 4), "PAGO AFIP VEP", D("-10000.00")),
        (date(2026, 9, 8), "DEBITO PRESTAMO", D("-555.55")),
        (date(2026, 9, 12), "ACREDITACION", D("70000.00")),
        (date(2026, 9, 20), "COMISION", D("-99.99")),
    ])
    estilos = ["menos", "atras", "parentesis"]
    columnas = [Col("Fecha", 40), Col("Concepto", 100), Col("Importe", 450, "der"), Col("Saldo", 550, "der")]
    filas = []
    for i, m in enumerate(reversed(movs)):            # el PDF lista del más nuevo al más viejo
        filas.append(Fila([m.fecha.strftime("%d/%m/%Y"), m.descripcion, ar(m.monto, estilos[i % 3]),
                           ar(m.saldo)]))
    contenido = pdf_extracto(columnas, filas, membrete=(
        "Banco de la Provincia de Buenos Aires", "Resumen de movimientos - Septiembre 2026",
    ))
    r = leer_extracto_pdf(contenido, hoy=HOY)
    assert r["banco_clave"] == "provincia"
    assert r["orden"] == "desc"
    assert_movs(r, list(reversed(movs)))
    assert r["cuadre"]["cierra"]
    assert r["cuadre"]["saldo_inicial"] == D("80000.00") and r["cuadre"]["saldo_inicial_inferido"]
    assert r["saldo_final"] == movs[-1].saldo
    assert (r["periodo_desde"], r["periodo_hasta"]) == (date(2026, 9, 1), date(2026, 9, 30))


# ── (d) Encabezado con palabras desconocidas → lectura estructural ──────────

def test_encabezado_desconocido_cae_en_lectura_estructural():
    movs = con_saldos(D("1000.00"), [
        (date(2026, 7, 1), "ALQUILER JULIO", D("-500.00")),
        (date(2026, 7, 2), "COBRO FACTURA 0001-00001234", D("2500.00")),
        (date(2026, 7, 9), "SERVICIO DE LIMPIEZA", D("-320.10")),
        (date(2026, 7, 22), "COBRO FACTURA 0001-00001240", D("1200.00")),
    ])
    # Sin "Fecha" ni palabras conocidas suficientes: el encabezado no se reconoce.
    columnas = [Col("Fch", 40), Col("Texto libre", 100), Col("Valor $", 450, "der"), Col("Acum.", 550, "der")]
    filas = [Fila([m.fecha.strftime("%d/%m/%Y"), m.descripcion, ar(m.monto), ar(m.saldo)]) for m in movs]
    contenido = pdf_extracto(columnas, filas, membrete=("Cooperativa de Crédito Ejemplo",))
    r = leer_extracto_pdf(contenido, hoy=HOY)
    assert r["metodo"] == "automatico"
    assert r["banco_clave"] == "generico"
    assert_movs(r, movs)
    assert r["cuadre"]["cierra"]
    assert r["aprendizaje"]["layout"]["tipo"] == "estructural"
    assert r["movimientos"][1]["descripcion"] == "COBRO FACTURA 0001-00001234"


# ── (e) 3 páginas: membrete/pie repetidos, encabezado por página, transporte ──

def test_tres_paginas_con_transporte_y_pie():
    movs = movimientos_generados(90, date(2026, 9, 1))
    columnas = [Col("Fecha", 40), Col("Descripción", 90), Col("Referencia", 280),
                Col("Débitos", 420, "der"), Col("Créditos", 490, "der"), Col("Saldo", 560, "der")]
    filas = [Fila(["", "SALDO ANTERIOR", "", "", "", ar(D("100000.00"))])]
    for m in movs:
        filas.append(Fila([m.fecha.strftime("%d/%m/%y"), m.descripcion, "",
                           ar(-m.monto) if m.monto < 0 else "", ar(m.monto) if m.monto > 0 else "",
                           ar(m.saldo)]))
    contenido = pdf_extracto(columnas, filas, por_pagina=31, transporte=True,
                             cabecera="BANCO MACRO S.A. - Resumen de cuenta - CUIT 30-71234567-1",
                             membrete=("Resumen de Cuenta Corriente Especial", "Del 01/09/2026 al 30/09/2026"))
    r = leer_extracto_pdf(contenido, hoy=HOY)
    assert r["paginas"] == 3
    assert r["banco_clave"] == "macro"
    assert_movs(r, movs)
    assert r["cuadre"]["cierra"]
    assert r["saldo_inicial"] == D("100000.00")
    assert {m["pagina"] for m in r["movimientos"]} == {1, 2, 3}
    textos = " ".join(m["descripcion"] for m in r["movimientos"])
    assert "TRANSPORTE" not in textos and "SUBTOTAL" not in textos and "Página" not in textos
    assert "garantizados" not in textos


def test_paginas_sin_encabezado_repetido():
    movs = movimientos_generados(70, date(2026, 9, 1))
    filas = filas_galicia(movs, D("100000.00"))
    contenido = pdf_extracto(cols_galicia(), filas, por_pagina=30, repetir_encabezado=False,
                             membrete=MEMBRETE_GALICIA)
    r = leer_extracto_pdf(contenido, hoy=HOY)
    assert_movs(r, movs)
    assert r["cuadre"]["cierra"]


def test_saldo_anterior_por_pagina_no_corta_la_lectura():
    movs = movimientos_generados(60, date(2026, 9, 1))
    contenido = pdf_extracto(cols_galicia(), filas_galicia(movs, D("100000.00")), por_pagina=25,
                             transporte=True, rotulo_transporte="SALDO ANTERIOR", membrete=MEMBRETE_GALICIA)
    r = leer_extracto_pdf(contenido, hoy=HOY)
    assert_movs(r, movs)
    assert r["cuadre"]["cierra"] and r["saldo_inicial"] == D("100000.00")
    assert "varias_cuentas" not in {a["codigo"] for a in r["alertas"]}


def test_pdf_con_dos_cuentas_lee_solo_la_primera():
    cc = galicia_sep(D("150000.00"))
    ca = con_saldos(D("999.00"), [
        (date(2026, 9, 3), "DEPOSITO CAJA DE AHORRO", D("1.00")),
        (date(2026, 9, 9), "EXTRACCION", D("-500.00")),
    ])
    filas = filas_galicia(cc, D("150000.00"))
    filas.append(Fila(["", "CAJA DE AHORRO EN PESOS NRO 4001234-5 001-9", "", "", "", ""]))
    filas += filas_galicia(ca, D("999.00"))
    contenido = pdf_extracto(cols_galicia(), filas, membrete=MEMBRETE_GALICIA)
    r = leer_extracto_pdf(contenido, hoy=HOY)
    assert_movs(r, cc)
    assert r["cuadre"]["cierra"]
    assert r["saldo_final"] == cc[-1].saldo
    assert "varias_cuentas" in {a["codigo"] for a in r["alertas"]}


def test_icbc_fecha_valor_no_es_importe_y_fechas_dd_mm():
    movs = con_saldos(D("3000.00"), [
        (date(2026, 9, 2), "TRANSF RECIBIDA", D("1000.00")),
        (date(2026, 9, 7), "PAGO PROVEEDOR", D("-2500.00")),
        (date(2026, 9, 29), "INTERESES", D("1.50")),
    ])
    columnas = [Col("Fecha", 40), Col("Concepto", 80), Col("F.Valor", 230), Col("Comprobante", 280),
                Col("Débitos", 430, "der"), Col("Créditos", 495, "der"), Col("Saldos", 560, "der")]
    filas = [Fila(["", "SALDO ANTERIOR", "", "", "", "", ar(D("3000.00"))])]
    filas += [Fila([m.fecha.strftime("%d-%m"), m.descripcion, m.fecha.strftime("%d-%m"), "98765",
                    ar(-m.monto) if m.monto < 0 else "", ar(m.monto) if m.monto > 0 else "", ar(m.saldo)])
              for m in movs]
    contenido = pdf_extracto(columnas, filas, membrete=("ICBC - Industrial and Commercial Bank of China",
                                                        "Período 01/09/2026 - 30/09/2026"))
    r = leer_extracto_pdf(contenido, hoy=HOY)
    assert r["banco_clave"] == "icbc"
    assert_movs(r, movs)
    assert r["cuadre"]["cierra"]
    assert r["movimientos"][0]["descripcion"] == "TRANSF RECIBIDA 98765"


def test_mercado_pago_valor_con_signo_pesos():
    movs = con_saldos(D("0.00"), [
        (date(2026, 9, 1), "Transferencia recibida", D("15000.00")),
        (date(2026, 9, 2), "Pago con QR Supermercado", D("-3456.78")),
        (date(2026, 9, 5), "Rendimientos", D("12.34")),
    ])
    columnas = [Col("Fecha", 40), Col("Descripción", 100), Col("ID de la operación", 280),
                Col("Valor", 470, "der"), Col("Saldo", 560, "der")]
    filas = [Fila([m.fecha.strftime("%d-%m-%Y"), m.descripcion, f"8{i}12345678",
                   f"$ {ar(m.monto)}", f"$ {ar(m.saldo)}"]) for i, m in enumerate(movs)]
    contenido = pdf_extracto(columnas, filas, membrete=("Mercado Pago", "RESUMEN DE CUENTA",
                                                        "Periodo: del 01-09-2026 al 30-09-2026"))
    r = leer_extracto_pdf(contenido, hoy=HOY)
    assert r["banco_clave"] == "mercadopago"
    assert_movs(r, movs)
    assert r["cuadre"]["cierra"] and r["cuadre"]["saldo_inicial"] == D("0.00")
    assert r["movimientos"][1]["descripcion"] == "Pago con QR Supermercado 8112345678"


def test_movimientos_que_empiezan_con_saldo_o_total_no_se_pierden():
    movs = con_saldos(D("500.00"), [
        (date(2026, 9, 2), "SALDO DEUDOR INTERESES", D("-10.00")),
        (date(2026, 9, 3), "TOTAL DISTRIBUIDORA SA PAGO", D("-90.00")),
        (date(2026, 9, 4), "SALDO A FAVOR AFIP", D("100.00")),
    ])
    filas = filas_galicia(movs, D("500.00"))
    filas.append(Fila(["", "TOTAL DEBITOS", "", "", ar(D("100.00")), ""]))
    filas.append(Fila(["", "SALDO PROMEDIO DEL PERIODO", "", "", "", ar(D("480.00"))]))
    contenido = pdf_extracto(cols_galicia(), filas, membrete=MEMBRETE_GALICIA)
    r = leer_extracto_pdf(contenido, hoy=HOY)
    assert_movs(r, movs)
    assert r["cuadre"]["cierra"]


def test_descendente_con_saldo_anterior_al_pie():
    movs = galicia_sep(D("150000.00"))
    filas = [Fila(["", "SALDO FINAL", "", "", "", ar(movs[-1].saldo)])]
    filas += list(reversed(filas_galicia(movs, None)))
    filas.append(Fila(["", "SALDO ANTERIOR", "", "", "", ar(D("150000.00"))]))
    contenido = pdf_extracto(cols_galicia(), filas, membrete=MEMBRETE_GALICIA)
    r = leer_extracto_pdf(contenido, hoy=HOY)
    assert r["orden"] == "desc"
    assert [(m["fecha"], m["monto"]) for m in r["movimientos"]] == [(m.fecha, m.monto) for m in reversed(movs)]
    assert r["saldo_inicial"] == D("150000.00") and not r["cuadre"]["saldo_inicial_inferido"]
    assert r["saldo_final"] == movs[-1].saldo and not r["cuadre"]["saldo_final_inferido"]
    assert r["cuadre"]["cierra"]
    assert "varias_cuentas" not in {a["codigo"] for a in r["alertas"]}


# ── (f) Fechas sin año + período que cruza diciembre → enero ───────────────

def test_fechas_sin_anio_con_cruce_de_anio():
    movs = con_saldos(D("20000.00"), [
        (date(2025, 12, 16), "PAGO PROVEEDOR", D("-1500.00")),
        (date(2025, 12, 23), "COBRO CLIENTE", D("8000.00")),
        (date(2025, 12, 31), "COMISION", D("-120.00")),
        (date(2026, 1, 2), "COBRO CLIENTE", D("3000.00")),
        (date(2026, 1, 14), "PAGO SUELDOS", D("-9000.00")),
    ])
    columnas = [Col("FECHA", 40), Col("ORIGEN", 85), Col("CONCEPTO", 150),
                Col("DÉBITO", 420, "der"), Col("CRÉDITO", 490, "der"), Col("SALDO", 560, "der")]
    filas = [Fila(["", "", "SALDO ANTERIOR", "", "", ar(D("20000.00"))])]
    filas += [Fila([m.fecha.strftime("%d/%m"), "0001", m.descripcion, ar(-m.monto) if m.monto < 0 else "",
                    ar(m.monto) if m.monto > 0 else "", ar(m.saldo)]) for m in movs]
    contenido = pdf_extracto(columnas, filas, col_desc=2, membrete=(
        "BBVA Argentina S.A.", "Av. Córdoba 111 - Provincia de Buenos Aires",
        "Período: 15/12/2025 al 14/01/2026",
    ))
    r = leer_extracto_pdf(contenido, hoy=HOY)
    assert r["banco_clave"] == "bbva"
    assert_movs(r, movs)
    assert r["cuadre"]["cierra"]
    assert not any(a["codigo"] == "anio_supuesto" for a in r["alertas"])


def test_fechas_sin_anio_ni_periodo_usa_hoy_sin_futuro():
    movs = con_saldos(D("1000.00"), [
        (date(2025, 12, 28), "COBRO", D("100.00")),
        (date(2026, 1, 3), "PAGO", D("-50.00")),
    ])
    filas = [Fila([m.fecha.strftime("%d/%m"), m.descripcion, "", ar(m.monto) if m.monto > 0 else "",
                   ar(-m.monto) if m.monto < 0 else "", ar(m.saldo)]) for m in movs]
    contenido = pdf_extracto(cols_galicia(), filas)
    r = leer_extracto_pdf(contenido, hoy=date(2026, 1, 20))
    assert_movs(r, movs)
    assert any(a["codigo"] == "anio_supuesto" for a in r["alertas"])


# ── (g) Importes sin signo ni columnas débito/crédito: signo por el saldo ───

def test_signo_deducido_del_saldo_incluso_sin_saldo_en_cada_fila():
    movs = con_saldos(D("10000.00"), [
        (date(2026, 9, 1), "DEPOSITO", D("5000.00")),
        (date(2026, 9, 1), "EXTRACCION CAJERO", D("-2000.00")),
        (date(2026, 9, 2), "PAGO SERVICIO", D("-750.50")),
        (date(2026, 9, 2), "COBRO", D("300.00")),
        (date(2026, 9, 2), "COMISION", D("-12.10")),
        (date(2026, 9, 3), "TRANSFERENCIA", D("-1000.00")),
    ])
    columnas = [Col("Fecha", 40), Col("Descripción", 100), Col("Importe", 450, "der"), Col("Saldo", 550, "der")]
    filas = [Fila(["", "SALDO ANTERIOR", "", ar(D("10000.00"))])]
    for i, m in enumerate(movs):
        ultimo_del_dia = i == len(movs) - 1 or movs[i + 1].fecha != m.fecha
        filas.append(Fila([m.fecha.strftime("%d/%m/%Y"), m.descripcion, ar(m.monto, "sin"),
                           ar(m.saldo) if ultimo_del_dia else ""]))
    contenido = pdf_extracto(columnas, filas)
    r = leer_extracto_pdf(contenido, hoy=HOY)
    assert [m["monto"] for m in r["movimientos"]] == [m.monto for m in movs]
    assert r["cuadre"]["cierra"]
    assert not any(m["dudosa"] for m in r["movimientos"])
    assert any(a["codigo"] == "signo_deducido" for a in r["alertas"])


def _pdf_un_saldo_por_dia(movs: list[Mov], saldo_inicial: D) -> bytes:
    columnas = [Col("Fecha", 40), Col("Descripción", 100), Col("Importe", 450, "der"), Col("Saldo", 550, "der")]
    filas = [Fila(["", "SALDO ANTERIOR", "", ar(saldo_inicial)])]
    for i, m in enumerate(movs):
        ultimo_del_dia = i == len(movs) - 1 or movs[i + 1].fecha != m.fecha
        filas.append(Fila([m.fecha.strftime("%d/%m/%Y"), m.descripcion, ar(m.monto, "sin"),
                           ar(m.saldo) if ultimo_del_dia else ""]))
    return pdf_extracto(columnas, filas)


def test_signo_deducido_con_muchas_filas_y_un_solo_saldo_por_dia():
    azar = random.Random(7)
    items = [(date(2026, 9, 1), f"MOVIMIENTO {i:02d}",
              D(azar.randint(100, 9_999_999)) / 100 * (1 if i % 3 == 0 else -1)) for i in range(18)]
    items.append((date(2026, 9, 2), "DEPOSITO GRANDE", D("90000.00")))
    movs = con_saldos(D("50000.00"), items)
    r = leer_extracto_pdf(_pdf_un_saldo_por_dia(movs, D("50000.00")), hoy=HOY)
    assert [m["monto"] for m in r["movimientos"]] == [m.monto for m in movs]
    assert r["cuadre"]["cierra"] and not any(m["dudosa"] for m in r["movimientos"])


def test_signo_ambiguo_queda_dudoso_en_vez_de_adivinar():
    # 10 + 10 − 10 − 10 = 0: cualquier par de signos opuestos cierra → no se puede saber.
    movs = con_saldos(D("100.00"), [(date(2026, 9, 1), f"MOV {i}", D("10.00") * (1 if i < 2 else -1))
                                    for i in range(4)])
    r = leer_extracto_pdf(_pdf_un_saldo_por_dia(movs, D("100.00")), hoy=HOY)
    assert all(m["dudosa"] and "Signo sin confirmar" in m["motivos"] for m in r["movimientos"])


def test_fecha_solo_en_la_primera_fila_del_dia():
    movs = galicia_sep()
    filas = filas_galicia(movs, D("150000.00"))
    for i in range(2, len(filas)):
        if movs[i - 1].fecha == movs[i - 2].fecha:
            filas[i].celdas[0] = ""                    # mismo día: el banco no repite la fecha
    assert any(f.celdas[0] == "" for f in filas[2:])
    r = leer_extracto_pdf(pdf_extracto(cols_galicia(), filas, membrete=MEMBRETE_GALICIA), hoy=HOY)
    assert_movs(r, movs)
    assert r["cuadre"]["cierra"] and not any(m["dudosa"] for m in r["movimientos"])


def test_saldo_deudor_con_signo_atras():
    """Cuenta en descubierto: saldos negativos impresos como "1.234,56-"."""
    movs = con_saldos(D("-2000.00"), [
        (date(2026, 9, 3), "CHEQUE PAGADO 12345", D("-5000.00")),
        (date(2026, 9, 10), "DEPOSITO", D("9000.00")),
        (date(2026, 9, 11), "INTERESES DESCUBIERTO", D("-321.45")),
    ])
    filas = [Fila(["", "SALDO ANTERIOR", "", "", "", ar(D("-2000.00"), "atras")])]
    filas += [Fila([m.fecha.strftime("%d/%m/%y"), m.descripcion, "", ar(m.monto) if m.monto > 0 else "",
                    ar(-m.monto) if m.monto < 0 else "", ar(m.saldo, "atras")]) for m in movs]
    r = leer_extracto_pdf(pdf_extracto(cols_galicia(), filas, membrete=MEMBRETE_GALICIA), hoy=HOY)
    assert_movs(r, movs)
    assert r["saldo_inicial"] == D("-2000.00") and r["cuadre"]["cierra"]


# ── (h) Una fila que rompe el saldo corrido → dudosa y no cierra ────────────

def test_fila_que_rompe_el_saldo_queda_dudosa():
    movs = galicia_sep()
    filas = filas_galicia(movs, D("150000.00"))
    # La fila 3 (índice de movimiento 2) muestra un importe que no coincide con el saldo.
    filas[3].celdas[4] = ar(D("1600.00"))
    contenido = pdf_extracto(cols_galicia(), filas, membrete=MEMBRETE_GALICIA)
    r = leer_extracto_pdf(contenido, hoy=HOY)
    assert r["cuadre"]["cierra"] is False
    assert r["cuadre"]["diferencia"] == D("100.00")
    assert r["cuadre"]["filas_con_salto"] == [2]
    fila = r["movimientos"][2]
    assert fila["dudosa"] is True and "El saldo no sigue" in fila["motivos"]
    assert sum(1 for m in r["movimientos"] if m["dudosa"]) == 1
    codigos = {a["codigo"] for a in r["alertas"]}
    assert {"no_cierra", "ia_no_disponible", "filas_dudosas"} <= codigos
    no_cierra = next(a for a in r["alertas"] if a["codigo"] == "no_cierra")
    assert "$ 100,00" in no_cierra["mensaje"]


# ── (i) PDF escaneado: IA (mockeada) o alerta sin IA ────────────────────────

def pdf_escaneado(paginas: int = 1) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    for _ in range(paginas):
        for y in range(100, 800, 20):
            c.rect(40, y, 500, 10, fill=1)
        c.showPage()
    c.save()
    return buf.getvalue()


def test_escaneado_sin_ia_alerta_y_no_lanza():
    r = leer_extracto_pdf(pdf_escaneado(), hoy=HOY)
    assert r["escaneado"] is True
    assert r["metodo"] is None
    assert r["movimientos"] == []
    assert r["ia_usada"] is False and r["ia_disponible"] is False
    codigos = {a["codigo"] for a in r["alertas"]}
    assert {"escaneado", "ia_no_disponible", "sin_movimientos"} <= codigos
    assert r["aprendizaje"] is None


def test_escaneado_con_ia(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "clave-de-prueba")
    llamadas = []

    def fake(mime, contenido):
        llamadas.append(mime)
        assert contenido.startswith(b"%PDF")
        return {
            "banco": "Banco Credicoop Coop. Ltdo.",
            "periodo_desde": "2026-09-01", "periodo_hasta": "2026-09-30",
            "saldo_inicial": "1000.00", "saldo_final": "1150,00",
            "movimientos": [
                {"fecha": "2026-09-02", "descripcion": "Depósito", "credito": "200.00", "saldo": "1200.00"},
                {"fecha": "02/09/2026", "descripcion": "Comisión", "debito": "$ 50,00", "saldo": "1150.00"},
                {"fecha": "2026-09-03", "descripcion": "Línea vacía", "importe": "0"},
            ],
        }

    monkeypatch.setattr(ia_mod, "lector_ia", fake)
    r = leer_extracto_pdf(pdf_escaneado(), hoy=HOY)
    assert llamadas == ["application/pdf"]
    assert r["metodo"] == "ia" and r["ia_usada"] and r["ia_disponible"]
    assert r["banco_clave"] == "credicoop"
    assert [m["monto"] for m in r["movimientos"]] == [D("200.00"), D("-50.00")]
    assert r["movimientos"][1]["fecha"] == date(2026, 9, 2)
    assert r["cuadre"]["cierra"]
    assert r["aprendizaje"] is None                  # escaneado: no hay geometría para aprender
    assert (r["periodo_desde"], r["periodo_hasta"]) == (date(2026, 9, 1), date(2026, 9, 30))


def test_ia_que_falla_no_lanza(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "clave-de-prueba")

    def fake(mime, contenido):
        raise RuntimeError("503 Service Unavailable")

    monkeypatch.setattr(ia_mod, "lector_ia", fake)
    r = leer_extracto_pdf(pdf_escaneado(), hoy=HOY)
    assert r["ia_usada"] is True and r["movimientos"] == []
    assert "ia_error" in {a["codigo"] for a in r["alertas"]}


def test_ia_respuesta_en_lista(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "clave-de-prueba")
    monkeypatch.setattr(ia_mod, "lector_ia", lambda m, c: [
        {"fecha": "2026-09-02", "descripcion": "A", "importe": "-10.00", "saldo": "90.00"},
        {"fecha": "2026-09-03", "descripcion": "B", "importe": "5.00", "saldo": "95.00"},
    ])
    r = leer_extracto_pdf(pdf_escaneado(), hoy=HOY)
    assert [m["monto"] for m in r["movimientos"]] == [D("-10.00"), D("5.00")]
    assert r["cuadre"]["cierra"] and r["cuadre"]["saldo_inicial"] == D("100.00")


def test_ia_mejora_una_lectura_que_no_cierra_en_tandas_de_4_paginas(monkeypatch):
    """PDF con texto que no cierra (falta una fila) → la IA lo lee por texto en tandas."""
    movs = movimientos_generados(150, date(2026, 9, 1))
    filas = filas_galicia(movs, D("100000.00"))
    filas[10].celdas[3] = filas[10].celdas[4] = ""     # una fila sin importe: la lectura no cierra
    contenido = pdf_extracto(cols_galicia(), filas, por_pagina=25, membrete=MEMBRETE_GALICIA)
    monkeypatch.setenv("GEMINI_API_KEY", "clave-de-prueba")
    tandas = []

    def fake(mime, datos):
        texto = datos.decode("utf-8")
        tandas.append((mime, texto.splitlines()[0]))
        if len(tandas) > 1:
            return {"movimientos": []}
        return {"saldo_inicial": "100000.00", "movimientos": [
            {"fecha": m.fecha.isoformat(), "descripcion": m.descripcion, "importe": str(m.monto),
             "saldo": str(m.saldo)} for m in movs
        ]}

    monkeypatch.setattr(ia_mod, "lector_ia", fake)
    r = leer_extracto_pdf(contenido, hoy=HOY)
    assert [t[0] for t in tandas] == ["text/plain", "text/plain"]
    assert tandas[0][1].startswith("Extracto bancario: páginas 1 a 4 de 7.")
    assert tandas[1][1].startswith("Extracto bancario: páginas 5 a 7 de 7.")
    assert r["metodo"] == "ia" and r["cuadre"]["cierra"]
    assert len(r["movimientos"]) == 150


def test_usar_ia_false_no_llama_ni_avisa_si_hay_clave(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "clave-de-prueba")
    r = leer_extracto_pdf(pdf_escaneado(), usar_ia=False, hoy=HOY)
    assert r["ia_usada"] is False and r["ia_disponible"] is False
    assert "ia_no_disponible" not in {a["codigo"] for a in r["alertas"]}


def test_forzar_ia_sin_clave_lee_igual_sin_ia():
    movs = galicia_sep()
    contenido = pdf_extracto(cols_galicia(), filas_galicia(movs, D("150000.00")), membrete=MEMBRETE_GALICIA)
    r = leer_extracto_pdf(contenido, forzar_ia=True, hoy=HOY)
    assert r["metodo"] == "automatico"
    assert_movs(r, movs)
    assert "ia_no_disponible" in {a["codigo"] for a in r["alertas"]}


# ── (j)(k) Archivos que no se pueden leer ──────────────────────────────────

def test_pdf_con_contrasena():
    contenido = pdf_extracto(cols_galicia(), filas_galicia(galicia_sep(), None), encrypt="dni12345")
    with pytest.raises(ExtractoPdfError) as exc:
        leer_extracto_pdf(contenido, hoy=HOY)
    assert exc.value.status == 400
    assert "contraseña" in exc.value.mensaje and "Guardar como PDF" in exc.value.mensaje


def test_pdf_protegido_solo_contra_copia_se_lee():
    from reportlab.lib.pdfencrypt import StandardEncryption

    movs = galicia_sep()
    # Sin clave de apertura; la de dueño da igual (se genera para no dejar una fija en el repo).
    enc = StandardEncryption("", ownerPassword=secrets.token_hex(8), canCopy=0, canModify=0)
    contenido = pdf_extracto(cols_galicia(), filas_galicia(movs, D("150000.00")), membrete=MEMBRETE_GALICIA,
                             encrypt=enc)
    r = leer_extracto_pdf(contenido, hoy=HOY)
    assert_movs(r, movs)


@pytest.mark.parametrize("contenido", [b"", b"hola, esto no es un PDF", b"PK\x03\x04xlsx", b"%PDF-1.4\nbasura basura"])
def test_no_es_pdf_o_danado(contenido):
    with pytest.raises(ExtractoPdfError) as exc:
        leer_extracto_pdf(contenido, hoy=HOY)
    assert exc.value.status == 400


def test_demasiadas_paginas():
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    for _ in range(81):
        c.drawString(40, 800, "x")
        c.showPage()
    c.save()
    with pytest.raises(ExtractoPdfError) as exc:
        leer_extracto_pdf(buf.getvalue(), hoy=HOY)
    assert exc.value.status == 413


def test_pdf_con_texto_sin_tabla():
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    for i, t in enumerate(["Estimado cliente:", "Le informamos que su resumen está disponible en el home banking.",
                           "Saludos cordiales, el banco."] * 5):
        c.drawString(40, 800 - 14 * i, t)
    c.showPage()
    c.save()
    r = leer_extracto_pdf(buf.getvalue(), hoy=HOY)
    assert r["metodo"] is None and r["movimientos"] == []
    assert "sin_movimientos" in {a["codigo"] for a in r["alertas"]}
    assert r["escaneado"] is False


# ── (l) Moldes: aprender de la IA y leer el próximo PDF sin IA ─────────────

def _respuesta_ia(movs: list[Mov], saldo_inicial: D) -> dict:
    return {
        "saldo_inicial": str(saldo_inicial),
        "movimientos": [
            {"fecha": m.fecha.isoformat(), "descripcion": m.descripcion,
             "debito": str(-m.monto) if m.monto < 0 else None,
             "credito": str(m.monto) if m.monto > 0 else None, "saldo": str(m.saldo)}
            for m in movs
        ],
    }


def test_molde_aprendido_de_la_ia_se_usa_sin_ia(monkeypatch):
    columnas = [Col("Fec.", 40), Col("Det.", 95), Col("Ref.", 300),
                Col("Deb.", 420, "der"), Col("Cred.", 490, "der"), Col("Saldo", 560, "der")]

    def armar(movs, saldo_inicial, mes):
        filas = [Fila(["", "SALDO ANTERIOR", "", "", "", ar(saldo_inicial)])]
        filas += [Fila([m.fecha.strftime("%d/%m/%Y"), m.descripcion, "X1",
                        ar(-m.monto) if m.monto < 0 else "", ar(m.monto) if m.monto > 0 else "",
                        ar(m.saldo)]) for m in movs]
        return pdf_extracto(columnas, filas, membrete=("Banco Supervielle S.A.", f"Resumen {mes} 2026"))

    sep = movimientos_generados(12, date(2026, 9, 1), D("5000.00"))
    monkeypatch.setenv("GEMINI_API_KEY", "clave-de-prueba")
    monkeypatch.setattr(ia_mod, "lector_ia", lambda mime, datos: _respuesta_ia(sep, D("5000.00")))
    r1 = leer_extracto_pdf(armar(sep, D("5000.00"), "Septiembre"), forzar_ia=True, hoy=HOY)
    assert r1["metodo"] == "ia" and r1["ia_usada"]
    assert r1["banco_clave"] == "supervielle"
    assert r1["cuadre"]["cierra"]
    apr = r1["aprendizaje"]
    assert apr is not None and apr["layout"]["tipo"] == "ia" and apr["banco_clave"] == "supervielle"
    import json
    json.dumps(apr)                                   # JSON-safe para guardarlo

    # Octubre: otros datos, mismo formato. Con el molde se lee sin IA.
    octu = movimientos_generados(20, date(2026, 10, 1), D("7777.77"))

    def prohibido(mime, datos):
        raise AssertionError("no se debía llamar a la IA")

    monkeypatch.setattr(ia_mod, "lector_ia", prohibido)
    molde = {"id": 42, "banco_clave": apr["banco_clave"], "firma": apr["firma"], "layout": apr["layout"]}
    r2 = leer_extracto_pdf(armar(octu, D("7777.77"), "Octubre"), moldes=[molde], hoy=HOY)
    assert r2["metodo"] == "molde" and r2["molde_id"] == 42
    assert r2["ia_usada"] is False
    assert r2["aprendizaje"] is None
    assert_movs(r2, octu)
    assert r2["cuadre"]["cierra"]


def test_molde_de_lectura_automatica_y_molde_que_no_cierra():
    movs = galicia_sep()
    contenido = pdf_extracto(cols_galicia(), filas_galicia(movs, D("150000.00")), membrete=MEMBRETE_GALICIA)
    apr = leer_extracto_pdf(contenido, hoy=HOY)["aprendizaje"]
    molde = {"id": 7, "banco_clave": "galicia", "firma": apr["firma"], "layout": apr["layout"]}
    otro = con_saldos(D("10.00"), [(date(2026, 10, 1), "COBRO", D("90.00")), (date(2026, 10, 2), "PAGO", D("-5.00"))])
    r = leer_extracto_pdf(pdf_extracto(cols_galicia(), filas_galicia(otro, D("10.00")), membrete=MEMBRETE_GALICIA),
                          moldes=[molde], hoy=HOY)
    assert r["metodo"] == "molde" and r["molde_id"] == 7
    assert_movs(r, otro)

    # Un molde con las columnas corridas no cierra → se lee automático con aviso.
    roto = {**molde, "layout": {**apr["layout"], "columnas": [
        {**c, "campo": {"credito": "debito", "debito": "credito"}.get(c["campo"], c["campo"])}
        for c in apr["layout"]["columnas"]
    ]}}
    r = leer_extracto_pdf(contenido, moldes=[roto], hoy=HOY)
    assert r["metodo"] == "automatico"
    assert "molde_no_cierra" in {a["codigo"] for a in r["alertas"]}
    assert_movs(r, movs)

    # Moldes basura (de una base corrupta) se ignoran sin romper.
    r = leer_extracto_pdf(contenido, moldes=[{"id": 1, "firma": apr["firma"], "layout": {"version": 99}},
                                             "basura", {"firma": None}], hoy=HOY)
    assert r["metodo"] == "automatico"


def test_molde_de_otro_banco_no_se_aplica():
    movs = galicia_sep()
    contenido = pdf_extracto(cols_galicia(), filas_galicia(movs, D("150000.00")), membrete=MEMBRETE_GALICIA)
    apr = leer_extracto_pdf(contenido, hoy=HOY)["aprendizaje"]
    # Mismo encabezado, pero el PDF es de otro banco → la firma no coincide.
    contenido_macro = pdf_extracto(cols_galicia(), filas_galicia(movs, D("150000.00")),
                                   membrete=("Banco Macro S.A.", "Período: 01/09/2026 al 30/09/2026"))
    molde = {"id": 3, "banco_clave": "galicia", "firma": apr["firma"], "layout": apr["layout"]}
    r = leer_extracto_pdf(contenido_macro, moldes=[molde], hoy=HOY)
    assert r["banco_clave"] == "macro" and r["metodo"] == "automatico"


# ── (m) Detección de banco ─────────────────────────────────────────────────

@pytest.mark.parametrize("texto, banco", [
    ("Banco de Galicia y Buenos Aires S.A.U. - Provincia de Buenos Aires", "galicia"),
    ("BBVA Argentina S.A. - Av. Córdoba 111 - Provincia de Buenos Aires", "bbva"),
    ("HSBC Bank Argentina - Sucursal Nación", "hsbc"),
    ("Banco de la Nación Argentina", "nacion"),
    ("Banco de la Provincia de Buenos Aires", "provincia"),
    ("Banco de la Provincia de Córdoba S.A.", "bancor"),
    ("Nuevo Banco de La Rioja S.A.", "rioja"),
    ("Banco Ciudad de Buenos Aires", "ciudad"),
    ("Ciudad Autónoma de Buenos Aires", "generico"),
    ("Período anterior: saldo", "generico"),
    ("Mercado Pago - Resumen de cuenta", "mercadopago"),
])
def test_detectar_banco_texto(texto, banco):
    assert detectar_banco_texto(texto) == banco


def test_detectar_banco_por_zonas_pesa_el_membrete():
    zonas = [("Banco de Galicia y Buenos Aires S.A.U.", 3.0),
             ("TRANSF A BANCO NACION", 1.0), ("PAGO BANCO SANTANDER", 1.0), ("DEBITO BBVA", 1.0)]
    assert detectar_banco_zonas(zonas) == "galicia"


def test_banco_de_pagina_galicia_con_direccion_en_provincia():
    movs = galicia_sep()
    contenido = pdf_extracto(cols_galicia(), filas_galicia(movs, D("150000.00")), membrete=MEMBRETE_GALICIA)
    assert leer_extracto_pdf(contenido, hoy=HOY)["banco_clave"] == "galicia"


# ── Fechas, importes y validación de saldos (unidades) ─────────────────────

@pytest.mark.parametrize("texto, esperado", [
    ("15/09/2026", (15, 9, 2026)), ("15/09/26", (15, 9, 2026)), ("15-09-26", (15, 9, 2026)),
    ("15.09.2026", (15, 9, 2026)), ("2026-09-15", (15, 9, 2026)), ("15/09", (15, 9, None)),
    ("15-sep", (15, 9, None)), ("15 SET 2026", (15, 9, 2026)), ("1/9", (1, 9, None)),
    ("15.09", None), ("31/02/2026", None), ("32/01", None), ("hola", None), ("1.234,56", None),
])
def test_parsear_fecha(texto, esperado):
    assert parsear_fecha(texto) == esperado


def test_detectar_periodo_variantes():
    assert detectar_periodo(["Período: 01/09/2026 al 30/09/2026"]) == (date(2026, 9, 1), date(2026, 9, 30))
    assert detectar_periodo(["Desde: 15/12/2025", "Hasta: 14/01/2026"]) == (date(2025, 12, 15), date(2026, 1, 14))
    assert detectar_periodo(["Resumen de SEPTIEMBRE 2026"]) == (date(2026, 9, 1), date(2026, 9, 30))
    assert detectar_periodo(["Del 1 de febrero de 2026 al 28 de febrero de 2026"]) == (
        date(2026, 2, 1), date(2026, 2, 28))
    assert detectar_periodo(["Fecha de emisión 05/10/2026"]) is None


def test_contexto_de_fechas_cruce_de_anio():
    ctx = armar_contexto((date(2025, 12, 15), date(2026, 1, 14)), [], HOY)
    assert ctx.resolver((28, 12, None)) == date(2025, 12, 28)
    assert ctx.resolver((2, 1, None)) == date(2026, 1, 2)
    ctx = armar_contexto(None, [], date(2026, 1, 10))
    assert ctx.resolver((28, 12, None)) == date(2025, 12, 28)
    assert ctx.resolver((5, 1, None)) == date(2026, 1, 5)


@pytest.mark.parametrize("texto, es", [
    ("1.234,56", True), ("1234,56", True), ("-1.234,56", True), ("1.234,56-", True), ("(1.234,56)", True),
    ("$1.234,56", True), ("1,234.56", True), ("0,00", True),
    ("1.234", False), ("12345678", False), ("20-12345678-9", False), ("21,00%", False), ("15/09", False),
    ("1.234,5", False), ("1.234,567", False), ("0110599520000001234567", False),
])
def test_es_importe(texto, es):
    assert es_importe(texto) is es


def test_validar_saldos_ascendente_con_saldos_explicitos():
    movs = [{"monto": D("-200.00"), "saldo": D("800.00")}, {"monto": D("700.00"), "saldo": D("1500.00")}]
    c = validar_saldos(movs, orden="asc", saldo_inicial=D("1000.00"), saldo_final=D("1500.00"))
    assert c["cierra"] and c["diferencia"] == D("0.00")
    assert c["total_creditos"] == D("700.00") and c["total_debitos"] == D("200.00")
    assert c["cantidad"] == 2 and c["filas_con_salto"] == []
    assert not c["saldo_inicial_inferido"] and not c["saldo_final_inferido"]


def test_validar_saldos_descendente_infiere_saldos():
    movs = [{"monto": "700.00", "saldo": "1500.00"}, {"monto": "-200,00", "saldo": "800.00"}]
    c = validar_saldos(movs, orden="desc", saldo_inicial=None, saldo_final=None)
    assert c["saldo_inicial"] == D("1000.00") and c["saldo_inicial_inferido"]
    assert c["saldo_final"] == D("1500.00") and c["saldo_final_inferido"]
    assert c["cierra"]


def test_validar_saldos_salto_en_orden_original():
    # desc: índice 0 es el más nuevo. El salto está en el movimiento del medio.
    movs = [
        {"monto": D("10.00"), "saldo": D("130.00")},
        {"monto": D("10.00"), "saldo": D("115.00")},   # debería ser 120
        {"monto": D("10.00"), "saldo": D("110.00")},
    ]
    c = validar_saldos(movs, orden="desc", saldo_inicial=D("100.00"), saldo_final=None)
    assert c["filas_con_salto"] == [0, 1]
    # Los totales dan (los dos saltos se compensan), pero con saltos no cierra.
    assert c["diferencia"] == D("0.00") and c["cierra"] is False
    marcar_dudosas(movs, c)
    assert movs[0]["dudosa"] and movs[1]["dudosa"] and "dudosa" not in movs[2]


def test_validar_saldos_no_deduce_el_final_de_filas_sin_saldo():
    # La última fila no trae saldo: su importe no se puede controlar → sin saldo final.
    movs = [{"monto": D("5.00"), "saldo": D("105.00")}, {"monto": D("-1.00")}]
    c = validar_saldos(movs, orden="asc", saldo_inicial=None, saldo_final=None)
    assert c["saldo_final"] is None and not c["saldo_final_inferido"] and c["cierra"] is False
    # Con el saldo final impreso sí se controla.
    c = validar_saldos(movs, orden="asc", saldo_inicial=None, saldo_final=D("104.00"))
    assert c["cierra"]


def test_validar_saldos_sin_saldos_no_cierra_y_saldo_parcial():
    c = validar_saldos([{"monto": D("5.00")}, {"monto": D("-1.00")}], orden="asc", saldo_inicial=None, saldo_final=None)
    assert c["cierra"] is False and c["diferencia"] is None and c["saldo_final_calculado"] is None
    # Saldo solo en la segunda fila: se infiere el inicial restando los montos hasta ahí.
    c = validar_saldos([{"monto": D("5.00")}, {"monto": D("-1.00"), "saldo": D("104.00")}],
                       orden="asc", saldo_inicial=None, saldo_final=None)
    assert c["saldo_inicial"] == D("100.00") and c["cierra"]
    c = validar_saldos([], orden="asc", saldo_inicial=D("1.00"), saldo_final=D("1.00"))
    assert c["cierra"] and c["cantidad"] == 0


def test_validar_saldos_detecta_diferencia_total():
    movs = [{"monto": D("100.00")}, {"monto": D("-30.00")}]
    c = validar_saldos(movs, orden="asc", saldo_inicial=D("0"), saldo_final=D("75.00"))
    assert c["saldo_final_calculado"] == D("70.00") and c["diferencia"] == D("5.00") and not c["cierra"]
    assert formatear_pesos(c["diferencia"]) == "$ 5,00"


# ── Performance ─────────────────────────────────────────────────────────────

def test_resumen_de_40_paginas_y_1500_filas_se_lee_rapido():
    movs = movimientos_generados(1500, date(2026, 9, 1))
    filas = filas_galicia(movs, D("100000.00"))
    contenido = pdf_extracto(cols_galicia(), filas, por_pagina=38, membrete=MEMBRETE_GALICIA,
                             cabecera="Banco de Galicia - Resumen de cuenta")
    t0 = time.perf_counter()
    r = leer_extracto_pdf(contenido, hoy=HOY)
    duracion = time.perf_counter() - t0
    assert r["paginas"] == 40
    assert len(r["movimientos"]) == 1500
    assert r["cuadre"]["cierra"]
    assert duracion < 20, f"tardó {duracion:.1f}s"
