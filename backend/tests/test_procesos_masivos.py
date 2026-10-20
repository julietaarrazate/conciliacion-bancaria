# ruff: noqa: F811  (db y client son fixtures importadas de test_iva_liquidacion)
"""Procesos masivos (benchmark Ola 2, punto 8): correr un cálculo para todas
las organizaciones accesibles y subir "Mis Comprobantes" de varias organizaciones
juntos (cada Excel va a su org por el CUIT del título).

Reglas:
- Solo orgs accesibles para el usuario y con el módulo activo (el resto: omitido).
- Lo presentado/revisado no se toca (ya_presentado).
- Cada org se guarda por separado: un error no corta al resto.
- La liquidación de IVA recalculada conserva retenciones, percepciones y saldos
  cargados a mano (si no, el cálculo los pondría en 0).
"""
from datetime import date
from decimal import Decimal

from app.models.contabilidad import PlanCuenta
from app.models.iibb import IIBBConfig
from app.models.iva_liquidacion import ComprobanteIva, LiquidacionIva
from app.models.monotributo import MonotributoConfig
from app.models.organizacion import Organizacion
from app.services import procesos_masivos as svc
from app.services.auth import get_password_hash
from app.models.user import User
from tests.test_iva_liquidacion import (  # noqa: F401
    _H_RECIBIDOS, _auth, _build_xlsx, _fila_recibido, _token, client, db,
)

CUIT_1 = "30700000008"
CUIT_2 = "20111111112"


def _preparar(db):
    """Org 1 y 2 con CUIT y módulo de IVA; org 2 además IIBB; org 3 sin nada.
    admin@liq.test (org 1) puede ver la org 2."""
    for oid, cuit in ((1, CUIT_1), (2, CUIT_2)):
        org = db.get(Organizacion, oid)
        org.configuracion = {**(org.configuracion or {}), "cuit": cuit}
        db.add(PlanCuenta(organizacion_id=oid, codigo="4-1-1", nombre="Ventas", tipo="ingreso", tasa_iva=0.21))
    db.add(IIBBConfig(organizacion_id=2, activo=True, modo="simple"))
    admin = db.query(User).filter_by(email="admin@liq.test").one()
    admin.allowed_org_ids = [2]
    db.commit()


def _comprobante(db, org_id, numero, iva, direccion="emitido"):
    db.add(ComprobanteIva(organizacion_id=org_id, direccion=direccion, periodo="2026-05",
                          fecha=date(2026, 5, 10), tipo_codigo=1, tipo_desc="1 - Factura A",
                          punto_venta=1, numero=numero, cuit_contraparte="30555555551",
                          neto_gravado_total=Decimal(iva) * 5, total_iva=Decimal(iva),
                          imp_total=Decimal(iva) * 6))
    db.commit()


def _r(resultados, org_id):
    return next(r for r in resultados if r["organizacion_id"] == org_id)


# ── Calcular para todas ──────────────────────────────────────────────────────

def test_iva_para_todas_las_accesibles(db):
    _preparar(db)
    _comprobante(db, 1, 1, "2100")
    _comprobante(db, 2, 1, "4200")
    res = svc.correr(db, "iva_liquidacion", "2026-05", [1, 2, 3], usuario_id=1)
    assert _r(res, 1)["resultado"] == "calculado"
    assert _r(res, 2)["resultado"] == "calculado"
    assert _r(res, 3)["resultado"] == "omitido"
    assert db.query(LiquidacionIva).filter_by(organizacion_id=1).one().debito_fiscal == Decimal("2100.00")
    assert db.query(LiquidacionIva).filter_by(organizacion_id=2).one().debito_fiscal == Decimal("4200.00")


def test_iva_recalculada_conserva_lo_cargado_a_mano(db):
    _preparar(db)
    _comprobante(db, 1, 1, "2100")
    db.add(LiquidacionIva(organizacion_id=1, periodo="2026-05", estado="borrador",
                          retenciones=Decimal("300"), percepciones=Decimal("150"),
                          saldo_tecnico_anterior=Decimal("500"), saldo_libre_anterior=Decimal("50")))
    db.commit()
    svc.correr(db, "iva_liquidacion", "2026-05", [1], usuario_id=1)
    liq = db.query(LiquidacionIva).filter_by(organizacion_id=1).one()
    assert liq.retenciones == Decimal("300.00") and liq.percepciones == Decimal("150.00")
    assert liq.saldo_tecnico_anterior == Decimal("500.00") and liq.saldo_libre_anterior == Decimal("50.00")
    assert liq.debito_fiscal == Decimal("2100.00")


