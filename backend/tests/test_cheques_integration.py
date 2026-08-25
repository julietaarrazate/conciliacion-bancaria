"""
Tests de integración para el módulo de cheques vía FastAPI TestClient.

Cubre:
- Ciclo completo: crear → acreditar → rechazar
- Error 400 al crear cheque sin cuenta contable en el cliente
- Error 400 al rechazar un cheque que no está acreditado
- Eliminar cheque registrado → crea asiento reverso
"""
import pytest

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
from app.models.cliente import Cliente
from app.models.cheque import Cheque
from app.models.contabilidad import PlanCuenta, Asiento


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def db():
    """DB SQLite en memoria con org, usuarios y plan de cuentas completo."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    org = Organizacion(id=1, nombre="OrgCheques")
    session.add(org)
    session.commit()

    # Sembrar plan de cuentas completo (incluye 1-1-2-1, 2-1-2-0, 3-1-3-0, etc.)
    seed_contabilidad_org(session, 1)

    admin = User(
        email="admin@cheques.test", full_name="Admin Cheques",
        hashed_password=get_password_hash("pw123"),
        organizacion_id=1, is_active=True, role="admin", is_superadmin=False,
    )
    session.add(admin)
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


def _banco_cuenta_id(db):
    """Retorna el id de la cuenta 'Banco Macro' (1-1-1-3-1) del plan de cuentas."""
    c = db.query(PlanCuenta).filter(
        PlanCuenta.codigo == "1-1-1-3-1", PlanCuenta.organizacion_id == 1
    ).first()
    assert c is not None, "Cuenta 1-1-1-3-1 no existe en el plan de cuentas"
    return c.id


def _crear_cliente_con_cuenta(db, nombre="ClienteTest"):
    """Crea un cliente con cuenta contable vinculada (2-1-2-X)."""
    # Obtener la cuenta padre 2-1-2-0
    padre = db.query(PlanCuenta).filter(
        PlanCuenta.codigo == "2-1-2-0", PlanCuenta.organizacion_id == 1
    ).first()
    assert padre is not None, "Cuenta padre 2-1-2-0 no existe"

    # Crear la cuenta hoja del cliente
    cuenta = PlanCuenta(
        codigo="2-1-2-99",
        nombre=nombre,
        tipo="pasivo",
        nivel=5,
        activo=True,
        organizacion_id=1,
        parent_id=padre.id,
    )
    db.add(cuenta)
    db.flush()

    cliente = Cliente(
        nombre=nombre,
        organizacion_id=1,
        cuenta_contable_id=cuenta.id,
    )
    db.add(cliente)
    db.commit()
    db.refresh(cliente)
    return cliente


def _crear_cliente_sin_cuenta(db, nombre="ClienteSinCuenta"):
    """Crea un cliente SIN cuenta contable."""
    cliente = Cliente(nombre=nombre, organizacion_id=1)
    db.add(cliente)
    db.commit()
    db.refresh(cliente)
    return cliente


# ── Tests: crear cheque ───────────────────────────────────────────────────────

class TestCrearCheque:

    def test_crear_cheque_happy_path(self, client, db):
        """POST /cheques con cliente con cuenta → 200, estado 'registrado'."""
        token = _token(db, "admin@cheques.test")
        cli = _crear_cliente_con_cuenta(db)

        r = client.post(
            "/cheques",
            json={
                "cliente_id": cli.id,
                "monto": 5000.0,
                "comision": 0.0,
                "librador": "Juan Pérez",
                "numero": "12345678",
                "banco_origen": "Banco Test",
                "fecha_deposito": "2026-06-10",
            },
            headers=_auth(token),
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["estado"] == "registrado"
        assert data["cliente_id"] == cli.id
        assert float(data["monto"]) == 5000.0

    def test_crear_cheque_genera_asiento_registro(self, client, db):
        """Crear cheque genera asiento 'cheque_registro' en el libro diario."""
        token = _token(db, "admin@cheques.test")
        cli = _crear_cliente_con_cuenta(db)

        r = client.post(
            "/cheques",
            json={"cliente_id": cli.id, "monto": 3000.0, "comision": 60.0,
                  "fecha_deposito": "2026-06-10"},
            headers=_auth(token),
        )
        assert r.status_code == 200
        cheque_id = r.json()["id"]

        asientos = db.query(Asiento).filter(
            Asiento.modulo == "cheque_registro",
            Asiento.referencia_id == cheque_id,
        ).all()
        assert len(asientos) == 1, "Debe existir un asiento cheque_registro"
        # Con comisión → 3 líneas
        assert len(asientos[0].lineas) == 3

    def test_crear_cheque_sin_cuenta_contable_retorna_400(self, client, db):
        """Cliente sin cuenta contable → HTTP 400 con mensaje descriptivo."""
        token = _token(db, "admin@cheques.test")
        cli = _crear_cliente_sin_cuenta(db)

        r = client.post(
            "/cheques",
            json={"cliente_id": cli.id, "monto": 1000.0, "comision": 0.0},
            headers=_auth(token),
        )
        assert r.status_code == 400
        assert "cuenta contable" in r.json()["detail"].lower()

    def test_crear_cheque_sin_auth_retorna_401_o_403(self, client):
        r = client.post("/cheques", json={"monto": 100.0})
        assert r.status_code in (401, 403)


# ── Tests: acreditar cheque ───────────────────────────────────────────────────

class TestAcreditarCheque:

    def _crear_cheque(self, client, db, token, cli):
        r = client.post(
            "/cheques",
            json={"cliente_id": cli.id, "monto": 10000.0, "comision": 200.0,
                  "fecha_deposito": "2026-06-10"},
            headers=_auth(token),
        )
        assert r.status_code == 200
        return r.json()["id"]

    def test_acreditar_cheque_happy_path(self, client, db):
        """POST /cheques/{id}/acreditar → estado 'acreditado', 2 asientos nuevos."""
        token = _token(db, "admin@cheques.test")
        cli = _crear_cliente_con_cuenta(db)
        cheque_id = self._crear_cheque(client, db, token, cli)
        banco_id = _banco_cuenta_id(db)

        r = client.post(
            f"/cheques/{cheque_id}/acreditar",
            json={"banco_cuenta_id": banco_id, "fecha_acred": "2026-06-11"},
            headers=_auth(token),
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["estado"] == "acreditado"
        assert data["banco_cuenta_id"] == banco_id

        # Verificar que se crearon los 2 asientos de acreditación
        banco_asientos = db.query(Asiento).filter(
            Asiento.modulo == "cheque_acred_banco",
            Asiento.referencia_id == cheque_id,
        ).all()
        cliente_asientos = db.query(Asiento).filter(
            Asiento.modulo == "cheque_acred_cliente",
            Asiento.referencia_id == cheque_id,
        ).all()
        assert len(banco_asientos) == 1
        assert len(cliente_asientos) == 1

    def test_acreditar_cheque_ya_acreditado_retorna_400(self, client, db):
        """Acreditar un cheque ya acreditado → HTTP 400."""
        token = _token(db, "admin@cheques.test")
        cli = _crear_cliente_con_cuenta(db)
        cheque_id = self._crear_cheque(client, db, token, cli)
        banco_id = _banco_cuenta_id(db)

        # Primera acreditación OK
        r1 = client.post(
            f"/cheques/{cheque_id}/acreditar",
            json={"banco_cuenta_id": banco_id},
            headers=_auth(token),
        )
        assert r1.status_code == 200

        # Segunda acreditación → error
        r2 = client.post(
            f"/cheques/{cheque_id}/acreditar",
            json={"banco_cuenta_id": banco_id},
            headers=_auth(token),
        )
        assert r2.status_code == 400


# ── Tests: rechazar cheque ────────────────────────────────────────────────────

class TestRechazarCheque:

    def _ciclo_hasta_acreditado(self, client, db, token):
        cli = _crear_cliente_con_cuenta(db)
        banco_id = _banco_cuenta_id(db)

        r = client.post(
            "/cheques",
            json={"cliente_id": cli.id, "monto": 5000.0, "comision": 0.0,
                  "fecha_deposito": "2026-06-10"},
            headers=_auth(token),
        )
        assert r.status_code == 200
        cheque_id = r.json()["id"]

        r2 = client.post(
            f"/cheques/{cheque_id}/acreditar",
            json={"banco_cuenta_id": banco_id, "fecha_acred": "2026-06-11"},
            headers=_auth(token),
        )
        assert r2.status_code == 200
        return cheque_id, banco_id

    def test_rechazar_cheque_acreditado_happy_path(self, client, db):
        """POST /cheques/{id}/rechazar desde estado acreditado → estado 'rechazado'."""
        token = _token(db, "admin@cheques.test")
        cheque_id, _ = self._ciclo_hasta_acreditado(client, db, token)

        r = client.post(
            f"/cheques/{cheque_id}/rechazar",
            json={"gastos_bancarios": 250.0, "fecha_rechazo": "2026-06-12"},
            headers=_auth(token),
        )
        assert r.status_code == 200, r.text
        assert r.json()["estado"] == "rechazado"

        # Debe haber asientos de rechazo
        rechazo_banco = db.query(Asiento).filter(
            Asiento.modulo == "cheque_rechazo_banco",
            Asiento.referencia_id == cheque_id,
        ).all()
        assert len(rechazo_banco) == 1

    def test_rechazar_cheque_registrado_retorna_400(self, client, db):
        """Rechazar cheque en estado 'registrado' (no acreditado) → HTTP 400."""
        token = _token(db, "admin@cheques.test")
        cli = _crear_cliente_con_cuenta(db)

        r = client.post(
            "/cheques",
            json={"cliente_id": cli.id, "monto": 2000.0, "comision": 0.0},
            headers=_auth(token),
        )
        assert r.status_code == 200
        cheque_id = r.json()["id"]

        r2 = client.post(
            f"/cheques/{cheque_id}/rechazar",
            json={"gastos_bancarios": 0.0},
            headers=_auth(token),
        )
        assert r2.status_code == 400
        assert "acreditado" in r2.json()["detail"].lower()


# ── Tests: eliminar cheque ────────────────────────────────────────────────────

class TestEliminarCheque:

    def test_eliminar_cheque_registrado_crea_reverso(self, client, db):
        """DELETE /cheques/{id} en estado registrado → crea asiento reverso."""
        token = _token(db, "admin@cheques.test")
        cli = _crear_cliente_con_cuenta(db)

        r = client.post(
            "/cheques",
            json={"cliente_id": cli.id, "monto": 1500.0, "comision": 0.0,
                  "fecha_deposito": "2026-06-10"},
            headers=_auth(token),
        )
        assert r.status_code == 200
        cheque_id = r.json()["id"]

        # Verificar que existe el asiento de registro
        assert db.query(Asiento).filter(
            Asiento.modulo == "cheque_registro",
            Asiento.referencia_id == cheque_id,
        ).count() == 1

        r_del = client.delete(f"/cheques/{cheque_id}", headers=_auth(token))
        assert r_del.status_code == 200
        assert r_del.json()["ok"] is True

        # El cheque ya no existe en la DB
        assert db.query(Cheque).filter(Cheque.id == cheque_id).first() is None

        # Debe existir el asiento reverso
        reverso = db.query(Asiento).filter(
            Asiento.modulo == "cheque_registro_reverso",
            Asiento.referencia_id.isnot(None),
        ).first()
        assert reverso is not None, "Debe crearse asiento reverso al eliminar cheque"

    def test_eliminar_cheque_sin_auth_retorna_403(self, client, db):
        r = client.delete("/cheques/1")
        assert r.status_code in (401, 403)

    def test_eliminar_cheque_inexistente_retorna_404(self, client, db):
        token = _token(db, "admin@cheques.test")
        r = client.delete("/cheques/99999", headers=_auth(token))
        assert r.status_code == 404


# ── Tests: listar cheques ─────────────────────────────────────────────────────

class TestListarCheques:

    def test_listar_cheques_retorna_200(self, client, db):
        token = _token(db, "admin@cheques.test")
        r = client.get("/cheques", headers=_auth(token))
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)

    def test_listar_cheques_con_estado_filtro(self, client, db):
        token = _token(db, "admin@cheques.test")
        r = client.get("/cheques?estado=registrado", headers=_auth(token))
        assert r.status_code == 200
        for item in r.json()["items"]:
            assert item["estado"] == "registrado"
