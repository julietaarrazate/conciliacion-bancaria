# ruff: noqa: F811  (db y client son fixtures importadas de test_comprobantes_compra)
"""Controles nuevos de Comprobantes por revisar (benchmark Ola 1, punto 4):

- La factura tiene que estar a nombre de la organización: la IA lee el CUIT del
  receptor y se compara con el CUIT de la org (configuracion["cuit"], o el de
  la configuración de ARCA si no hay otro).
- No se confirma en un período con la liquidación de IVA presentada.
"""
from app.models.arca import ArcaConfig
from app.models.iva_liquidacion import ComprobanteIva, LiquidacionIva
from app.models.organizacion import Organizacion
from app.services import comprobantes_compra_service as svc
from tests.test_comprobantes_compra import (  # noqa: F401
    RESPUESTA_IA, _auth, _borrador_listo, client, db,
)

CUIT_ORG = "30700000008"     # dígito verificador válido
CUIT_OTRO = "20111111112"    # dígito verificador válido


def _ia_con_receptor(monkeypatch, cuit_receptor):
    monkeypatch.setattr(svc, "ocr_factura",
                        lambda mime, contenido: {**RESPUESTA_IA, "cuit_receptor": cuit_receptor})


def _set_cuit_org(db, cuit, org_id=1):
    org = db.get(Organizacion, org_id)
    org.configuracion = {**(org.configuracion or {}), "cuit": cuit}
    db.commit()


# ── Lectura del CUIT receptor ────────────────────────────────────────────────

def test_normaliza_cuit_receptor():
    d = svc.normalizar_datos({**RESPUESTA_IA, "cuit_receptor": "30-70000000-8"})
    assert d["cuit_receptor"] == CUIT_ORG


def test_el_prompt_pide_el_cuit_receptor():
    assert "cuit_receptor" in svc.PROMPT_FACTURA


# ── CUIT de la organización ──────────────────────────────────────────────────

def test_cuit_organizacion_get_y_put(client, db):
    h = _auth(db, "admin@cc.test")
    assert client.get("/comprobantes-compra/cuit-organizacion", headers=h).json() == {"cuit": None}
    r = client.put("/comprobantes-compra/cuit-organizacion", headers=h, json={"cuit": "30-70000000-8"})
    assert r.status_code == 200, r.text
    assert r.json() == {"cuit": CUIT_ORG}
    db.expire_all()
    config = db.get(Organizacion, 1).configuracion
    assert config["cuit"] == CUIT_ORG
    assert "match_rules" in config   # el resto de la configuración se conserva


def test_cuit_organizacion_invalido_422(client, db):
    r = client.put("/comprobantes-compra/cuit-organizacion", headers=_auth(db, "admin@cc.test"),
                   json={"cuit": "30700000009"})
    assert r.status_code == 422


def test_cuit_organizacion_revisor_no_puede_cambiarlo(client, db):
    r = client.put("/comprobantes-compra/cuit-organizacion", headers=_auth(db, "revisor@cc.test"),
                   json={"cuit": CUIT_ORG})
    assert r.status_code == 403


def test_cuit_organizacion_usa_el_de_arca_si_no_hay_otro(client, db):
    db.add(ArcaConfig(organizacion_id=1, cuit=CUIT_ORG))
    db.commit()
    r = client.get("/comprobantes-compra/cuit-organizacion", headers=_auth(db, "admin@cc.test"))
    assert r.json() == {"cuit": CUIT_ORG}


# ── Alerta: factura a nombre de otro CUIT ────────────────────────────────────

def test_alerta_si_la_factura_es_de_otro_cuit(client, db, monkeypatch):
    _set_cuit_org(db, CUIT_ORG)
    _ia_con_receptor(monkeypatch, CUIT_OTRO)
    bid = _borrador_listo(client, db)
    alertas = client.get(f"/comprobantes-compra/{bid}", headers=_auth(db, "admin@cc.test")).json()["alertas"]
    assert any("otro CUIT" in a and CUIT_OTRO in a for a in alertas)


def test_sin_alerta_si_la_factura_es_de_la_org(client, db, monkeypatch):
    _set_cuit_org(db, CUIT_ORG)
    _ia_con_receptor(monkeypatch, CUIT_ORG)
    bid = _borrador_listo(client, db)
    alertas = client.get(f"/comprobantes-compra/{bid}", headers=_auth(db, "admin@cc.test")).json()["alertas"]
    assert not any("otro CUIT" in a for a in alertas)


def test_sin_cuit_de_la_org_no_controla(client, db, monkeypatch):
    _ia_con_receptor(monkeypatch, CUIT_OTRO)
    bid = _borrador_listo(client, db)
    alertas = client.get(f"/comprobantes-compra/{bid}", headers=_auth(db, "admin@cc.test")).json()["alertas"]
    assert not any("otro CUIT" in a for a in alertas)


# ── Período con la liquidación de IVA presentada ─────────────────────────────

def _presentar(db, periodo="2026-09", org_id=1):
    db.add(LiquidacionIva(organizacion_id=org_id, periodo=periodo, estado="presentada"))
    db.commit()


def test_alerta_si_el_periodo_esta_presentado(client, db):
    _presentar(db)
    bid = _borrador_listo(client, db)     # la factura de prueba es de 2026-09
    alertas = client.get(f"/comprobantes-compra/{bid}", headers=_auth(db, "admin@cc.test")).json()["alertas"]
    assert any("2026-09" in a and "presentada" in a for a in alertas)


def test_no_confirma_en_periodo_presentado(client, db):
    _presentar(db)
    bid = _borrador_listo(client, db)
    h = _auth(db, "admin@cc.test")
    r = client.post(f"/comprobantes-compra/{bid}/confirmar", headers=h, json={})
    assert r.status_code == 409
    assert "presentada" in r.json()["detail"]
    assert db.query(ComprobanteIva).count() == 0
    # en un período posterior, sí
    r = client.post(f"/comprobantes-compra/{bid}/confirmar", headers=h, json={"periodo": "2026-10"})
    assert r.status_code == 200, r.text
    assert db.query(ComprobanteIva).one().periodo == "2026-10"


def test_presentada_de_otra_org_no_bloquea(client, db):
    _presentar(db, org_id=2)
    bid = _borrador_listo(client, db)
    r = client.post(f"/comprobantes-compra/{bid}/confirmar", headers=_auth(db, "admin@cc.test"), json={})
    assert r.status_code == 200, r.text
