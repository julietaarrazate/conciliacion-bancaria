"""Tests del módulo Ingresos Brutos (IIBB) y Convenio Multilateral.

Cubre:
  - cálculo de ingreso del período (haber - debe de cuentas resultado "3-1*").
  - modo simple: ingreso_total × alícuota de la jurisdicción única.
  - modo convenio_multilateral: distribución por coeficientes × alícuotas propias.
  - warning cuando los coeficientes no suman 100% (no bloquea el cálculo).
  - idempotencia de guardar_o_actualizar_proyeccion (upsert, no duplica).
  - marcar_presentada no se pisa con recálculo posterior (inmutable).
  - error si el módulo no está activo → 400 vía API.
  - permisos: 403 sin admin_accounting (config/jurisdicciones), 403 sin manage_finance (calcular).
  - aislamiento multi-org (cada org ve solo sus jurisdicciones/proyecciones).
  - end-to-end API: activar config → jurisdicciones → calcular → historial → presentar.
"""
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.services.auth import get_password_hash, create_access_token
from app.services.seed_contable import seed_contabilidad_org
from app.services.iibb_service import (
    calcular_ingreso_periodo,
    calcular_proyeccion_iibb,
    guardar_o_actualizar_proyeccion,
    marcar_presentada,
    seed_iibb_jurisdiccion,
    IIBBServiceError,
)
from app.models.organizacion import Organizacion
from app.models.user import User
from app.models.contabilidad import PlanCuenta, Asiento, AsientoDetalle
from app.models.iibb import IIBBConfig, JurisdiccionIIBB, ProyeccionIIBB


PERIODO = "2026-06"


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    org = Organizacion(id=1, nombre="OrgIIBB")
    org2 = Organizacion(id=2, nombre="OrgIIBB2")
    session.add_all([org, org2])
    session.commit()

    seed_contabilidad_org(session, 1)
    seed_contabilidad_org(session, 2)

    admin = User(
        email="admin@iibb.test", full_name="Admin IIBB",
        hashed_password=get_password_hash("pw123"),
        organizacion_id=1, is_active=True, role="admin", is_superadmin=False,
    )
    revisor = User(
        email="rev@iibb.test", full_name="Revisor IIBB",
        hashed_password=get_password_hash("pw123"),
        organizacion_id=1, is_active=True, role="revisor", is_superadmin=False,
    )
    session.add_all([admin, revisor])
    session.commit()

    yield session
    session.close()


@pytest.fixture
def client(db):
    def _override_db():
        yield db
    app.dependency_overrides[get_db] = _override_db
    c = TestClient(app, raise_server_exceptions=True)
    yield c
    app.dependency_overrides.pop(get_db, None)


def _token(db, email):
    user = db.query(User).filter(User.email == email).first()
    return create_access_token({"sub": user.email, "user_id": user.id, "role": user.role})


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _cuenta(db, codigo, org=1):
    return db.query(PlanCuenta).filter(
        PlanCuenta.codigo == codigo, PlanCuenta.organizacion_id == org
    ).first()


def _asiento(db, fecha, lineas, org=1):
    """lineas = [(codigo, debe, haber), ...]"""
    a = Asiento(fecha=fecha, descripcion="test", modulo="test", organizacion_id=org)
    db.add(a)
    db.flush()
    for codigo, debe, haber in lineas:
        c = _cuenta(db, codigo, org)
        db.add(AsientoDetalle(
            asiento_id=a.id, cuenta_id=c.id,
            debe=Decimal(str(debe)), haber=Decimal(str(haber)),
        ))
    db.commit()
    return a


def _ingreso(db, fecha, monto, org=1):
    """Asiento de ingreso: Banco D / Comisiones (3-1-1-0, ingreso) H."""
    _asiento(db, fecha, [
        ("1-1-1-3-1", monto, 0),
        ("3-1-1-0", 0, monto),
    ], org=org)


def _jur(db, nombre, alicuota=0.0, coef=0.0, activa=True, orden=0, org=1):
    j = JurisdiccionIIBB(
        organizacion_id=org, nombre=nombre,
        alicuota=Decimal(str(alicuota)),
        coeficiente_distribucion=Decimal(str(coef)),
        activa=activa, orden=orden,
    )
    db.add(j)
    db.commit()
    db.refresh(j)
    return j


def _config(db, activo=True, modo="simple", jurisdiccion_unica_id=None, org=1):
    cfg = IIBBConfig(
        organizacion_id=org, activo=activo, modo=modo,
        jurisdiccion_unica_id=jurisdiccion_unica_id,
    )
    db.add(cfg)
    db.commit()
    return cfg


