# ruff: noqa: F811  (fixtures `client_real`/`db` importados del módulo de la API de PDF)
"""PDF: reconocer el banco aunque el PDF no lo nombre (por el CBU), y recordar el
banco que eligió la persona en la revisión (en el molde, por organización).

PDF sintéticos con reportlab; CBU ficticios con verificadores bien.
"""

from __future__ import annotations

import io

from app.models.extracto import ExtractoBancario
from app.models.extracto_pdf import MoldeExtractoPdf
from app.services.extracto_pdf import leer_extracto_pdf
from tests.test_banco_identificacion import cbu_ficticio
from tests.test_extractos_pdf_api import (  # noqa: F401 (fixtures)
    _auth, _confirmar, _listo, _sin_rate_limit, client_real, db,
)

FILAS = [
    ("02/09/2026", "TRANSF RECIBIDA PEREZ JUAN", "", "500,00", "1.500,00"),
    ("03/09/2026", "PAGO PROVEEDOR ACME SA", "200,00", "", "1.300,00"),
    ("05/09/2026", "COMISION MANTENIMIENTO", "50,00", "", "1.250,00"),
    ("10/09/2026", "TRANSF RECIBIDA GOMEZ ANA", "", "750,00", "2.000,00"),
]


def _pdf(membrete: list[str], filas=FILAS, mes: int = 9) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    _, h = A4
    y = h - 50
    for i, linea in enumerate(membrete):
        c.setFont("Helvetica-Bold" if i == 0 else "Helvetica", 12 if i == 0 else 9)
        c.drawString(40, y, linea)
        y -= 15
    c.setFont("Helvetica", 9)
    c.drawString(40, y, f"Período: 01/{mes:02d}/2026 al 30/{mes:02d}/2026")
    y -= 30
    for x, titulo in [(40, "Fecha"), (100, "Descripción"), (360, "Débitos"), (440, "Créditos"), (520, "Saldo")]:
        c.drawString(x, y, titulo)
    y -= 15
    c.drawString(100, y, "SALDO ANTERIOR")
    c.drawRightString(560, y, "1.000,00")
    for fecha, desc, debito, credito, saldo in filas:
        y -= 14
        c.drawString(40, y, fecha)
        c.drawString(100, y, desc)
        if debito:
            c.drawRightString(400, y, debito)
        if credito:
            c.drawRightString(480, y, credito)
        c.drawRightString(560, y, saldo)
    y -= 15
    c.drawString(100, y, "SALDO FINAL")
    c.drawRightString(560, y, "2.000,00")
    c.showPage()
    c.save()
    return buf.getvalue()


def test_lector_pdf_solo_con_cbu_reconoce_el_banco():
    cbu = cbu_ficticio("285")
    res = leer_extracto_pdf(_pdf(["Resumen de Cuenta Corriente en Pesos", f"CBU: {cbu}"]), usar_ia=False)
    assert res["banco_clave"] == "macro"
    assert res["banco_deteccion"]["motivo"] == "por el CBU de la cuenta"
    assert res["cuadre"]["cierra"] is True


def test_lector_pdf_cbu_en_un_movimiento_no_cuenta():
    otro = cbu_ficticio("011")
    filas = [FILAS[0], (FILAS[1][0], f"TRANSF A CBU {otro}", *FILAS[1][2:]), *FILAS[2:]]
    res = leer_extracto_pdf(_pdf(["Resumen de Cuenta Corriente en Pesos"], filas=filas), usar_ia=False)
    assert res["banco_clave"] == "generico"
    assert res["banco_deteccion"]["pedir_confirmacion"] is True


def test_lector_pdf_cbu_le_gana_al_nombre():
    cbu = cbu_ficticio("007")
    res = leer_extracto_pdf(_pdf(["Banco Macro S.A.", f"CBU {cbu}"]), usar_ia=False)
    assert res["banco_clave"] == "galicia"
    assert "Banco Macro" in res["banco_deteccion"]["conflicto"]


def test_lector_pdf_cbu_en_el_nombre_del_archivo():
    cbu = cbu_ficticio("191")
    res = leer_extracto_pdf(_pdf(["Resumen de cuenta"]), usar_ia=False, nombre_archivo=f"{cbu}.pdf")
    assert res["banco_clave"] == "credicoop"


def test_api_pdf_con_cbu_sale_con_el_banco(client_real, db):
    b = _listo(client_real, db, _pdf(["Resumen de Cuenta Corriente en Pesos", f"CBU {cbu_ficticio('017')}"]))
    assert b["banco_clave"] == "bbva" and b["banco"] == "BBVA"
    assert b["banco_deteccion"]["motivo"] == "por el CBU de la cuenta"
    assert _confirmar(client_real, _auth(db), b, banco_clave="bbva").status_code == 200
    assert db.query(ExtractoBancario).one().banco == "BBVA"


def test_api_pdf_banco_elegido_se_recuerda_en_el_molde_por_org(client_real, db):
    septiembre = _pdf(["Resumen de Cuenta Corriente en Pesos"])
    b = _listo(client_real, db, septiembre)
    assert b["banco_clave"] == "generico" and b["banco_deteccion"]["pedir_confirmacion"] is True
    r = _confirmar(client_real, _auth(db), b, banco_clave="supervielle", banco="Supervielle")
    assert r.status_code == 200, r.text
    assert db.query(ExtractoBancario).one().banco == "Supervielle"
    molde = db.query(MoldeExtractoPdf).one()
    assert molde.banco_clave == "supervielle" and molde.layout.get("banco_confirmado") is True

    # Otro mes, misma org: el formato aprendido trae el banco elegido.
    octubre = _pdf(["Resumen de Cuenta Corriente en Pesos"], mes=10, filas=[
        ("01/10/2026", "TRANSF RECIBIDA LOPEZ MARIA", "", "1.000,00", "2.000,00"),
    ])
    b2 = _listo(client_real, db, octubre, nombre="oct.pdf")
    assert b2["metodo"] == "molde"
    assert b2["banco_clave"] == "supervielle"
    assert b2["banco_deteccion"]["motivo"] == "confirmado antes"

    # Otra organización: no ve lo aprendido por la org 1.
    b3 = _listo(client_real, db, octubre, email="admin2@pdf.test")
    assert b3["banco_clave"] == "generico"


def test_api_pdf_banco_invalido_422(client_real, db):
    b = _listo(client_real, db, _pdf(["Resumen de cuenta"]))
    r = _confirmar(client_real, _auth(db), b, banco_clave="no-existe")
    assert r.status_code == 422
