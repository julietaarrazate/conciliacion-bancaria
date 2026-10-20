# ruff: noqa: F811  (db y client son fixtures importadas de test_iva_liquidacion)
"""Comparar "Mis Comprobantes" de ARCA con lo cargado en Cuadra, importar solo
lo elegido y deshacer una tanda (benchmark Ola 1, punto 3).

No se conecta a ARCA: usa el Excel que se descarga de la web, igual que la
importación existente. Reutiliza los helpers y fixtures de test_iva_liquidacion.
"""
import json
from datetime import date
from decimal import Decimal

from app.models.iva_liquidacion import ComprobanteIva, LiquidacionIva
from app.services.comparar_mis_comprobantes import clave_comprobante, comparar
from app.services.mis_comprobantes_parser import parsear_mis_comprobantes
from tests.test_iva_liquidacion import (  # noqa: F401
    _H_RECIBIDOS, _auth, _build_xlsx, _fila_recibido, _token, client, db,
)

TITULO = "Mis Comprobantes Recibidos - CUIT 30700000008"


def _xlsx_compras():
    return _build_xlsx(TITULO, _H_RECIBIDOS, [
        # ya cargada en Cuadra con el mismo IVA
        _fila_recibido("05/05/2026", "1 - Factura A", 10, 100, 30555555551, "PROV UNO SA",
                       2100, 10000, 2100, 12100),
        # ya cargada pero con otro IVA en Cuadra
        _fila_recibido("06/05/2026", "1 - Factura A", 10, 101, 30555555551, "PROV UNO SA",
                       4200, 20000, 4200, 24200),
        # falta en Cuadra
        _fila_recibido("07/05/2026", "1 - Factura A", 20, 7, 30666666661, "PROV DOS SRL",
                       630, 3000, 630, 3630),
        # falta en Cuadra (otra)
        _fila_recibido("08/05/2026", "6 - Factura B", 21, 8, 30777777771, "PROV TRES",
                       None, None, None, 5000),
        # fuera de período
        _fila_recibido("02/06/2026", "1 - Factura A", 10, 150, 30555555551, "PROV UNO SA",
                       210, 1000, 210, 1210),
    ])


def _cargar_en_cuadra(db, org_id=1):
    """Lo que ya estaba cargado (a mano o desde Comprobantes por revisar)."""
    base = dict(organizacion_id=org_id, direccion="recibido", periodo="2026-05", tipo_codigo=1,
                tipo_desc="1 - Factura A", cuit_contraparte="30555555551", denominacion="PROV UNO SA")
    db.add_all([
        ComprobanteIva(fecha=date(2026, 5, 5), punto_venta=10, numero=100,
                       neto_gravado_total=Decimal("10000"), total_iva=Decimal("2100"),
                       imp_total=Decimal("12100"), **base),
        ComprobanteIva(fecha=date(2026, 5, 6), punto_venta=10, numero=101,
                       neto_gravado_total=Decimal("20000"), total_iva=Decimal("4000"),
                       imp_total=Decimal("24000"), **base),
        # está en Cuadra y ARCA no lo tiene
        ComprobanteIva(fecha=date(2026, 5, 9), punto_venta=99, numero=1,
                       neto_gravado_total=Decimal("500"), total_iva=Decimal("105"),
                       imp_total=Decimal("605"), **base),
    ])
    db.commit()


# ── Servicio ─────────────────────────────────────────────────────────────────

def test_clave_normaliza_cuit():
    assert clave_comprobante(1, 10, 100, "30-55555555-1") == clave_comprobante(1, 10, 100, "30555555551")


def test_comparar_clasifica(db):
    _cargar_en_cuadra(db)
    filas = parsear_mis_comprobantes(_xlsx_compras(), "recibido")
    r = comparar(db, 1, "recibido", "2026-05", filas)

    assert [f["numero"] for f in r["faltantes"]] == [7, 8]
    assert r["iva_faltante"] == Decimal("630.00")
    assert {f["numero"] for f in r["ya_cargados"]} == {100, 101}
    distinto = next(f for f in r["ya_cargados"] if f["numero"] == 101)
    assert distinto["importe_distinto"] is True
    assert distinto["total_iva_cuadra"] == Decimal("4000.00")
    igual = next(f for f in r["ya_cargados"] if f["numero"] == 100)
    assert igual["importe_distinto"] is False
    assert [c.numero for c in r["solo_en_cuadra"]] == [1]
    assert r["fuera_de_periodo"] == 1