# ── Seed ────────────────────────────────────────────────────────────

def test_seed_jurisdiccion_ilustrativa(db):
    n = seed_iibb_jurisdiccion(db, 1)
    assert n == 1
    # idempotente
    assert seed_iibb_jurisdiccion(db, 1) == 0
    j = db.query(JurisdiccionIIBB).filter(JurisdiccionIIBB.organizacion_id == 1).first()
    assert j is not None
    assert j.alicuota == Decimal("0")  # NO se siembran alícuotas reales


# ── Ingreso del período ──────────────────────────────────────────────

def test_ingreso_periodo_dentro_y_fuera(db):
    _ingreso(db, date(2026, 6, 5), 100000)
    _ingreso(db, date(2026, 6, 30), 50000)
    _ingreso(db, date(2026, 5, 31), 999999)   # fuera (mes anterior)
    _ingreso(db, date(2026, 7, 1), 888888)    # fuera (mes siguiente)

    total = calcular_ingreso_periodo(db, 1, date(2026, 6, 1), date(2026, 6, 30))
    assert total == Decimal("150000.00")


def test_ingreso_periodo_neto_haber_menos_debe(db):
    _ingreso(db, date(2026, 6, 10), 100000)
    _asiento(db, date(2026, 6, 15), [
        ("3-1-1-0", 30000, 0),   # débito en ingreso (devolución)
        ("1-1-1-3-1", 0, 30000),
    ])
    total = calcular_ingreso_periodo(db, 1, date(2026, 6, 1), date(2026, 6, 30))
    assert total == Decimal("70000.00")


# ── Modo simple ──────────────────────────────────────────────────────

def test_proyeccion_simple(db):
    j = _jur(db, "CABA", alicuota=0.05)
    _config(db, modo="simple", jurisdiccion_unica_id=j.id)
    _ingreso(db, date(2026, 6, 10), 1000000)

    calc = calcular_proyeccion_iibb(db, 1, PERIODO)
    assert calc["modo"] == "simple"
    assert calc["ingreso_total"] == Decimal("1000000.00")
    assert calc["impuesto_total"] == Decimal("50000.00")  # 5%
    assert len(calc["detalle"]) == 1
    assert calc["detalle"][0]["nombre"] == "CABA"
    assert calc["detalle"][0]["impuesto"] == 50000.00
    assert calc["warning"] is None


def test_proyeccion_simple_sin_jurisdiccion_unica_falla(db):
    _config(db, modo="simple", jurisdiccion_unica_id=None)
    _ingreso(db, date(2026, 6, 10), 1000)
    with pytest.raises(IIBBServiceError):
        calcular_proyeccion_iibb(db, 1, PERIODO)


# ── Modo convenio multilateral ───────────────────────────────────────

def test_proyeccion_convenio_multilateral(db):
    _jur(db, "CABA", alicuota=0.05, coef=0.6, orden=1)
    _jur(db, "Buenos Aires", alicuota=0.04, coef=0.4, orden=2)
    _config(db, modo="convenio_multilateral")
    _ingreso(db, date(2026, 6, 10), 1000000)

    calc = calcular_proyeccion_iibb(db, 1, PERIODO)
    assert calc["modo"] == "convenio_multilateral"
    assert calc["ingreso_total"] == Decimal("1000000.00")
    # CABA: 600000 × 5% = 30000 ; BA: 400000 × 4% = 16000
    assert calc["impuesto_total"] == Decimal("46000.00")
    assert calc["suma_coeficientes"] == Decimal("1.0000")
    assert calc["warning"] is None
    detalle = {d["nombre"]: d for d in calc["detalle"]}
    assert detalle["CABA"]["ingreso_atribuido"] == 600000.00
    assert detalle["CABA"]["impuesto"] == 30000.00
    assert detalle["Buenos Aires"]["impuesto"] == 16000.00


def test_convenio_coeficientes_no_suman_100_warning(db):
    _jur(db, "CABA", alicuota=0.05, coef=0.5, orden=1)
    _jur(db, "Buenos Aires", alicuota=0.04, coef=0.35, orden=2)
    _config(db, modo="convenio_multilateral")
    _ingreso(db, date(2026, 6, 10), 1000000)

    calc = calcular_proyeccion_iibb(db, 1, PERIODO)
    assert calc["suma_coeficientes"] == Decimal("0.8500")
    assert calc["warning"] is not None
    assert "no" in calc["warning"].lower() and "100" in calc["warning"]
    # el cálculo SIGUE funcionando (no bloquea)
    # CABA: 500000×5% = 25000 ; BA: 350000×4% = 14000
    assert calc["impuesto_total"] == Decimal("39000.00")


