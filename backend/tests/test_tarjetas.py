"""Tests E2E del módulo de liquidaciones de tarjetas (Visa / Mastercard / Amex).

Usa FastAPI TestClient + SQLite en memoria (StaticPool). El plan de cuentas se
siembra con `seed_contabilidad_org` para que las 9 cuentas nuevas existan.

Cubre:
  - Las 9 cuentas nuevas del PLAN_PATCH están sembradas.
  - Invariante contable: si no balancea → 422.
  - Crear liquidación Visa → 201 + asiento de 6 líneas + partida doble.
  - Asiento agrupado balanceado (suma debe == suma haber).
  - Soft delete reversa el asiento (deja original + reverso).
  - Conciliar vincula el movimiento del extracto.
  - Multi-tenant: org 2 no ve datos de org 1 (NUNCA se toca org_id=1 con datos reales).
"""
import pytest
from decimal import Decimal
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.services.auth import get_password_hash, create_access_token
from app.services.seed_contable import seed_contabilidad_org
from app.models.organizacion import Organizacion
from app.models.user import User
from app.models.contabilidad import PlanCuenta, Asiento, AsientoDetalle
from app.models.extracto import ExtractoBancario, MovimientoBanco
from app.models.liquidacion_tarjeta import LiquidacionTarjeta


CUENTAS_NUEVAS = [
    "1-1-2-3", "1-1-2-4", "1-1-2-5", "1-1-2-6",
    "3-1-4-0", "3-2-3-0", "3-2-3-1", "3-2-3-2", "3-2-3-3",
]


# ── Fixtures ──────────────────────────────────────────────────────────────────

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

    # Dos orgs: 1 (con plan sembrado) y 2 (aislada, también sembrada)
    session.add(Organizacion(id=1, nombre="Org A"))
    session.add(Organizacion(id=2, nombre="Org Prueba"))
    session.commit()

    # Superadmin: puede operar/switch en cualquier org
    superadmin = User(
        email="super@tarjetas.test", full_name="Super",
        hashed_password=get_password_hash("pw123"),
        organizacion_id=1, is_active=True, role="admin", is_superadmin=True,
    )
    # Admin de org 1 (manage_finance + delete_records, sin switch de org)
    admin = User(
        email="admin@tarjetas.test", full_name="Admin",
        hashed_password=get_password_hash("pw123"),
        organizacion_id=1, is_active=True, role="admin", is_superadmin=False,
    )
    # Operador de org 1: NO delete_records
    operador = User(
        email="op@tarjetas.test", full_name="Operador",
        hashed_password=get_password_hash("pw123"),
        organizacion_id=1, is_active=True, role="operador", is_superadmin=False,
    )
    session.add_all([superadmin, admin, operador])
    session.commit()

    seed_contabilidad_org(session, 1)
    seed_contabilidad_org(session, 2)

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
    u = db.query(User).filter(User.email == email).first()
    return create_access_token({"sub": u.email, "user_id": u.id, "role": u.role})


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _payload_balanceado(marca="visa", **over):
    """Liquidación que balancea: bruto = neto + componentes."""
    p = {
        "marca": marca,
        "periodo": "2026-05",
        "fecha_acreditacion": "2026-05-31",
        "monto_bruto": 100000.00,
        "aranceles": 3000.00,
        "iva_df": 630.00,
        "percepciones_iibb": 1000.00,
        "retenciones": 500.00,
        "neto": 94870.00,   # 100000 - (3000+630+1000+500)
    }
    p.update(over)
    return p


def _crear_mov(db, org_id=1, monto=94870.00):
    ext = ExtractoBancario(nombre_archivo="ext.xlsx", creado_por=1, organizacion_id=org_id)
    db.add(ext)
    db.flush()
    mov = MovimientoBanco(
        extracto_id=ext.id, monto=Decimal(str(monto)), fecha=date(2026, 5, 31),
        titular="LIQUIDACION VISA", organizacion_id=org_id,
    )
    db.add(mov)
    db.commit()
    db.refresh(mov)
    return mov.id


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_cuentas_nuevas_en_plan(db):
    """Las 9 cuentas nuevas existen post-seed en cada org."""
    for org_id in (1, 2):
        codes = {
            c.codigo for c in db.query(PlanCuenta)
            .filter(PlanCuenta.organizacion_id == org_id).all()
        }
        for cod in CUENTAS_NUEVAS:
            assert cod in codes, f"Falta cuenta {cod} en org {org_id}"


def test_invariante_no_balancea(client, db):
    """Si neto + componentes != bruto → HTTP 422."""
    tok = _token(db, "admin@tarjetas.test")
    bad = _payload_balanceado(neto=90000.00)  # rompe el balance
    r = client.post("/tarjetas", json=bad, headers=_auth(tok))
    assert r.status_code == 422, r.text
    assert "balancea" in r.text.lower()


