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


# ── 2. PATCH /me: cambiar el email pide la contraseña ────────────────────────

def test_patch_me_email_sin_password_se_rechaza(client, db):
    tok = create_access_token({"sub": "op1@t.test"})
    r = client.patch("/me", headers=_auth(tok), json={"email": "otro@t.test"})
    assert r.status_code == 400
    r = client.patch("/me", headers=_auth(tok),
                     json={"email": "otro@t.test", "current_password": "mala"})
    assert r.status_code == 400
    assert _user(db, "op1@t.test") is not None
    assert _user(db, "otro@t.test") is None


def test_patch_me_email_con_password_normaliza(client, db):
    tok = create_access_token({"sub": "op1@t.test"})
    r = client.patch("/me", headers=_auth(tok),
                     json={"email": "  Nuevo@T.Test ", "current_password": "pw123456"})
    assert r.status_code == 200
    assert r.json()["email"] == "nuevo@t.test"


def test_patch_me_email_invalido_o_en_uso(client, db):
    tok = create_access_token({"sub": "op1@t.test"})
    r = client.patch("/me", headers=_auth(tok),
                     json={"email": "no-es-un-mail", "current_password": "pw123456"})
    assert r.status_code == 400
    r = client.patch("/me", headers=_auth(tok),
                     json={"email": "ADMIN1@t.test", "current_password": "pw123456"})
    assert r.status_code == 400
    assert "en uso" in r.json()["detail"]


def test_patch_me_solo_nombre_o_mismo_email_no_pide_password(client, db):
    tok = create_access_token({"sub": "op1@t.test"})
    r = client.patch("/me", headers=_auth(tok),
                     json={"full_name": "Nombre Nuevo", "email": "OP1@t.test"})
    assert r.status_code == 200
    assert r.json()["full_name"] == "Nombre Nuevo"
    assert r.json()["email"] == "op1@t.test"


# ── 3. Login con Google ──────────────────────────────────────────────────────

class _Resp:
    def __init__(self, status_code, data):
        self.status_code = status_code
        self._data = data
        self.text = str(data)

    def json(self):
        return self._data


@pytest.fixture
def google(monkeypatch):
    """Simula Google: el test elige qué devuelve tokeninfo."""
    from app.routers import google_auth
    monkeypatch.setattr(google_auth.settings, "google_client_id", "cid")
    monkeypatch.setattr(google_auth.settings, "google_client_secret", "secret")
    google_auth.limiter.reset()
    info = {"aud": "cid", "email": "op1@t.test", "email_verified": "true"}
    monkeypatch.setattr(google_auth.http_requests, "post",
                        lambda *a, **k: _Resp(200, {"id_token": "idt"}))
    monkeypatch.setattr(google_auth.http_requests, "get", lambda *a, **k: _Resp(200, info))
    return info


def _google_login(client):
    return client.post("/auth/google", json={"code": "c", "redirect_uri": "https://x/login"})


@pytest.mark.parametrize("valor,ok", [
    ("true", True), (True, True), ("TRUE", True),
    ("false", False), (False, False), ("", False), (None, False), ("0", False),
])
def test_google_email_verified_se_compara_bien(client, google, valor, ok):
    google["email_verified"] = valor
    r = _google_login(client)
    assert r.status_code == (200 if ok else 401)


def test_google_tiene_rate_limit(client, google):
    codigos = [_google_login(client).status_code for _ in range(12)]
    assert codigos[:10] == [200] * 10
    assert 429 in codigos[10:]


def test_google_admin_pasa_por_2fa(client, google, monkeypatch):
    enviados = []
    monkeypatch.setattr(auth_router.settings, "resend_api_key", "re_test")
    monkeypatch.setattr("app.services.email_sender.send_email", lambda **k: enviados.append(k))
    google["email"] = "admin1@t.test"
    r = _google_login(client)
    assert r.status_code == 202
    assert r.json()["requires_2fa"] is True
    assert "access_token" not in r.json()
    assert len(enviados) == 1


# ── 4. 2FA: cupo de códigos, intentos y falla cerrada ────────────────────────

