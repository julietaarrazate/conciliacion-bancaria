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
    EscalaGanancias, LiquidacionSueldoPeriodo, DetalleLiquidacionEmpleado,
)
from app.services.sueldos_service import calcular_ganancias_4ta


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


# ── Retención de Ganancias 4ta categoría (Extensión 1) ────────────────

def _escala(db, org=1, tramos=None):
    """Crea tramos de la escala de Ganancias para una org. tramos = lista de
    dicts {desde, hasta, alicuota, fijo}; hasta=None = último tramo (sin techo)."""
    creados = []
    for t in (tramos or []):
        e = EscalaGanancias(
            organizacion_id=org,
            tramo_desde=Decimal(str(t["desde"])),
            tramo_hasta=(Decimal(str(t["hasta"])) if t.get("hasta") is not None else None),
            alicuota=Decimal(str(t["alicuota"])),
            monto_fijo=Decimal(str(t["fijo"])),
        )
        db.add(e)
        creados.append(e)
    db.commit()
    for e in creados:
        db.refresh(e)
    return creados


def test_ganancias_inactivo_retencion_cero(db):
    """ganancias_activo=False (default) -> calcular_ganancias_4ta no calcula, da 0."""
    _escala(db, tramos=[{"desde": 0, "hasta": None, "alicuota": 0.27, "fijo": 0}])
    r = calcular_ganancias_4ta(
        bruto_mensual=Decimal("500000"),
        escala=[],
        minimo_no_imponible=Decimal("100000"),
        deduccion_especial=Decimal("50000"),
        ganancias_activo=False,
    )
    assert r == Decimal("0")


def test_ganancias_sin_escala_retencion_cero(db):
    """ganancias_activo=True pero sin tramos cargados -> 0 (no debe romper)."""
    r = calcular_ganancias_4ta(
        bruto_mensual=Decimal("500000"),
        escala=[],
        minimo_no_imponible=Decimal("0"),
        deduccion_especial=Decimal("0"),
        ganancias_activo=True,
    )
    assert r == Decimal("0")


def test_ganancias_dos_tramos_calcula_correctamente(db):
    """2 tramos: [0, 1000000) al 5% fijo 0 ; [1000000, None) al 10% fijo 50000.
    bruto mensual = 200000 ; MNI = 50000/mes ; ded.especial = 30000/mes.
    ganancia_neta_anual = 200000*12 - 50000*12 - 30000*12 = 2400000-600000-360000 = 1440000
    cae en el 2do tramo (>=1000000): retencion_anual = 50000 + 10%*(1440000-1000000) = 50000+44000=94000
    retencion_mensual = 94000/12 = 7833.33"""
    tramos = _escala(db, tramos=[
        {"desde": 0, "hasta": 1000000, "alicuota": 0.05, "fijo": 0},
        {"desde": 1000000, "hasta": None, "alicuota": 0.10, "fijo": 50000},
    ])
    r = calcular_ganancias_4ta(
        bruto_mensual=Decimal("200000"),
        escala=tramos,
        minimo_no_imponible=Decimal("50000"),
        deduccion_especial=Decimal("30000"),
        ganancias_activo=True,
    )
    assert r == Decimal("7833.33")


def test_ganancias_ganancia_neta_negativa_retencion_cero(db):
    """Si MNI+deducción superan el bruto anualizado, no hay retención."""
    tramos = _escala(db, tramos=[{"desde": 0, "hasta": None, "alicuota": 0.27, "fijo": 0}])
    r = calcular_ganancias_4ta(
        bruto_mensual=Decimal("50000"),
        escala=tramos,
        minimo_no_imponible=Decimal("100000"),
        deduccion_especial=Decimal("50000"),
        ganancias_activo=True,
    )
    assert r == Decimal("0")


def test_ganancias_integrado_en_liquidacion_reduce_neto(db):
    """Activando ganancias_activo en ConfigSueldos, la liquidación descuenta
    retencion_ganancias del neto y la reporta en el detalle."""
    cfg = _cfg(db, aporte_jubilacion=0.11, aporte_inssjp=0.03, aporte_obra_social=0.03)
    cfg.ganancias_activo = True
    cfg.minimo_no_imponible = Decimal("0")
    cfg.deduccion_especial = Decimal("0")
    db.commit()
    _escala(db, tramos=[{"desde": 0, "hasta": None, "alicuota": 0.10, "fijo": 0}])
    _empleado(db, "Juan", basico=120000)  # bruto = 130000

    calc = calcular_liquidacion_periodo(db, 1, PERIODO)
    d = calc["detalle"][0]
    # ganancia_neta_anual = 130000*12 = 1560000 ; retencion_anual = 10%*1560000=156000
    # retencion_mensual = 156000/12 = 13000
    assert d["retencion_ganancias"] == Decimal("13000.00")
    # aportes = 130000*17% = 22100 ; neto = 130000 - 22100 - 13000 = 94900
    assert calc["total_neto"] == Decimal("94900.00")


def test_escala_ganancias_crud_admin(db, client):
    admin = _token(db, "admin@sueldos.test")
    r = client.post("/sueldos/escala-ganancias", json={
        "tramo_desde": 0, "tramo_hasta": 500000, "alicuota": 0.05, "monto_fijo": 0,
    }, headers=_auth(admin))
    assert r.status_code == 200
    tid = r.json()["id"]

    r = client.get("/sueldos/escala-ganancias", headers=_auth(admin))
    assert r.status_code == 200
    assert r.json()["total"] == 1

    r = client.put(f"/sueldos/escala-ganancias/{tid}", json={"alicuota": 0.07}, headers=_auth(admin))
    assert r.status_code == 200
    assert r.json()["alicuota"] == 0.07

    r = client.delete(f"/sueldos/escala-ganancias/{tid}", headers=_auth(admin))
    assert r.status_code == 200

    r = client.get("/sueldos/escala-ganancias", headers=_auth(admin))
    assert r.json()["total"] == 0


