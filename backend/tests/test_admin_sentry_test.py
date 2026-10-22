"""POST /admin/sentry-test: solo superadmin; lanza el error de prueba y lo audita."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.auditoria import AuditoriaLog
from app.models.organizacion import Organizacion
from app.models.user import User
from app.routers.admin import SentryTestError
from app.services.auth import create_access_token, get_password_hash


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    session.add(Organizacion(id=1, nombre="Org"))
    session.commit()
    for email, superadmin in (("super@t.test", True), ("admin@t.test", False)):
        session.add(User(
            email=email, full_name=email, hashed_password=get_password_hash("pw123"),
            organizacion_id=1, is_active=True, role="admin", is_superadmin=superadmin,
        ))
    session.commit()
    yield session
    session.close()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app, raise_server_exceptions=True)
    app.dependency_overrides.pop(get_db, None)


def _auth(db, email):
    u = db.query(User).filter(User.email == email).first()
    tok = create_access_token({"sub": u.email, "user_id": u.id, "role": u.role})
    return {"Authorization": f"Bearer {tok}"}


def test_superadmin_dispara_el_error_y_queda_auditado(client, db):
    with pytest.raises(SentryTestError):
        client.post("/admin/sentry-test", headers=_auth(db, "super@t.test"))
    assert db.query(AuditoriaLog).filter(AuditoriaLog.accion == "SENTRY_TEST").count() == 1


def test_admin_comun_no_puede(client, db):
    r = client.post("/admin/sentry-test", headers=_auth(db, "admin@t.test"))
    assert r.status_code == 403


def test_sin_login_no_puede(client):
    r = client.post("/admin/sentry-test")
    assert r.status_code in (401, 403)