def test_lo_presentado_no_se_toca(db):
    _preparar(db)
    db.add(LiquidacionIva(organizacion_id=1, periodo="2026-05", estado="presentada",
                          debito_fiscal=Decimal("999")))
    db.commit()
    _comprobante(db, 1, 1, "2100")
    res = svc.correr(db, "iva_liquidacion", "2026-05", [1], usuario_id=1)
    assert res[0]["resultado"] == "ya_presentado"
    assert db.query(LiquidacionIva).filter_by(organizacion_id=1).one().debito_fiscal == Decimal("999.00")


def test_un_error_no_corta_al_resto(db, monkeypatch):
    _preparar(db)
    from app.services import iva_service

    original = iva_service.guardar_o_actualizar_proyeccion

    def falla_en_la_1(db_, org_id, periodo):
        if org_id == 1:
            raise iva_service.IvaServiceError("Sin cuentas configuradas")
        return original(db_, org_id, periodo)
    monkeypatch.setattr(iva_service, "guardar_o_actualizar_proyeccion", falla_en_la_1)
    res = svc.correr(db, "iva_proyeccion", "2026-05", [1, 2], usuario_id=1)
    assert _r(res, 1)["resultado"] == "error" and "Sin cuentas" in _r(res, 1)["detalle"]
    assert _r(res, 2)["resultado"] == "calculado"


def test_modulo_inactivo_se_omite(db):
    _preparar(db)
    db.add(MonotributoConfig(organizacion_id=1, activo=False))
    db.commit()
    res = svc.correr(db, "monotributo_control", "2026-S1", [1, 2], usuario_id=1)
    assert {r["resultado"] for r in res} == {"omitido"}
    res = svc.correr(db, "iibb_proyeccion", "2026-05", [1, 2], usuario_id=1)
    assert _r(res, 1)["resultado"] == "omitido"
    assert _r(res, 2)["resultado"] in ("calculado", "error")   # depende de sus datos, pero corre


def test_periodo_y_accion_validos():
    for accion, periodo in (("iva_liquidacion", "2026-13"), ("monotributo_control", "2026-05"),
                            ("inventada", "2026-05")):
        try:
            svc.validar(accion, periodo)
            raise AssertionError(f"{accion} {periodo} debería ser inválido")
        except svc.ProcesoInvalido:
            pass
    svc.validar("monotributo_control", "2026-S2")


# ── Endpoints: calcular ──────────────────────────────────────────────────────

def test_endpoint_calcular_solo_accesibles(db, client):
    _preparar(db)
    _comprobante(db, 1, 1, "2100")
    r = client.post("/procesos-masivos/calcular", headers=_auth(_token(db, "admin@liq.test")),
                    json={"accion": "iva_liquidacion", "periodo": "2026-05"})
    assert r.status_code == 200, r.text
    assert [x["organizacion_id"] for x in r.json()["resultados"]] == [1, 2]   # la 3 no es accesible


def test_endpoint_calcular_org_ajena_pedida_se_ignora(db, client):
    _preparar(db)
    r = client.post("/procesos-masivos/calcular", headers=_auth(_token(db, "admin@liq.test")),
                    json={"accion": "iva_liquidacion", "periodo": "2026-05", "org_ids": [1, 3]})
    assert [x["organizacion_id"] for x in r.json()["resultados"]] == [1]


def test_endpoint_calcular_invalido_422(db, client):
    r = client.post("/procesos-masivos/calcular", headers=_auth(_token(db, "admin@liq.test")),
                    json={"accion": "iva_liquidacion", "periodo": "mayo"})
    assert r.status_code == 422


def test_endpoint_sin_permiso_403(db, client):
    db.add(User(email="rev@liq.test", full_name="Rev", hashed_password=get_password_hash("pw"),
                organizacion_id=1, is_active=True, role="revisor", is_superadmin=False))
    db.commit()
    r = client.post("/procesos-masivos/calcular", headers=_auth(_token(db, "rev@liq.test")),
                    json={"accion": "iva_liquidacion", "periodo": "2026-05"})
    assert r.status_code == 403


# ── Mis Comprobantes de varias organizaciones ──────────────────────────────────────