def test_convenio_ignora_jurisdicciones_inactivas(db):
    _jur(db, "CABA", alicuota=0.05, coef=1.0, orden=1, activa=True)
    _jur(db, "Cordoba", alicuota=0.04, coef=0.5, orden=2, activa=False)
    _config(db, modo="convenio_multilateral")
    _ingreso(db, date(2026, 6, 10), 1000000)

    calc = calcular_proyeccion_iibb(db, 1, PERIODO)
    assert len(calc["detalle"]) == 1
    assert calc["detalle"][0]["nombre"] == "CABA"
    assert calc["impuesto_total"] == Decimal("50000.00")


def test_convenio_sin_jurisdicciones_activas_falla(db):
    _jur(db, "CABA", alicuota=0.05, coef=1.0, activa=False)
    _config(db, modo="convenio_multilateral")
    _ingreso(db, date(2026, 6, 10), 1000)
    with pytest.raises(IIBBServiceError):
        calcular_proyeccion_iibb(db, 1, PERIODO)


# ── Módulo apagado / período inválido ────────────────────────────────

def test_modulo_inactivo_falla(db):
    j = _jur(db, "CABA", alicuota=0.05)
    _config(db, activo=False, modo="simple", jurisdiccion_unica_id=j.id)
    with pytest.raises(IIBBServiceError):
        calcular_proyeccion_iibb(db, 1, PERIODO)


def test_periodo_invalido(db):
    j = _jur(db, "CABA", alicuota=0.05)
    _config(db, modo="simple", jurisdiccion_unica_id=j.id)
    with pytest.raises(IIBBServiceError):
        calcular_proyeccion_iibb(db, 1, "2026-13")
    with pytest.raises(IIBBServiceError):
        calcular_proyeccion_iibb(db, 1, "basura")


# ── Persistencia / idempotencia ──────────────────────────────────────

def test_guardar_es_idempotente(db):
    j = _jur(db, "CABA", alicuota=0.05)
    _config(db, modo="simple", jurisdiccion_unica_id=j.id)
    _ingreso(db, date(2026, 6, 10), 1000000)

    p1 = guardar_o_actualizar_proyeccion(db, 1, PERIODO)
    id1 = p1.id
    assert p1.impuesto_total == Decimal("50000.00")

    _ingreso(db, date(2026, 6, 12), 1000000)
    p2 = guardar_o_actualizar_proyeccion(db, 1, PERIODO)
    assert p2.id == id1
    assert db.query(ProyeccionIIBB).filter(
        ProyeccionIIBB.organizacion_id == 1, ProyeccionIIBB.periodo == PERIODO
    ).count() == 1
    assert p2.impuesto_total == Decimal("100000.00")


def test_presentada_no_se_pisa(db):
    j = _jur(db, "CABA", alicuota=0.05)
    _config(db, modo="simple", jurisdiccion_unica_id=j.id)
    _ingreso(db, date(2026, 6, 10), 1000000)

    guardar_o_actualizar_proyeccion(db, 1, PERIODO)
    p = marcar_presentada(db, 1, PERIODO)
    assert p.estado == "presentado"
    assert p.fecha_presentacion is not None
    impuesto_presentado = p.impuesto_total

    _ingreso(db, date(2026, 6, 20), 5000000)
    p2 = guardar_o_actualizar_proyeccion(db, 1, PERIODO)
    assert p2.estado == "presentado"
    assert p2.impuesto_total == impuesto_presentado


def test_marcar_presentada_sin_proyeccion_falla(db):
    with pytest.raises(IIBBServiceError):
        marcar_presentada(db, 1, PERIODO)


# ── Aislamiento multi-org ────────────────────────────────────────────

def test_aislamiento_multi_org(db):
    j1 = _jur(db, "CABA", alicuota=0.05, org=1)
    _config(db, modo="simple", jurisdiccion_unica_id=j1.id, org=1)
    _ingreso(db, date(2026, 6, 10), 1000000, org=1)

    j2 = _jur(db, "Cordoba", alicuota=0.03, org=2)
    _config(db, modo="simple", jurisdiccion_unica_id=j2.id, org=2)
    _ingreso(db, date(2026, 6, 10), 2000000, org=2)

    c1 = calcular_proyeccion_iibb(db, 1, PERIODO)
    c2 = calcular_proyeccion_iibb(db, 2, PERIODO)
    assert c1["ingreso_total"] == Decimal("1000000.00")
    assert c1["impuesto_total"] == Decimal("50000.00")
    assert c2["ingreso_total"] == Decimal("2000000.00")
    assert c2["impuesto_total"] == Decimal("60000.00")  # 3%


