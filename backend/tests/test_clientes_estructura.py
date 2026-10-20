"""
GET /clientes/estructura devuelve los nombres de los clientes de la organización
del usuario (desde la base), no una lista fija.

Regresión: antes servía una lista hardcodeada de nombres a cualquier usuario
logueado, sin importar su organización. Ahora:
  - sin org_id → clientes de la org del usuario (o la 1 si no tiene),
  - con org_id → solo si `can_switch_org` lo permite; si no, se ignora.
"""
import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.services.auth import get_password_hash, create_access_token
from app.models.organizacion import Organizacion
from app.models.user import User
from app.models.cliente import Cliente


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

    session.add(Organizacion(id=1, nombre="Principal"))
    session.add(Organizacion(id=2, nombre="Secundaria"))
    session.commit()

    session.add_all([
        Cliente(nombre="Distribuidora Andina", organizacion_id=1),
        Cliente(nombre="Cliente Norte", organizacion_id=1),
        Cliente(nombre="Cliente Sur", organizacion_id=2),
    ])

    def _user(email, org_id, superadmin=False, allowed=None):
        return User(
            email=email, full_name=email.split("@")[0],
            hashed_password=get_password_hash("pw123"),
            organizacion_id=org_id, is_active=True, role="admin",
            is_superadmin=superadmin, allowed_org_ids=allowed or [],
        )

    session.add_all([
        _user("super@org.test", 1, superadmin=True),
        _user("operador1@org.test", 1),
        _user("operador2@org.test", 2),
        _user("contador@org.test", 1, allowed=[2]),
    ])
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


def _headers(db, email):
    user = db.query(User).filter(User.email == email).first()
    token = create_access_token({"sub": user.email, "user_id": user.id, "role": user.role})
    return {"Authorization": f"Bearer {token}"}


def _estructura(client, db, email, org_id=None):
    url = "/clientes/estructura" + (f"?org_id={org_id}" if org_id is not None else "")
    r = client.get(url, headers=_headers(db, email))
    assert r.status_code == 200, r.text
    return r.json()


def test_devuelve_clientes_de_la_org_del_usuario_ordenados(client, db):
    assert _estructura(client, db, "operador1@org.test") == {
        "clientes": ["Cliente Norte", "Distribuidora Andina"],
    }
    assert _estructura(client, db, "operador2@org.test") == {"clientes": ["Cliente Sur"]}


def test_org_id_ajeno_se_ignora_sin_permiso(client, db):
    """Un usuario sin acceso a la org 2 no ve sus clientes aunque mande org_id=2."""
    data = _estructura(client, db, "operador1@org.test", org_id=2)
    assert data == {"clientes": ["Cliente Norte", "Distribuidora Andina"]}


def test_org_id_respetado_si_puede_cambiar_de_org(client, db):
    assert _estructura(client, db, "contador@org.test", org_id=2) == {"clientes": ["Cliente Sur"]}
    assert _estructura(client, db, "super@org.test", org_id=2) == {"clientes": ["Cliente Sur"]}


def test_superadmin_sin_org_id_ve_su_propia_org(client, db):
    assert _estructura(client, db, "super@org.test") == {
        "clientes": ["Cliente Norte", "Distribuidora Andina"],
    }


def test_requiere_autenticacion(client):
    r = client.get("/clientes/estructura")
    assert r.status_code in (401, 403)
