"""Tests del módulo Liquidador de Sueldos y F931.

Cubre:
  - cálculo simple de liquidación (1-2 empleados).
  - aportes/contribuciones correctos según las alícuotas configuradas.
  - SAC proporcional (básico/12) integrado a la base imponible.
  - básico por override del empleado vs básico de la categoría.
  - inmutabilidad post-presentado (no se pisa con recálculo).
  - permisos por capa (403 sin permiso).
  - aislamiento multi-org.
  - asiento contable al aprobar (partida doble Debe == Haber).
  - validación de CUIL (11 dígitos).
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
from app.services.sueldos_service import (
    calcular_liquidacion_periodo,
    guardar_o_actualizar_liquidacion,
    aprobar_liquidacion,
    marcar_presentada,
    get_o_crear_config,
    seed_config_sueldos,
    SueldosServiceError,
)
from app.models.organizacion import Organizacion
from app.models.user import User
from app.models.contabilidad import PlanCuenta, Asiento, AsientoDetalle
from app.models.sueldos import (
    ConvenioColectivo, CategoriaConvenio, Empleado, ConfigSueldos,
    LiquidacionSueldoPeriodo, DetalleLiquidacionEmpleado,
)


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

    org = Organizacion(id=1, nombre="OrgSueldos")
    org2 = Organizacion(id=2, nombre="OrgSueldos2")
    session.add_all([org, org2])
    session.commit()

    seed_contabilidad_org(session, 1)
    seed_contabilidad_org(session, 2)

    admin = User(
        email="admin@sueldos.test", full_name="Admin Sueldos",
        hashed_password=get_password_hash("pw123"),
        organizacion_id=1, is_active=True, role="admin", is_superadmin=False,
    )
    revisor = User(
        email="rev@sueldos.test", full_name="Revisor Sueldos",
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


_CAMPOS_ALICUOTA = [
    "aporte_jubilacion", "aporte_inssjp", "aporte_obra_social",
    "contrib_jubilacion", "contrib_inssjp", "contrib_obra_social",
    "contrib_asig_fam", "contrib_fondo_desempleo", "alicuota_art",
]


def _cfg(db, org=1, **alicuotas):
    """Crea/activa la ConfigSueldos. Pone TODAS las alícuotas en 0 y aplica solo
    las dadas (fracciones), para que los tests sean deterministas."""
    cfg = get_o_crear_config(db, org)
    cfg.activo = True
    for k in _CAMPOS_ALICUOTA:
        setattr(cfg, k, Decimal(str(alicuotas.get(k, 0))))
    db.commit()
    db.refresh(cfg)
    return cfg


def _empleado(db, nombre, basico=None, categoria_id=None, org=1, activo=True):
    e = Empleado(
        organizacion_id=org, nombre=nombre,
        sueldo_basico=(Decimal(str(basico)) if basico is not None else None),
        categoria_id=categoria_id, activo=activo,
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


# ── Seed / config ────────────────────────────────────────────────────

def test_seed_config_apagada(db):
    n = seed_config_sueldos(db, 1)
    assert n == 1
    assert seed_config_sueldos(db, 1) == 0  # idempotente
    cfg = db.query(ConfigSueldos).filter(ConfigSueldos.organizacion_id == 1).first()
    assert cfg is not None
    assert cfg.activo is False
    # alícuotas de referencia sembradas, ART en 0
    assert cfg.aporte_jubilacion == Decimal("0.1100")
    assert cfg.alicuota_art == Decimal("0")


def test_modulo_inactivo_falla(db):
    _empleado(db, "Juan", basico=100000)
    with pytest.raises(SueldosServiceError):
        calcular_liquidacion_periodo(db, 1, PERIODO)


def test_periodo_invalido(db):
    _cfg(db)
    with pytest.raises(SueldosServiceError):
        calcular_liquidacion_periodo(db, 1, "2026-13")


# ── Cálculo ──────────────────────────────────────────────────────────

def test_liquidacion_simple_un_empleado(db):
    # aportes 11%+3%+3% = 17% ; contribuciones 10%+ART 0 = 10%
    _cfg(db, aporte_jubilacion=0.11, aporte_inssjp=0.03, aporte_obra_social=0.03,
         contrib_jubilacion=0.10)
    _empleado(db, "Juan", basico=120000)

    calc = calcular_liquidacion_periodo(db, 1, PERIODO)
    assert calc["cantidad_empleados"] == 1
    # SAC = 120000/12 = 10000 ; bruto = 130000
    assert calc["total_bruto"] == Decimal("130000.00")
    # aportes = 130000 × 17% = 22100
    assert calc["total_aportes"] == Decimal("22100.00")
    # contribuciones = 130000 × 10% = 13000
    assert calc["total_contribuciones"] == Decimal("13000.00")
    # neto = bruto - aportes = 107900
    assert calc["total_neto"] == Decimal("107900.00")
    # F931
    assert calc["f931"]["total_remuneraciones"] == 130000.00
    assert calc["f931"]["total_aportes"] == 22100.00
    assert calc["f931"]["total_contribuciones"] == 13000.00


def test_sac_proporcional(db):
    _cfg(db)  # alícuotas de referencia (no afecta el SAC)
    _empleado(db, "Ana", basico=240000)
    calc = calcular_liquidacion_periodo(db, 1, PERIODO)
    d = calc["detalle"][0]
    assert d["sac_proporcional"] == Decimal("20000.00")  # 240000/12
    assert d["sueldo_bruto"] == Decimal("260000.00")


def test_liquidacion_dos_empleados(db):
    _cfg(db, aporte_jubilacion=0.10, contrib_jubilacion=0.20)
    _empleado(db, "Juan", basico=120000)   # bruto 130000
    _empleado(db, "Ana", basico=240000)    # bruto 260000

    calc = calcular_liquidacion_periodo(db, 1, PERIODO)
    assert calc["cantidad_empleados"] == 2
    assert calc["total_bruto"] == Decimal("390000.00")
    assert calc["total_aportes"] == Decimal("39000.00")        # 10% de 390000
    assert calc["total_contribuciones"] == Decimal("78000.00") # 20% de 390000


def test_basico_de_categoria_cuando_no_hay_override(db):
    _cfg(db, aporte_jubilacion=0.10)
    conv = ConvenioColectivo(organizacion_id=1, nombre="Comercio")
    db.add(conv); db.commit(); db.refresh(conv)
    cat = CategoriaConvenio(convenio_id=conv.id, nombre="Vendedor B", sueldo_basico=Decimal("180000"))
    db.add(cat); db.commit(); db.refresh(cat)
    _empleado(db, "Pedro", basico=None, categoria_id=cat.id)

    calc = calcular_liquidacion_periodo(db, 1, PERIODO)
    # bruto = 180000 + 15000 = 195000
    assert calc["total_bruto"] == Decimal("195000.00")


def test_empleado_inactivo_se_ignora(db):
    _cfg(db, aporte_jubilacion=0.10)
    _empleado(db, "Activo", basico=120000)
    _empleado(db, "Inactivo", basico=999999, activo=False)
    calc = calcular_liquidacion_periodo(db, 1, PERIODO)
    assert calc["cantidad_empleados"] == 1
    assert calc["total_bruto"] == Decimal("130000.00")


# ── Persistencia / idempotencia / inmutabilidad ──────────────────────

def test_guardar_es_idempotente(db):
    _cfg(db, aporte_jubilacion=0.10)
    _empleado(db, "Juan", basico=120000)
    p1 = guardar_o_actualizar_liquidacion(db, 1, PERIODO)
    id1 = p1.id
    assert p1.total_bruto == Decimal("130000.00")

    _empleado(db, "Ana", basico=120000)
    p2 = guardar_o_actualizar_liquidacion(db, 1, PERIODO)
    assert p2.id == id1
    assert db.query(LiquidacionSueldoPeriodo).count() == 1
    assert p2.total_bruto == Decimal("260000.00")
    # los detalles se reemplazan (no se duplican)
    assert db.query(DetalleLiquidacionEmpleado).filter(
        DetalleLiquidacionEmpleado.liquidacion_periodo_id == id1
    ).count() == 2


def test_presentada_no_se_pisa(db):
    _cfg(db, aporte_jubilacion=0.10)
    _empleado(db, "Juan", basico=120000)
    liq = guardar_o_actualizar_liquidacion(db, 1, PERIODO)
    liq = aprobar_liquidacion(db, 1, liq.id, None)
    liq = marcar_presentada(db, 1, liq.id)
    assert liq.estado == "presentado"
    bruto = liq.total_bruto

    _empleado(db, "Ana", basico=500000)
    p2 = guardar_o_actualizar_liquidacion(db, 1, PERIODO)
    assert p2.estado == "presentado"
    assert p2.total_bruto == bruto  # intacto


def test_marcar_presentada_requiere_aprobada(db):
    _cfg(db, aporte_jubilacion=0.10)
    _empleado(db, "Juan", basico=120000)
    liq = guardar_o_actualizar_liquidacion(db, 1, PERIODO)
    # en borrador, no aprobada
    with pytest.raises(SueldosServiceError):
        marcar_presentada(db, 1, liq.id)


# ── Asiento contable (partida doble) ─────────────────────────────────

def test_aprobar_genera_asiento_partida_doble(db):
    _cfg(db, aporte_jubilacion=0.10, contrib_jubilacion=0.20)
    _empleado(db, "Juan", basico=120000)  # bruto 130000
    liq = guardar_o_actualizar_liquidacion(db, 1, PERIODO)
    liq = aprobar_liquidacion(db, 1, liq.id, None)
    assert liq.estado == "aprobado"
    assert liq.fecha_aprobacion is not None

    asiento = (
        db.query(Asiento)
        .filter(Asiento.modulo == "sueldos_liquidacion", Asiento.referencia_id == liq.id)
        .first()
    )
    assert asiento is not None
    detalles = db.query(AsientoDetalle).filter(AsientoDetalle.asiento_id == asiento.id).all()
    total_debe = sum(d.debe for d in detalles)
    total_haber = sum(d.haber for d in detalles)
    assert total_debe == total_haber  # partida doble
    # Debe = bruto + contribuciones = 130000 + 26000 = 156000
    assert total_debe == Decimal("156000.00")


def test_aprobar_es_idempotente_no_duplica_asiento(db):
    _cfg(db, aporte_jubilacion=0.10, contrib_jubilacion=0.20)
    _empleado(db, "Juan", basico=120000)
    liq = guardar_o_actualizar_liquidacion(db, 1, PERIODO)
    aprobar_liquidacion(db, 1, liq.id, None)
    # re-aprobar no debe duplicar el asiento (idempotente por modulo+ref)
    from app.services.motor_contable import registrar_liquidacion_sueldos
    registrar_liquidacion_sueldos(
        db=db, liquidacion_id=liq.id, org_id=1, usuario_id=None, periodo=PERIODO,
        total_bruto=Decimal("130000"), total_aportes=Decimal("13000"),
        total_contribuciones=Decimal("26000"), total_neto=Decimal("117000"),
    )
    n = db.query(Asiento).filter(
        Asiento.modulo == "sueldos_liquidacion", Asiento.referencia_id == liq.id
    ).count()
    assert n == 1


def test_aprobar_solo_desde_borrador(db):
    _cfg(db, aporte_jubilacion=0.10)
    _empleado(db, "Juan", basico=120000)
    liq = guardar_o_actualizar_liquidacion(db, 1, PERIODO)
    aprobar_liquidacion(db, 1, liq.id, None)
    with pytest.raises(SueldosServiceError):
        aprobar_liquidacion(db, 1, liq.id, None)  # ya aprobada


# ── Aislamiento multi-org ────────────────────────────────────────────

def test_aislamiento_multi_org(db):
    _cfg(db, org=1, aporte_jubilacion=0.10)
    _empleado(db, "Juan", basico=120000, org=1)
    _cfg(db, org=2, aporte_jubilacion=0.10)
    _empleado(db, "Pedro", basico=300000, org=2)

    c1 = calcular_liquidacion_periodo(db, 1, PERIODO)
    c2 = calcular_liquidacion_periodo(db, 2, PERIODO)
    assert c1["total_bruto"] == Decimal("130000.00")
    assert c2["total_bruto"] == Decimal("325000.00")  # 300000 + 25000 SAC


# ── Permisos / API ───────────────────────────────────────────────────

def test_config_requiere_admin_accounting(db, client):
    rev = _token(db, "rev@sueldos.test")  # solo view_accounting
    r = client.get("/sueldos/config", headers=_auth(rev))
    assert r.status_code == 403


def test_empleados_post_requiere_admin(db, client):
    rev = _token(db, "rev@sueldos.test")
    r = client.post("/sueldos/empleados", json={"nombre": "X"}, headers=_auth(rev))
    assert r.status_code == 403


def test_calcular_requiere_manage_finance(db, client):
    _cfg(db)
    rev = _token(db, "rev@sueldos.test")
    r = client.post(f"/sueldos/liquidacion/calcular?periodo={PERIODO}", headers=_auth(rev))
    assert r.status_code == 403


def test_empleados_lectura_view_accounting(db, client):
    rev = _token(db, "rev@sueldos.test")
    r = client.get("/sueldos/empleados", headers=_auth(rev))
    assert r.status_code == 200


def test_cuil_invalido_400(db, client):
    admin = _token(db, "admin@sueldos.test")
    r = client.post("/sueldos/empleados",
                    json={"nombre": "Juan", "cuil": "123"}, headers=_auth(admin))
    assert r.status_code == 400


def test_proyeccion_modulo_inactivo_400(db, client):
    admin = _token(db, "admin@sueldos.test")
    # config existe pero apagada por default → 400
    r = client.get(f"/sueldos/liquidacion?periodo={PERIODO}", headers=_auth(admin))
    assert r.status_code == 400


def test_soft_delete_empleado(db, client):
    admin = _token(db, "admin@sueldos.test")
    e = _empleado(db, "Borrable", basico=100000)
    r = client.delete(f"/sueldos/empleados/{e.id}", headers=_auth(admin))
    assert r.status_code == 200
    # no aparece más en el listado
    r = client.get("/sueldos/empleados", headers=_auth(admin))
    assert all(x["id"] != e.id for x in r.json()["items"])
    # sigue en la DB con deleted_at
    refreshed = db.query(Empleado).filter(Empleado.id == e.id).first()
    assert refreshed.deleted_at is not None


def test_end_to_end_api(db, client):
    admin = _token(db, "admin@sueldos.test")

    # 1. activar config con alícuotas
    r = client.put("/sueldos/config", json={
        "activo": True, "aporte_jubilacion": 0.11, "aporte_inssjp": 0.03,
        "aporte_obra_social": 0.03, "contrib_jubilacion": 0.10,
    }, headers=_auth(admin))
    assert r.status_code == 200
    assert r.json()["activo"] is True

    # 2. crear empleado
    r = client.post("/sueldos/empleados", json={
        "nombre": "Juan Perez", "cuil": "20123456789", "sueldo_basico": 120000,
    }, headers=_auth(admin))
    assert r.status_code == 200

    # 3. preview
    r = client.get(f"/sueldos/liquidacion?periodo={PERIODO}", headers=_auth(admin))
    assert r.status_code == 200
    assert float(r.json()["total_bruto"]) == 130000.0

    # 4. calcular y persistir
    r = client.post(f"/sueldos/liquidacion/calcular?periodo={PERIODO}", headers=_auth(admin))
    assert r.status_code == 200
    lid = r.json()["id"]

    # 5. aprobar
    r = client.post(f"/sueldos/liquidacion/{lid}/aprobar", headers=_auth(admin))
    assert r.status_code == 200
    assert r.json()["estado"] == "aprobado"

    # 6. historial
    r = client.get("/sueldos/historial", headers=_auth(admin))
    assert r.status_code == 200
    assert r.json()["total"] == 1

    # 7. marcar presentada
    r = client.post(f"/sueldos/liquidacion/{lid}/marcar-presentada", headers=_auth(admin))
    assert r.status_code == 200
    assert r.json()["estado"] == "presentado"