@pytest.fixture
def twofa(monkeypatch):
    """2FA activo; guarda los códigos 'enviados' por mail."""
    import re
    enviados = []
    monkeypatch.setattr(auth_router.settings, "resend_api_key", "re_test")
    monkeypatch.setattr(auth_router.settings, "debug", False)

    def _send(**k):
        enviados.append(re.search(r">(\d{6})<", k["html"]).group(1))
    monkeypatch.setattr("app.services.email_sender.send_email", _send)
    return enviados


def _login_admin(client):
    return client.post("/auth/login", json={"email": "admin1@t.test", "password": "pw123456"})


def test_2fa_flujo_ok(client, twofa):
    r = _login_admin(client)
    assert r.status_code == 202
    r = client.post("/auth/verify-2fa", json={"email": "admin1@t.test", "code": twofa[-1]})
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_2fa_cupo_de_codigos_por_hora(client, twofa):
    for _ in range(auth_router.TWOFA_MAX_CODES_PER_HOUR):
        assert _login_admin(client).status_code == 202
    r = _login_admin(client)
    assert r.status_code == 429
    assert len(twofa) == auth_router.TWOFA_MAX_CODES_PER_HOUR


def test_2fa_codigo_nuevo_invalida_el_anterior(client, twofa):
    _login_admin(client)
    primero = twofa[-1]
    _login_admin(client)
    if primero != twofa[-1]:
        r = client.post("/auth/verify-2fa", json={"email": "admin1@t.test", "code": primero})
        assert r.status_code == 401


def test_2fa_intentos_fallidos_invalidan_el_codigo(client, twofa):
    _login_admin(client)
    bueno = twofa[-1]
    malo = "000000" if bueno != "000000" else "111111"
    for _ in range(auth_router.TWOFA_MAX_ATTEMPTS):
        auth_router.limiter.reset()
        r = client.post("/auth/verify-2fa", json={"email": "admin1@t.test", "code": malo})
        assert r.status_code == 401
    auth_router.limiter.reset()
    r = client.post("/auth/verify-2fa", json={"email": "admin1@t.test", "code": bueno})
    assert r.status_code == 401


def test_2fa_falla_cerrado_si_no_se_envia_el_mail(client, twofa, monkeypatch):
    def _falla(**k):
        raise RuntimeError("Resend caído")
    monkeypatch.setattr("app.services.email_sender.send_email", _falla)
    r = _login_admin(client)
    assert r.status_code == 503
    assert "access_token" not in r.json()


def test_2fa_falla_cerrado_si_no_se_crea_el_codigo(client, twofa, monkeypatch):
    import app.models.twofa_code as m

    class _Rota:
        user_id = m.TwofaCode.user_id
        created_at = m.TwofaCode.created_at
        used = m.TwofaCode.used

        def __init__(self, *a, **k):
            raise RuntimeError("DB rota")
    monkeypatch.setattr(m, "TwofaCode", _Rota)
    r = _login_admin(client)
    assert r.status_code == 503
    assert "access_token" not in r.json()


# ── 5. Usuario inactivo: mismo 401 que contraseña mala ───────────────────────

def test_login_inactivo_mismo_401_que_password_mala(client):
    r_inactivo = client.post("/auth/login", json={"email": "inactivo@t.test", "password": "pw123456"})
    r_mala = client.post("/auth/login", json={"email": "op1@t.test", "password": "mala1234"})
    r_inexistente = client.post("/auth/login", json={"email": "nadie@t.test", "password": "pw123456"})
    assert r_inactivo.status_code == r_mala.status_code == r_inexistente.status_code == 401
    assert r_inactivo.json() == r_mala.json() == r_inexistente.json()


def test_login_inactivo_con_password_mala_tambien_401(client):
    r = client.post("/auth/login", json={"email": "inactivo@t.test", "password": "mala1234"})
    assert r.status_code == 401


# ── 6. Mail de reset: el nombre va escapado ──────────────────────────────────

def test_mail_reset_escapa_el_nombre():
    from app.services.password_reset import _html_email
    cuerpo = _html_email('<b>Juan</b> Pérez', "https://app/r?token=abc", 60)
    assert "<b>" not in cuerpo
    assert "&lt;b&gt;" in cuerpo
    # Nombre vacío o solo espacios: saludo genérico (antes tiraba IndexError)
    assert "Hola Hola" in _html_email("   ", "https://app/r", 60)
