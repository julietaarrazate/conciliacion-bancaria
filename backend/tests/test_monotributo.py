"""Tests del módulo Control Semestral Monotributo.

Cubre:
  - cálculo de ingresos_12m con asientos dentro/fuera de la ventana de 12 meses.
  - evaluar_categoria: dentro, cerca del límite, excede la actual (sugiere superior),
    excede TODAS las categorías (excede=True).
  - idempotencia de guardar_o_actualizar_control (upsert, no duplica).
  - marcar_revisado no se pisa con recálculo posterior.
  - error si el módulo no está activo → 400 vía API.
  - permisos: 403 sin admin_accounting (config/categorias), 403 sin manage_finance (calcular).
  - end-to-end API: activar config → calcular → historial → marcar revisado.
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
from app.services.monotributo_service import (
    calcular_ingresos_12m,
    evaluar_categoria,
    calcular_control_semestral,
    guardar_o_actualizar_control,
    marcar_revisado,
    seed_monotributo_categorias,
    MonotributoServiceError,
)
from app.models.organizacion import Organizacion
from app.models.user import User
from app.models.contabilidad import PlanCuenta, Asiento, AsientoDetalle
from app.models.monotributo import (
    CategoriaMonotributo, MonotributoConfig, ControlMonotributo,
)


PERIODO = "2026-S1"  # corte 30/jun/2026 → ventana [1/jul/2025, 30/jun/2026]


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

    org = Organizacion(id=1, nombre="OrgMono")
    session.add(org)
    session.commit()

    seed_contabilidad_org(session, 1)
    seed_monotributo_categorias(session, 1)

    admin = User(
        email="admin@mono.test", full_name="Admin Mono",
        hashed_password=get_password_hash("pw123"),
        organizacion_id=1, is_active=True, role="admin", is_superadmin=False,
    )
    revisor = User(
        email="rev@mono.test", full_name="Revisor Mono",
        hashed_password=get_password_hash("pw123"),
        organizacion_id=1, is_active=True, role="revisor", is_superadmin=False,
    )
    operador = User(
        email="op@mono.test", full_name="Operador Mono",
        hashed_password=get_password_hash("pw123"),
        organizacion_id=1, is_active=True, role="operador", is_superadmin=False,
    )
    session.add_all([admin, revisor, operador])
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


def _cuenta(db, codigo):
    return db.query(PlanCuenta).filter(
        PlanCuenta.codigo == codigo, PlanCuenta.organizacion_id == 1
    ).first()


def _asiento(db, fecha, lineas):
    """lineas = [(codigo, debe, haber), ...]"""
    a = Asiento(fecha=fecha, descripcion="test", modulo="test", organizacion_id=1)
    db.add(a)
    db.flush()
    for codigo, debe, haber in lineas:
        c = _cuenta(db, codigo)
        db.add(AsientoDetalle(
            asiento_id=a.id, cuenta_id=c.id,
            debe=Decimal(str(debe)), haber=Decimal(str(haber)),
        ))
    db.commit()
    return a


def _ingreso(db, fecha, monto):
    """Asiento de ingreso: Banco D / Comisiones (3-1-1-0, ingreso) H."""
    _asiento(db, fecha, [
        ("1-1-1-3-1", monto, 0),
        ("3-1-1-0", 0, monto),
    ])


def _activar_config(db, categoria="A", tipo="servicios"):
    cfg = MonotributoConfig(
        organizacion_id=1, activo=True,
        categoria_actual=categoria, tipo_actividad=tipo,
    )
    db.add(cfg)
    db.commit()
    return cfg


def _set_limite(db, categoria, tipo, limite):
    c = db.query(CategoriaMonotributo).filter(
        CategoriaMonotributo.organizacion_id == 1,
        CategoriaMonotributo.categoria == categoria,
        CategoriaMonotributo.tipo_actividad == tipo,
    ).first()
    c.limite_anual = Decimal(str(limite))
    db.commit()


# ── Seed ───────────────────────────────────────────────────────────

def test_seed_categorias(db):
    """Servicios A-H (8) + bienes A-K (11) = 19 categorías, idempotente."""
    n = seed_monotributo_categorias(db, 1)  # ya sembrado en fixture → 0
    assert n == 0
    total = db.query(CategoriaMonotributo).filter(
        CategoriaMonotributo.organizacion_id == 1
    ).count()
    assert total == 19
    serv = db.query(CategoriaMonotributo).filter(
        CategoriaMonotributo.organizacion_id == 1,
        CategoriaMonotributo.tipo_actividad == "servicios",
    ).count()
    bienes = db.query(CategoriaMonotributo).filter(
        CategoriaMonotributo.organizacion_id == 1,
        CategoriaMonotributo.tipo_actividad == "bienes",
    ).count()
    assert serv == 8
    assert bienes == 11


# ── Ingresos 12m ───────────────────────────────────────────────────

def test_ingresos_12m_dentro_y_fuera_de_ventana(db):
    """Ventana S1 2026 = [1/jul/2025, 30/jun/2026]."""
    _ingreso(db, date(2025, 7, 15), 100000)   # dentro
    _ingreso(db, date(2026, 6, 30), 50000)    # dentro (borde)
    _ingreso(db, date(2025, 6, 30), 999999)   # fuera (antes de la ventana)
    _ingreso(db, date(2026, 7, 1), 888888)    # fuera (después del corte)

    desde, hasta = date(2025, 7, 1), date(2026, 6, 30)
    total, detalle = calcular_ingresos_12m(db, 1, desde, hasta)
    assert total == Decimal("150000.00")
    # 2 meses con movimiento
    assert {d["mes"] for d in detalle} == {"2025-07", "2026-06"}


def test_ingresos_12m_neto_haber_menos_debe(db):
    """Un débito en cuenta de ingreso (devolución) resta del total."""
    _ingreso(db, date(2026, 1, 10), 100000)
    _asiento(db, date(2026, 2, 5), [
        ("3-1-1-0", 30000, 0),   # débito en ingreso (devolución)
        ("1-1-1-3-1", 0, 30000),
    ])
    desde, hasta = date(2025, 7, 1), date(2026, 6, 30)
    total, _ = calcular_ingresos_12m(db, 1, desde, hasta)
    assert total == Decimal("70000.00")


# ── evaluar_categoria ──────────────────────────────────────────────

def test_evaluar_categoria_dentro(db):
    # límites conocidos para servicios
    _set_limite(db, "A", "servicios", 1000000)
    _set_limite(db, "B", "servicios", 2000000)
    cat, limite, excede = evaluar_categoria(db, 1, "servicios", Decimal("500000"))
    assert cat == "A"
    assert limite == Decimal("1000000.00")
    assert excede is False


def test_evaluar_categoria_borde_exacto(db):
    _set_limite(db, "A", "servicios", 1000000)
    cat, limite, excede = evaluar_categoria(db, 1, "servicios", Decimal("1000000"))
    assert cat == "A"  # <= limite entra en A
    assert excede is False


def test_evaluar_categoria_excede_actual_sugiere_superior(db):
    _set_limite(db, "A", "servicios", 1000000)
    _set_limite(db, "B", "servicios", 2000000)
    cat, limite, excede = evaluar_categoria(db, 1, "servicios", Decimal("1500000"))
    assert cat == "B"   # supera A → sugiere B
    assert excede is False


def test_evaluar_categoria_excede_todas(db):
    # H es la última de servicios; le ponemos un tope bajo y superamos
    _set_limite(db, "H", "servicios", 5000000)
    cat, limite, excede = evaluar_categoria(db, 1, "servicios", Decimal("999999999"))
    assert cat == "H"   # la más alta disponible
    assert excede is True


def test_evaluar_categoria_sin_categorias_falla(db):
    # org sin categorías para "bienes" inexistente
    db.query(CategoriaMonotributo).filter(
        CategoriaMonotributo.tipo_actividad == "bienes"
    ).delete()
    db.commit()
    with pytest.raises(MonotributoServiceError):
        evaluar_categoria(db, 1, "bienes", Decimal("100"))


# ── calcular_control_semestral ─────────────────────────────────────

def test_control_requiere_modulo_activo(db):
    """Sin config (o activo=False) → MonotributoServiceError."""
    with pytest.raises(MonotributoServiceError):
        calcular_control_semestral(db, 1, PERIODO)


def test_control_porcentaje_uso(db):
    _activar_config(db, categoria="A", tipo="servicios")
    _set_limite(db, "A", "servicios", 1000000)
    _set_limite(db, "B", "servicios", 2000000)
    _ingreso(db, date(2026, 3, 10), 875000)

    calc = calcular_control_semestral(db, 1, PERIODO)
    assert calc["ingresos_12m"] == Decimal("875000.00")
    assert calc["categoria_actual"] == "A"
    assert calc["limite_categoria_actual"] == Decimal("1000000.00")
    assert calc["porcentaje_uso"] == Decimal("87.50")
    assert calc["categoria_sugerida"] == "A"
    assert calc["excede"] is False
    assert calc["fecha_corte"] == date(2026, 6, 30)


def test_periodo_invalido(db):
    _activar_config(db)
    with pytest.raises(MonotributoServiceError):
        calcular_control_semestral(db, 1, "2026-13")
    with pytest.raises(MonotributoServiceError):
        calcular_control_semestral(db, 1, "basura")
    with pytest.raises(MonotributoServiceError):
        calcular_control_semestral(db, 1, "2026-S3")


# ── Persistencia / idempotencia ────────────────────────────────────

def test_guardar_es_idempotente(db):
    _activar_config(db, categoria="A")
    _set_limite(db, "A", "servicios", 1000000)
    _ingreso(db, date(2026, 3, 10), 500000)

    c1 = guardar_o_actualizar_control(db, 1, PERIODO)
    id1 = c1.id
    assert c1.ingresos_12m == Decimal("500000.00")

    _ingreso(db, date(2026, 4, 10), 200000)
    c2 = guardar_o_actualizar_control(db, 1, PERIODO)

    assert c2.id == id1
    assert db.query(ControlMonotributo).filter(
        ControlMonotributo.organizacion_id == 1, ControlMonotributo.periodo == PERIODO
    ).count() == 1
    assert c2.ingresos_12m == Decimal("700000.00")


def test_revisado_no_se_pisa(db):
    _activar_config(db, categoria="A")
    _set_limite(db, "A", "servicios", 1000000)
    _ingreso(db, date(2026, 3, 10), 500000)

    guardar_o_actualizar_control(db, 1, PERIODO)
    c = marcar_revisado(db, 1, PERIODO)
    assert c.estado == "revisado"
    assert c.fecha_revision is not None
    ingresos_revisado = c.ingresos_12m

    # Agregar ingresos y recalcular: queda igual
    _ingreso(db, date(2026, 5, 10), 999999)
    c2 = guardar_o_actualizar_control(db, 1, PERIODO)
    assert c2.estado == "revisado"
    assert c2.ingresos_12m == ingresos_revisado


def test_marcar_revisado_sin_control_falla(db):
    _activar_config(db)
    with pytest.raises(MonotributoServiceError):
        marcar_revisado(db, 1, PERIODO)


# ── Permisos / API ─────────────────────────────────────────────────

def test_config_requiere_admin_accounting(db, client):
    token = _token(db, "rev@mono.test")  # solo view_accounting
    r = client.get("/monotributo/config", headers=_auth(token))
    assert r.status_code == 403


def test_categorias_view_ok_pero_put_requiere_admin(db, client):
    rev = _token(db, "rev@mono.test")
    r = client.get("/monotributo/categorias", headers=_auth(rev))
    assert r.status_code == 200
    data = r.json()
    assert "items" in data and data["total"] == 19

    cat = db.query(CategoriaMonotributo).filter(
        CategoriaMonotributo.organizacion_id == 1
    ).first()
    r = client.put(f"/monotributo/categorias/{cat.id}",
                   json={"limite_anual": 12345.0}, headers=_auth(rev))
    assert r.status_code == 403


def test_calcular_requiere_manage_finance(db, client):
    """El revisor (view_accounting, sin manage_finance) no puede persistir."""
    _activar_config(db)
    rev = _token(db, "rev@mono.test")
    r = client.post(f"/monotributo/control/calcular?periodo={PERIODO}", headers=_auth(rev))
    assert r.status_code == 403


def test_control_modulo_inactivo_400(db, client):
    """Sin config activa → 400 vía API."""
    token = _token(db, "admin@mono.test")
    r = client.get(f"/monotributo/control?periodo={PERIODO}", headers=_auth(token))
    assert r.status_code == 400


def test_end_to_end_api(db, client):
    admin = _token(db, "admin@mono.test")

    # 1. activar config
    r = client.put("/monotributo/config",
                   json={"activo": True, "categoria_actual": "A", "tipo_actividad": "servicios"},
                   headers=_auth(admin))
    assert r.status_code == 200
    assert r.json()["activo"] is True

    # 2. ajustar límite de A
    cat_a = db.query(CategoriaMonotributo).filter(
        CategoriaMonotributo.organizacion_id == 1,
        CategoriaMonotributo.categoria == "A",
        CategoriaMonotributo.tipo_actividad == "servicios",
    ).first()
    r = client.put(f"/monotributo/categorias/{cat_a.id}",
                   json={"limite_anual": 1000000.0}, headers=_auth(admin))
    assert r.status_code == 200
    assert r.json()["limite_anual"] == 1000000.0

    # ingreso
    _ingreso(db, date(2026, 3, 1), 600000)

    # 3. preview
    r = client.get(f"/monotributo/control?periodo={PERIODO}", headers=_auth(admin))
    assert r.status_code == 200
    assert float(r.json()["ingresos_12m"]) == 600000.0

    # 4. calcular y persistir
    r = client.post(f"/monotributo/control/calcular?periodo={PERIODO}", headers=_auth(admin))
    assert r.status_code == 200
    cid = r.json()["id"]
    assert r.json()["estado"] == "pendiente"

    # 5. historial
    r = client.get("/monotributo/historial", headers=_auth(admin))
    assert r.status_code == 200
    assert r.json()["total"] == 1

    # 6. marcar revisado
    r = client.post(f"/monotributo/control/{cid}/marcar-revisado", headers=_auth(admin))
    assert r.status_code == 200
    assert r.json()["estado"] == "revisado"