def test_escala_ganancias_post_requiere_admin_accounting(db, client):
    """revisor no tiene admin_accounting -> 403 al intentar editar la escala."""
    rev = _token(db, "rev@sueldos.test")
    r = client.post("/sueldos/escala-ganancias", json={
        "tramo_desde": 0, "tramo_hasta": None, "alicuota": 0.27, "monto_fijo": 0,
    }, headers=_auth(rev))
    assert r.status_code == 403


def test_config_acepta_campos_ganancias(db, client):
    admin = _token(db, "admin@sueldos.test")
    r = client.put("/sueldos/config", json={
        "activo": True,
        "aporte_jubilacion": 0.11, "aporte_inssjp": 0.03, "aporte_obra_social": 0.03,
        "contrib_jubilacion": 0.10, "contrib_inssjp": 0.0, "contrib_obra_social": 0.0,
        "contrib_asig_fam": 0.0, "contrib_fondo_desempleo": 0.0, "alicuota_art": 0.0,
        "ganancias_activo": True, "minimo_no_imponible": 100000, "deduccion_especial": 50000,
    }, headers=_auth(admin))
    assert r.status_code == 200
    body = r.json()
    assert body["ganancias_activo"] is True
    assert body["minimo_no_imponible"] == 100000.0
    assert body["deduccion_especial"] == 50000.0


# ── Recibo de sueldo en PDF ────────────────────────────────────────

def test_recibo_pdf_devuelve_pdf_valido(db, client):
    admin = _token(db, "admin@sueldos.test")
    _cfg(db, aporte_jubilacion=0.11, aporte_inssjp=0.03, aporte_obra_social=0.03,
         contrib_jubilacion=0.10)
    emp = _empleado(db, "Juan Recibo", basico=120000)

    r = client.post(f"/sueldos/liquidacion/calcular?periodo={PERIODO}", headers=_auth(admin))
    assert r.status_code == 200
    liq_id = r.json()["id"]

    r = client.get(
        f"/sueldos/liquidacion/{liq_id}/empleado/{emp.id}/recibo-pdf",
        headers=_auth(admin),
    )
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"
    assert "attachment" in r.headers.get("content-disposition", "")


def test_recibo_pdf_requiere_view_accounting(db, client):
    """Sin token (no autenticado) -> 401, no 500."""
    _cfg(db)
    emp = _empleado(db, "Sin Permiso", basico=100000)
    r = client.get(f"/sueldos/liquidacion/1/empleado/{emp.id}/recibo-pdf")
    assert r.status_code in (401, 403)


def test_recibo_pdf_404_liquidacion_inexistente(db, client):
    admin = _token(db, "admin@sueldos.test")
    emp = _empleado(db, "Fantasma", basico=100000)
    r = client.get(
        f"/sueldos/liquidacion/9999/empleado/{emp.id}/recibo-pdf",
        headers=_auth(admin),
    )
    assert r.status_code == 404


def test_recibo_pdf_404_empleado_sin_detalle(db, client):
    admin = _token(db, "admin@sueldos.test")
    _cfg(db, aporte_jubilacion=0.11)
    _empleado(db, "Juan En Liquidacion", basico=120000)
    otro = _empleado(db, "Otro Empleado Sin Detalle", basico=80000, activo=False)

    r = client.post(f"/sueldos/liquidacion/calcular?periodo={PERIODO}", headers=_auth(admin))
    liq_id = r.json()["id"]

    r = client.get(
        f"/sueldos/liquidacion/{liq_id}/empleado/{otro.id}/recibo-pdf",
        headers=_auth(admin),
    )
    assert r.status_code == 404


def test_recibo_pdf_incluye_retencion_ganancias_cuando_aplica(db, client):
    """Si ganancias_activo y hay retención > 0, el PDF se genera igual sin error
    (no testeamos el contenido del PDF en detalle, solo que no rompe)."""
    admin = _token(db, "admin@sueldos.test")
    cfg = _cfg(db, aporte_jubilacion=0.11, aporte_inssjp=0.03, aporte_obra_social=0.03,
               contrib_jubilacion=0.10)
    cfg.ganancias_activo = True
    cfg.minimo_no_imponible = Decimal("0")
    cfg.deduccion_especial = Decimal("0")
    db.commit()
    db.add(EscalaGanancias(
        organizacion_id=1, tramo_desde=Decimal("0"), tramo_hasta=None,
        alicuota=Decimal("0.10"), monto_fijo=Decimal("0"),
    ))
    db.commit()
    emp = _empleado(db, "Con Ganancias", basico=500000)

    r = client.post(f"/sueldos/liquidacion/calcular?periodo={PERIODO}", headers=_auth(admin))
    assert r.status_code == 200
    liq_id = r.json()["id"]
    det = next(d for d in r.json()["detalle"] if d["empleado_id"] == emp.id)
    assert det["retencion_ganancias"] > 0

    r = client.get(
        f"/sueldos/liquidacion/{liq_id}/empleado/{emp.id}/recibo-pdf",
        headers=_auth(admin),
    )
    assert r.status_code == 200
    assert r.content[:4] == b"%PDF"
