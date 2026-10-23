"""Autenticación (revisión de seguridad oct/2026).

- Cambiar o restablecer la contraseña cierra las sesiones abiertas (JWT con `iat`
  anterior a `users.password_changed_at`).
"""
from datetime import datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.database import Base, get_db
from app.main import app
from app.models.organizacion import Organizacion
from app.models.password_reset import PasswordResetToken
from app.models.user import User
from app.routers import auth as auth_router
from app.services.auth import create_access_token, get_password_hash, verify_password
from app.services.password_reset import _hash_token

settings = get_settings()


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    s = sessionmaker(bind=engine)()
    s.add(Organizacion(id=1, nombre="Org1"))
    s.commit()
    for email, rol, superadmin, activo in (
        ("op1@t.test", "operador", False, True),
        ("admin1@t.test", "admin", False, True),
        ("inactivo@t.test", "operador", False, False),
    ):
        s.add(User(
            email=email, full_name=email, hashed_password=get_password_hash("pw123456"),
            organizacion_id=1, is_active=activo, role=rol, is_superadmin=superadmin,
        ))
    s.commit()
    yield s
    s.close()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    for mod in (auth_router,):
        lim = getattr(mod, "limiter", None)
        if lim is not None:
            lim.reset()
    yield TestClient(app, raise_server_exceptions=True)
    app.dependency_overrides.pop(get_db, None)


def _user(db, email):
    return db.query(User).filter(User.email == email).first()


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _token_viejo(u, segundos_atras=60):
    """Token emitido hace un rato (antes de cualquier cambio de contraseña del test)."""
    ahora = datetime.utcnow()
    return jwt.encode(
        {"sub": u.email, "user_id": u.id, "role": u.role, "jti": "viejo",
         "iat": ahora - timedelta(seconds=segundos_atras), "exp": ahora + timedelta(hours=1)},
        settings.secret_key, algorithm=settings.algorithm,
    )


# ── 1. Cambio de contraseña cierra las sesiones abiertas ─────────────────────

def test_create_access_token_emite_iat(db):
    u = _user(db, "op1@t.test")
    payload = jwt.decode(
        create_access_token({"sub": u.email}), settings.secret_key, algorithms=[settings.algorithm],
    )
    assert "iat" in payload


def test_change_password_cierra_sesiones_y_devuelve_token_nuevo(client, db):
    u = _user(db, "op1@t.test")
    viejo = _token_viejo(u)
    assert client.get("/me", headers=_auth(viejo)).status_code == 200

    r = client.post("/me/change-password", headers=_auth(viejo),
                    json={"current_password": "pw123456", "new_password": "nueva12345"})
    assert r.status_code == 200
    nuevo = r.json()["access_token"]
    assert _user(db, "op1@t.test").password_changed_at is not None

    assert client.get("/me", headers=_auth(viejo)).status_code == 401
    assert client.get("/me", headers=_auth(nuevo)).status_code == 200


def test_reset_password_cierra_sesiones(client, db):
    u = _user(db, "op1@t.test")
    viejo = _token_viejo(u)
    db.add(PasswordResetToken(
        user_id=u.id, token_hash=_hash_token("t" * 43), created_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(hours=1),
    ))
    db.commit()
    r = client.post("/auth/reset-password", json={"token": "t" * 43, "new_password": "nueva12345"})
    assert r.status_code == 200
    assert client.get("/me", headers=_auth(viejo)).status_code == 401
    # Con la contraseña nueva se entra
    r = client.post("/auth/login", json={"email": "op1@t.test", "password": "nueva12345"})
    assert r.status_code == 200
    assert client.get("/me", headers=_auth(r.json()["access_token"])).status_code == 200


def test_token_sin_iat_y_usuario_sin_cambio_siguen_andando(client, db):
    u = _user(db, "op1@t.test")
    ahora = datetime.utcnow()
    sin_iat = jwt.encode(
        {"sub": u.email, "jti": "x", "exp": ahora + timedelta(hours=1)},
        settings.secret_key, algorithm=settings.algorithm,
    )
    # Usuario que nunca cambió la contraseña: el token viejo vale
    assert client.get("/me", headers=_auth(_token_viejo(u))).status_code == 200
    # Token sin iat: vale aunque el usuario haya cambiado la contraseña
    u.password_changed_at = ahora
    db.commit()
    assert client.get("/me", headers=_auth(sin_iat)).status_code == 200


def test_margen_de_un_segundo_para_el_token_del_mismo_segundo(client, db):
    u = _user(db, "op1@t.test")
    u.password_changed_at = datetime.utcnow()
    db.commit()
    # Un token emitido en el mismo instante (iat se redondea al segundo) sigue valiendo
    tok = create_access_token({"sub": u.email})
    assert client.get("/me", headers=_auth(tok)).status_code == 200
    assert verify_password("pw123456", u.hashed_password)