def test_comparar_aislado_por_org(db):
    _cargar_en_cuadra(db, org_id=2)
    filas = parsear_mis_comprobantes(_xlsx_compras(), "recibido")
    r = comparar(db, 1, "recibido", "2026-05", filas)
    assert len(r["faltantes"]) == 4
    assert r["ya_cargados"] == [] and r["solo_en_cuadra"] == []


# ── Endpoints ────────────────────────────────────────────────────────────────

def _post_archivo(client, token, url, xlsx, data=None):
    return client.post(url, headers=_auth(token), data=data or {},
                       files={"file": ("mc.xlsx", xlsx, "application/octet-stream")})


def test_endpoint_comparar(db, client):
    _cargar_en_cuadra(db)
    token = _token(db, "admin@liq.test")
    r = _post_archivo(client, token, "/iva/comprobantes/comparar?direccion=recibido&periodo=2026-05",
                      _xlsx_compras())
    assert r.status_code == 200, r.text
    d = r.json()
    assert [f["numero"] for f in d["faltantes"]] == [7, 8]
    assert d["faltantes"][0]["clave"] == clave_comprobante(1, 20, 7, "30666666661")
    assert d["iva_faltante"] == 630.0
    assert len(d["ya_cargados"]) == 2
    assert [c["numero"] for c in d["solo_en_cuadra"]] == [1]
    assert d["fuera_de_periodo"] == 1
    # comparar no carga nada
    assert db.query(ComprobanteIva).count() == 3


def test_importar_solo_las_elegidas_con_lote_y_deshacer(db, client):
    _cargar_en_cuadra(db)
    token = _token(db, "admin@liq.test")
    elegida = clave_comprobante(1, 20, 7, "30666666661")
    r = _post_archivo(client, token, "/iva/comprobantes/importar?direccion=recibido&periodo=2026-05",
                      _xlsx_compras(), data={"claves": json.dumps([elegida])})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["importados"] == 1
    assert d["lote"]
    nueva = db.query(ComprobanteIva).filter(ComprobanteIva.numero == 7).one()
    assert nueva.lote_importacion == d["lote"]
    assert db.query(ComprobanteIva).filter(ComprobanteIva.numero == 8).count() == 0

    r2 = client.delete(f"/iva/comprobantes/lote/{d['lote']}", headers=_auth(token))
    assert r2.status_code == 200, r2.text
    assert r2.json()["borrados"] == 1
    assert db.query(ComprobanteIva).filter(ComprobanteIva.numero == 7).count() == 0
    # lo cargado antes no se toca
    assert db.query(ComprobanteIva).count() == 3


def test_importar_sin_claves_sigue_igual(db, client):
    token = _token(db, "admin@liq.test")
    r = _post_archivo(client, token, "/iva/comprobantes/importar?direccion=recibido&periodo=2026-05",
                      _xlsx_compras())
    d = r.json()
    assert d["importados"] == 4 and d["fuera_de_periodo"] == 1
    assert db.query(ComprobanteIva).filter(ComprobanteIva.lote_importacion == d["lote"]).count() == 4


def test_deshacer_bloqueado_si_la_liquidacion_esta_presentada(db, client):
    token = _token(db, "admin@liq.test")
    d = _post_archivo(client, token, "/iva/comprobantes/importar?direccion=recibido&periodo=2026-05",
                      _xlsx_compras()).json()
    db.add(LiquidacionIva(organizacion_id=1, periodo="2026-05", estado="presentada"))
    db.commit()
    r = client.delete(f"/iva/comprobantes/lote/{d['lote']}", headers=_auth(token))
    assert r.status_code == 409
    assert db.query(ComprobanteIva).count() == 4


def test_deshacer_lote_de_otra_org_no_borra(db, client):
    token_admin = _token(db, "admin@liq.test")
    d = _post_archivo(client, token_admin, "/iva/comprobantes/importar?direccion=recibido&periodo=2026-05",
                      _xlsx_compras()).json()
    # el lote es de la org 1; un usuario de la org 2 no lo puede borrar
    from app.models.user import User
    from app.services.auth import get_password_hash
    db.add(User(email="otro@liq.test", full_name="Otro", hashed_password=get_password_hash("pw"),
                organizacion_id=2, is_active=True, role="admin", is_superadmin=False))
    db.commit()
    r = client.delete(f"/iva/comprobantes/lote/{d['lote']}", headers=_auth(_token(db, "otro@liq.test")))
    assert r.status_code == 404
    assert db.query(ComprobanteIva).count() == 4