def test_crear_liquidacion_visa(client, db):
    """POST Visa → 201, asiento con 6 líneas, partida doble cuadrada."""
    tok = _token(db, "admin@tarjetas.test")
    r = client.post("/tarjetas", json=_payload_balanceado("visa"), headers=_auth(tok))
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["marca"] == "visa"
    assert data["estado"] == "pendiente"
    assert data["asiento_id"] is not None

    asiento = db.query(Asiento).filter(Asiento.id == data["asiento_id"]).first()
    assert asiento is not None
    assert asiento.modulo == "tarjeta_liq"
    detalles = db.query(AsientoDetalle).filter(AsientoDetalle.asiento_id == asiento.id).all()
    # 6 líneas: banco, arancel, iva, iibb, retenciones (D) + ingresos (H)
    assert len(detalles) == 6, [(d.debe, d.haber) for d in detalles]

    # El arancel de Visa va a 3-2-3-1
    cta_arancel = db.query(PlanCuenta).filter(
        PlanCuenta.codigo == "3-2-3-1", PlanCuenta.organizacion_id == 1).first()
    arancel_line = [d for d in detalles if d.cuenta_id == cta_arancel.id]
    assert arancel_line and arancel_line[0].debe == Decimal("3000.00")


def test_asiento_agrupado_partida_doble(client, db):
    """Suma debe == suma haber == monto bruto."""
    tok = _token(db, "admin@tarjetas.test")
    r = client.post("/tarjetas", json=_payload_balanceado("mastercard"), headers=_auth(tok))
    assert r.status_code == 201, r.text
    asiento_id = r.json()["asiento_id"]
    detalles = db.query(AsientoDetalle).filter(AsientoDetalle.asiento_id == asiento_id).all()
    total_debe = sum(d.debe for d in detalles)
    total_haber = sum(d.haber for d in detalles)
    assert total_debe == total_haber == Decimal("100000.00")


def test_soft_delete_reversa_asiento(client, db):
    """DELETE → soft delete + asiento de reverso. El original queda."""
    tok = _token(db, "admin@tarjetas.test")
    r = client.post("/tarjetas", json=_payload_balanceado("amex"), headers=_auth(tok))
    liq_id = r.json()["id"]
    asiento_id = r.json()["asiento_id"]

    rd = client.delete(f"/tarjetas/{liq_id}", headers=_auth(tok))
    assert rd.status_code == 200, rd.text

    liq = db.query(LiquidacionTarjeta).filter(LiquidacionTarjeta.id == liq_id).first()
    assert liq.deleted_at is not None
    assert liq.estado == "anulada"

    # Ya no aparece en el listado
    rl = client.get("/tarjetas", headers=_auth(tok))
    assert all(item["id"] != liq_id for item in rl.json()["items"])

    # El asiento original sigue + hay un reverso (tarjeta_liq_reverso).
    # reversar_asientos fija referencia_id = id del asiento original.
    assert db.query(Asiento).filter(Asiento.id == asiento_id).first() is not None
    reverso = db.query(Asiento).filter(
        Asiento.modulo == "tarjeta_liq_reverso",
        Asiento.referencia_id == asiento_id,
    ).first()
    assert reverso is not None
    # Reverso cuadra en partida doble
    rd = db.query(AsientoDetalle).filter(AsientoDetalle.asiento_id == reverso.id).all()
    assert sum(d.debe for d in rd) == sum(d.haber for d in rd) == Decimal("100000.00")


def test_operador_no_puede_borrar(client, db):
    """El operador no tiene delete_records → 403."""
    tok_admin = _token(db, "admin@tarjetas.test")
    r = client.post("/tarjetas", json=_payload_balanceado("visa"), headers=_auth(tok_admin))
    liq_id = r.json()["id"]

    tok_op = _token(db, "op@tarjetas.test")
    rd = client.delete(f"/tarjetas/{liq_id}", headers=_auth(tok_op))
    assert rd.status_code == 403


def test_conciliar_vincula_movimiento(client, db):
    """PATCH /conciliar vincula el movimiento y deja estado conciliada."""
    tok = _token(db, "admin@tarjetas.test")
    r = client.post("/tarjetas", json=_payload_balanceado("visa"), headers=_auth(tok))
    liq_id = r.json()["id"]
    mov_id = _crear_mov(db, org_id=1)

    rc = client.patch(f"/tarjetas/{liq_id}/conciliar",
                      json={"extracto_movimiento_id": mov_id}, headers=_auth(tok))
    assert rc.status_code == 200, rc.text
    data = rc.json()
    assert data["estado"] == "conciliada"
    assert data["extracto_movimiento_id"] == mov_id


def test_multitenancy(client, db):
    """Org 2 (vía superadmin con ?org_id=2) no ve liquidaciones de org 1."""
    tok_admin = _token(db, "admin@tarjetas.test")
    # Liquidación en org 1
    client.post("/tarjetas", json=_payload_balanceado("visa"), headers=_auth(tok_admin))

    tok_super = _token(db, "super@tarjetas.test")
    # Liquidación en org 2
    r2 = client.post("/tarjetas?org_id=2", json=_payload_balanceado("mastercard"),
                     headers=_auth(tok_super))
    assert r2.status_code == 201, r2.text
    assert r2.json()["organizacion_id"] == 2

    # Listado de org 2 NO incluye la de org 1
    lst2 = client.get("/tarjetas?org_id=2", headers=_auth(tok_super)).json()
    assert lst2["total"] == 1
    assert all(item["organizacion_id"] == 2 for item in lst2["items"])

    # Listado de org 1 NO incluye la de org 2
    lst1 = client.get("/tarjetas", headers=_auth(tok_admin)).json()
    assert lst1["total"] == 1
    assert all(item["organizacion_id"] == 1 for item in lst1["items"])