# ── Permisos / API ───────────────────────────────────────────────────

def test_config_requiere_admin_accounting(db, client):
    token = _token(db, "rev@iibb.test")  # solo view_accounting
    r = client.get("/iibb/config", headers=_auth(token))
    assert r.status_code == 403


def test_jurisdicciones_post_requiere_admin(db, client):
    rev = _token(db, "rev@iibb.test")
    r = client.post("/iibb/jurisdicciones",
                    json={"nombre": "CABA", "alicuota": 0.05}, headers=_auth(rev))
    assert r.status_code == 403


def test_calcular_requiere_manage_finance(db, client):
    j = _jur(db, "CABA", alicuota=0.05)
    _config(db, modo="simple", jurisdiccion_unica_id=j.id)
    rev = _token(db, "rev@iibb.test")
    r = client.post(f"/iibb/proyeccion/calcular?periodo={PERIODO}", headers=_auth(rev))
    assert r.status_code == 403


def test_proyeccion_modulo_inactivo_400(db, client):
    token = _token(db, "admin@iibb.test")
    r = client.get(f"/iibb/proyeccion?periodo={PERIODO}", headers=_auth(token))
    assert r.status_code == 400


def test_jurisdiccion_alicuota_fuera_de_rango_422(db, client):
    admin = _token(db, "admin@iibb.test")
    r = client.post("/iibb/jurisdicciones",
                    json={"nombre": "CABA", "alicuota": 1.5}, headers=_auth(admin))
    assert r.status_code == 422


def test_jurisdiccion_duplicada_409(db, client):
    admin = _token(db, "admin@iibb.test")
    r = client.post("/iibb/jurisdicciones",
                    json={"nombre": "CABA", "alicuota": 0.05}, headers=_auth(admin))
    assert r.status_code == 200
    r = client.post("/iibb/jurisdicciones",
                    json={"nombre": "CABA", "alicuota": 0.04}, headers=_auth(admin))
    assert r.status_code == 409


def test_end_to_end_api(db, client):
    admin = _token(db, "admin@iibb.test")

    # 1. crear jurisdicción
    r = client.post("/iibb/jurisdicciones",
                    json={"nombre": "CABA", "alicuota": 0.05, "orden": 1}, headers=_auth(admin))
    assert r.status_code == 200
    jur_id = r.json()["id"]

    # 2. activar config en modo simple con esa jurisdicción
    r = client.put("/iibb/config",
                   json={"activo": True, "modo": "simple", "jurisdiccion_unica_id": jur_id},
                   headers=_auth(admin))
    assert r.status_code == 200
    assert r.json()["activo"] is True

    # ingreso
    _ingreso(db, date(2026, 6, 5), 800000)

    # 3. preview
    r = client.get(f"/iibb/proyeccion?periodo={PERIODO}", headers=_auth(admin))
    assert r.status_code == 200
    assert float(r.json()["ingreso_total"]) == 800000.0
    assert float(r.json()["impuesto_total"]) == 40000.0

    # 4. calcular y persistir
    r = client.post(f"/iibb/proyeccion/calcular?periodo={PERIODO}", headers=_auth(admin))
    assert r.status_code == 200
    pid = r.json()["id"]
    assert r.json()["estado"] == "proyectado"

    # 5. historial
    r = client.get("/iibb/historial", headers=_auth(admin))
    assert r.status_code == 200
    assert r.json()["total"] == 1

    # 6. marcar presentada
    r = client.post(f"/iibb/proyeccion/{pid}/marcar-presentada", headers=_auth(admin))
    assert r.status_code == 200
    assert r.json()["estado"] == "presentado"


def test_end_to_end_convenio_warning_via_api(db, client):
    admin = _token(db, "admin@iibb.test")
    # 2 jurisdicciones que suman 80%
    client.post("/iibb/jurisdicciones",
                json={"nombre": "CABA", "alicuota": 0.05, "coeficiente_distribucion": 0.5, "orden": 1},
                headers=_auth(admin))
    client.post("/iibb/jurisdicciones",
                json={"nombre": "Buenos Aires", "alicuota": 0.04, "coeficiente_distribucion": 0.3, "orden": 2},
                headers=_auth(admin))
    client.put("/iibb/config",
               json={"activo": True, "modo": "convenio_multilateral"}, headers=_auth(admin))
    _ingreso(db, date(2026, 6, 5), 1000000)

    r = client.get(f"/iibb/proyeccion?periodo={PERIODO}", headers=_auth(admin))
    assert r.status_code == 200
    assert r.json()["warning"] is not None
    assert float(r.json()["suma_coeficientes"]) == 0.8