def _xlsx(cuit_titulo, filas):
    return _build_xlsx(f"Mis Comprobantes Recibidos - CUIT {cuit_titulo}", _H_RECIBIDOS, filas)


def _fila(num, iva=2100):
    return _fila_recibido("05/05/2026", "1 - Factura A", 10, num, 30555555551, "PROV SA",
                          iva, iva * 5, iva, iva * 6)


def test_cuit_del_titulo():
    assert svc.cuit_del_titulo(_xlsx("30-70000000-8", [])) == CUIT_1
    assert svc.cuit_del_titulo(_xlsx(CUIT_2, [])) == CUIT_2
    assert svc.cuit_del_titulo(_build_xlsx("Mis Comprobantes Recibidos", _H_RECIBIDOS, [])) is None


def _archivos(*pares):
    return [("files", (nombre, contenido, "application/octet-stream")) for nombre, contenido in pares]


def test_mis_comprobantes_masivo_compara_e_importa(db, client):
    _preparar(db)
    _comprobante(db, 1, 100, "2100", direccion="recibido")   # ya cargada en org 1 (pv 1, otra clave)
    h = _auth(_token(db, "admin@liq.test"))
    archivos = _archivos(
        ("org1.xlsx", _xlsx(CUIT_1, [_fila(1), _fila(2)])),
        ("org2.xlsx", _xlsx(CUIT_2, [_fila(7)])),
        ("ajena.xlsx", _xlsx("30555555551", [_fila(9)])),          # CUIT sin org accesible
        ("sin_cuit.xlsx", _build_xlsx("Mis Comprobantes Recibidos", _H_RECIBIDOS, [_fila(3)])),
    )
    r = client.post("/procesos-masivos/mis-comprobantes/comparar?direccion=recibido&periodo=2026-05",
                    headers=h, files=archivos)
    assert r.status_code == 200, r.text
    por = {x["archivo"]: x for x in r.json()["archivos"]}
    assert por["org1.xlsx"]["organizacion_id"] == 1 and por["org1.xlsx"]["faltantes"] == 2
    assert por["org1.xlsx"]["solo_en_cuadra"] == 1
    assert por["org2.xlsx"]["organizacion_id"] == 2 and por["org2.xlsx"]["iva_faltante"] == 2100.0
    assert por["ajena.xlsx"]["organizacion_id"] is None and "30555555551" in por["ajena.xlsx"]["error"]
    assert por["sin_cuit.xlsx"]["organizacion_id"] is None and por["sin_cuit.xlsx"]["error"]
    assert db.query(ComprobanteIva).count() == 1    # comparar no carga nada

    r = client.post("/procesos-masivos/mis-comprobantes/importar?direccion=recibido&periodo=2026-05",
                    headers=h, files=archivos)
    assert r.status_code == 200, r.text
    por = {x["archivo"]: x for x in r.json()["archivos"]}
    assert por["org1.xlsx"]["importados"] == 2 and por["org1.xlsx"]["lote"]
    assert por["org2.xlsx"]["importados"] == 1
    assert por["ajena.xlsx"]["importados"] == 0
    assert db.query(ComprobanteIva).filter_by(organizacion_id=1).count() == 3
    assert db.query(ComprobanteIva).filter_by(organizacion_id=2).count() == 1
    assert db.query(ComprobanteIva).filter_by(organizacion_id=3).count() == 0
    # el lote de la org 2 se deshace con el endpoint existente
    lote2 = por["org2.xlsx"]["lote"]
    assert client.delete(f"/iva/comprobantes/lote/{lote2}?org_id=2", headers=h).status_code == 200
    assert db.query(ComprobanteIva).filter_by(organizacion_id=2).count() == 0


def test_dos_orgs_con_el_mismo_cuit_no_se_adivina(db, client):
    _preparar(db)
    org3 = db.get(Organizacion, 3)
    org3.configuracion = {"cuit": CUIT_2}
    db.commit()
    r = client.post("/procesos-masivos/mis-comprobantes/comparar?direccion=recibido&periodo=2026-05",
                    headers=_auth(_token(db, "supa@liq.test")),
                    files=_archivos(("org2.xlsx", _xlsx(CUIT_2, [_fila(7)]))))
    x = r.json()["archivos"][0]
    assert x["organizacion_id"] is None and "más de una" in x["error"]
