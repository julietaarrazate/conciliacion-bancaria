"""Tests del módulo IVA Proyección y DDJJ.

Cubre:
  - cálculo de proyección con datos sintéticos (débito/crédito/saldo).
  - crédito fiscal real (cuenta 1-1-2-4) sumado al proyectado.
  - idempotencia de guardar_o_actualizar_proyeccion (upsert, no duplica).
  - marcar_presentada no se pisa con un recálculo posterior.
  - permisos: 403 al configurar tasa sin admin_accounting.
  - validación: 400 al setear tasa en cuenta no-hoja.
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
from app.services.iva_service import (
    calcular_proyeccion_iva,
    guardar_o_actualizar_proyeccion,
    marcar_presentada,
    IvaServiceError,
)
from app.models.organizacion import Organizacion
from app.models.user import User
from app.models.contabilidad import PlanCuenta, Asiento, AsientoDetalle
from app.models.proyeccion_iva import ProyeccionIva


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

    org = Organizacion(id=1, nombre="OrgIva")
    session.add(org)
    session.commit()

    seed_contabilidad_org(session, 1)

    admin = User(
        email="admin@iva.test", full_name="Admin Iva",
        hashed_password=get_password_hash("pw123"),
        organizacion_id=1, is_active=True, role="admin", is_superadmin=False,
    )
    revisor = User(
        email="rev@iva.test", full_name="Revisor Iva",
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


def _gravar(db, codigo, tasa):
    c = _cuenta(db, codigo)
    c.tasa_iva = Decimal(str(tasa))
    db.commit()


# ── Cálculo ────────────────────────────────────────────────────────

def test_calculo_basico_debito_credito_saldo(db):
    """Ingreso gravado 21% (haber) → débito; gasto gravado 21% (debe) → crédito."""
    # Ingreso por tarjetas 3-1-4-0 gravado 21%
    _gravar(db, "3-1-4-0", 0.21)
    # Gasto: comisiones tarjetas 3-2-3-0 gravado 21%
    _gravar(db, "3-2-3-0", 0.21)

    # Asiento: venta 100000 (ingreso en haber)
    _asiento(db, date(2026, 6, 10), [
        ("1-1-1-3-1", 100000, 0),
        ("3-1-4-0", 0, 100000),
    ])
    # Asiento: gasto 50000 (gasto en debe)
    _asiento(db, date(2026, 6, 15), [
        ("3-2-3-0", 50000, 0),
        ("1-1-1-3-1", 0, 50000),
    ])

    calc = calcular_proyeccion_iva(db, 1, PERIODO)
    assert calc["debito_fiscal"] == Decimal("21000.00")
    assert calc["credito_fiscal_proyectado"] == Decimal("10500.00")
    assert calc["credito_fiscal_real"] == Decimal("0.00")
    assert calc["credito_fiscal"] == Decimal("10500.00")
    assert calc["saldo"] == Decimal("10500.00")  # 21000 - 10500
    assert len(calc["detalle"]) == 2


def test_credito_fiscal_real_sumado(db):
    """El crédito fiscal real (1-1-2-4 en debe) se suma al proyectado."""
    _gravar(db, "3-1-4-0", 0.21)
    # Venta gravada
    _asiento(db, date(2026, 6, 5), [
        ("1-1-1-3-1", 100000, 0),
        ("3-1-4-0", 0, 100000),
    ])
    # IVA crédito real contabilizado (ej. liquidación tarjeta): 1-1-2-4 en debe
    _asiento(db, date(2026, 6, 8), [
        ("1-1-2-4", 5000, 0),
        ("1-1-1-3-1", 0, 5000),
    ])

    calc = calcular_proyeccion_iva(db, 1, PERIODO)
    assert calc["debito_fiscal"] == Decimal("21000.00")
    assert calc["credito_fiscal_real"] == Decimal("5000.00")
    assert calc["credito_fiscal_proyectado"] == Decimal("0.00")
    assert calc["credito_fiscal"] == Decimal("5000.00")
    assert calc["saldo"] == Decimal("16000.00")


def test_fuera_del_periodo_no_cuenta(db):
    """Asientos de otro mes no entran en la proyección."""
    _gravar(db, "3-1-4-0", 0.21)
    _asiento(db, date(2026, 5, 31), [  # mayo, no junio
        ("1-1-1-3-1", 100000, 0),
        ("3-1-4-0", 0, 100000),
    ])
    calc = calcular_proyeccion_iva(db, 1, PERIODO)
    assert calc["debito_fiscal"] == Decimal("0.00")
    assert calc["saldo"] == Decimal("0.00")


def test_periodo_invalido(db):
    with pytest.raises(IvaServiceError):
        calcular_proyeccion_iva(db, 1, "2026-13")
    with pytest.raises(IvaServiceError):
        calcular_proyeccion_iva(db, 1, "basura")


# ── Persistencia / idempotencia ────────────────────────────────────

def test_guardar_es_idempotente(db):
    """Recalcular no duplica el registro (upsert por org+período)."""
    _gravar(db, "3-1-4-0", 0.21)
    _asiento(db, date(2026, 6, 10), [
        ("1-1-1-3-1", 100000, 0),
        ("3-1-4-0", 0, 100000),
    ])
    p1 = guardar_o_actualizar_proyeccion(db, 1, PERIODO)
    id1 = p1.id
    assert p1.debito_fiscal == Decimal("21000.00")

    # Nuevo asiento → recalcular debe ACTUALIZAR el mismo registro
    _asiento(db, date(2026, 6, 20), [
        ("1-1-1-3-1", 50000, 0),
        ("3-1-4-0", 0, 50000),
    ])
    p2 = guardar_o_actualizar_proyeccion(db, 1, PERIODO)

    assert p2.id == id1  # mismo registro
    assert db.query(ProyeccionIva).filter(
        ProyeccionIva.organizacion_id == 1, ProyeccionIva.periodo == PERIODO
    ).count() == 1
    assert p2.debito_fiscal == Decimal("31500.00")  # (100k+50k)*0.21


def test_presentada_no_se_pisa(db):
    """Una proyección presentada NO se recalcula ni se sobrescribe."""
    _gravar(db, "3-1-4-0", 0.21)
    _asiento(db, date(2026, 6, 10), [
        ("1-1-1-3-1", 100000, 0),
        ("3-1-4-0", 0, 100000),
    ])
    guardar_o_actualizar_proyeccion(db, 1, PERIODO)
    p = marcar_presentada(db, 1, PERIODO)
    assert p.estado == "presentado"
    assert p.fecha_presentacion is not None
    debito_presentado = p.debito_fiscal

    # Agregar más ingresos y recalcular: debe quedar igual
    _asiento(db, date(2026, 6, 25), [
        ("1-1-1-3-1", 999999, 0),
        ("3-1-4-0", 0, 999999),
    ])
    p2 = guardar_o_actualizar_proyeccion(db, 1, PERIODO)
    assert p2.estado == "presentado"
    assert p2.debito_fiscal == debito_presentado  # no cambió


def test_marcar_presentada_sin_proyeccion_falla(db):
    with pytest.raises(IvaServiceError):
        marcar_presentada(db, 1, PERIODO)


# ── Permisos / validación (vía API) ────────────────────────────────

def test_config_requiere_admin_accounting(db, client):
    """El revisor (solo view_accounting) no puede configurar tasa → 403."""
    token = _token(db, "rev@iva.test")
    r = client.get("/iva/config", headers=_auth(token))
    assert r.status_code == 403


def test_config_admin_ok(db, client):
    token = _token(db, "admin@iva.test")
    r = client.get("/iva/config", headers=_auth(token))
    assert r.status_code == 200
    data = r.json()
    assert "items" in data and "total" in data
    # Solo cuentas hoja de tipo resultado
    assert all(it["tipo"] == "resultado" for it in data["items"])


def test_set_tasa_cuenta_no_hoja_falla(db, client):
    """Setear tasa en una cuenta con subcuentas → 400."""
    token = _token(db, "admin@iva.test")
    # 3-1-0-0 Ingresos tiene hijos (3-1-1-0, etc.)
    madre = _cuenta(db, "3-1-0-0")
    r = client.put(f"/iva/config/{madre.id}", json={"tasa_iva": 0.21}, headers=_auth(token))
    assert r.status_code == 400


def test_set_tasa_hoja_ok(db, client):
    token = _token(db, "admin@iva.test")
    hoja = _cuenta(db, "3-1-4-0")  # Ingresos por tarjetas (hoja)
    r = client.put(f"/iva/config/{hoja.id}", json={"tasa_iva": 0.21}, headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["tasa_iva"] == 0.21
    db.refresh(hoja)
    assert hoja.tasa_iva == Decimal("0.2100")


def test_preview_y_calcular_via_api(db, client):
    _gravar(db, "3-1-4-0", 0.21)
    _asiento(db, date(2026, 6, 10), [
        ("1-1-1-3-1", 100000, 0),
        ("3-1-4-0", 0, 100000),
    ])
    token = _token(db, "admin@iva.test")
    # preview (view_accounting)
    r = client.get(f"/iva/proyeccion?periodo={PERIODO}", headers=_auth(token))
    assert r.status_code == 200
    assert float(r.json()["debito_fiscal"]) == 21000.0

    # calcular + persistir (manage_finance)
    r = client.post(f"/iva/proyeccion/calcular?periodo={PERIODO}", headers=_auth(token))
    assert r.status_code == 200
    pid = r.json()["id"]
    assert r.json()["estado"] == "proyectado"

    # historial
    r = client.get("/iva/historial", headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["total"] == 1

    # marcar presentada (admin_accounting)
    r = client.post(f"/iva/proyeccion/{pid}/marcar-presentada", headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["estado"] == "presentado"
