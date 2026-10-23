"""Compatibilidad de JWT al pasar de python-jose a PyJWT.

Los tokens de abajo se generaron con python-jose 3.5.0 (la librería anterior), HS256, con una clave
de prueba que no es la de producción. Si el código nuevo los acepta igual que antes, las sesiones
abiertas y los links compartidos ya emitidos siguen funcionando después del deploy.
"""
import base64
import json
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.database import Base, get_db
from app.main import app
from app.models.organizacion import Organizacion
from app.models.revoked_token import RevokedToken
from app.services.auth import create_access_token, verify_token

# Clave SOLO de test (no es secreta ni se usa en ningún entorno real).
CLAVE_TEST = "clave-solo-para-test-compat-jose-no-es-secreta"

# Emitidos con python-jose: jwt.encode(payload, CLAVE_TEST, algorithm="HS256")
# Access token: sub/user_id/role/exp(1/1/2100)/jti, como los arma create_access_token.
JOSE_ACCESS = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJzdWIiOiJhbmFAZXhhbXBsZS5jb20iLCJ1c2VyX2lkIjo3LCJyb2xlIjoiYWRtaW4iLCJleHAiOjQxMDI0NDQ4MDAs"
    "Imp0aSI6IjAxMjM0NTY3ODlhYmNkZWYwMTIzNDU2Nzg5YWJjZGVmIn0."
    "QOQ8kQqX2BWSUzRklm3fCgRuqn2I9ok1CvrBd0CSgiw"
)
# Link compartido de estado de cuenta (clientes_dir.generar_share_link), exp 1/1/2100.
JOSE_SHARE = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJ0eXBlIjoic2hhcmVfY2xpZW50ZSIsImNsaWVudF9pZCI6NSwib3JnX2lkIjoyLCJleHAiOjQxMDI0NDQ4MDB9."
    "iCQ6WZZkOqjQzax9zEYw1RFzIu1xB9uq0Ms0T4iHEqQ"
)
# Access token ya vencido (exp 1/1/2020).
JOSE_VENCIDO = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJzdWIiOiJhbmFAZXhhbXBsZS5jb20iLCJ1c2VyX2lkIjo3LCJyb2xlIjoiYWRtaW4iLCJleHAiOjE1Nzc4MzY4MDAs"
    "Imp0aSI6ImZlZGNiYTk4NzY1NDMyMTBmZWRjYmE5ODc2NTQzMjEwIn0."
    "C6IexN19S14T-M-ihrfdq0oOfUk5R13unoCrRhcC60A"
)


@pytest.fixture
def clave_test(monkeypatch):
    # get_settings() está cacheado: todos los módulos comparten este mismo objeto.
    monkeypatch.setattr(get_settings(), "secret_key", CLAVE_TEST)


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    session.add(Organizacion(id=2, nombre="Org"))
    session.commit()
    app.dependency_overrides[get_db] = lambda: session
    yield TestClient(app), session
    app.dependency_overrides.pop(get_db, None)
    session.close()


def test_token_de_jose_se_sigue_aceptando(clave_test):
    payload = verify_token(JOSE_ACCESS)
    assert payload is not None
    assert payload["sub"] == "ana@example.com"
    assert payload["user_id"] == 7
    assert payload["role"] == "admin"
    assert payload["jti"] == "0123456789abcdef0123456789abcdef"
    assert payload["exp"] == 4102444800


def test_token_de_jose_vencido_se_rechaza(clave_test):
    assert verify_token(JOSE_VENCIDO) is None


def test_token_con_otra_clave_se_rechaza():
    # Sin el monkeypatch, la clave activa es otra: la firma no coincide.
    assert verify_token(JOSE_ACCESS) is None


def test_firma_alterada_se_rechaza(clave_test):
    cabeza, cuerpo, firma = JOSE_ACCESS.split(".")
    otra = ("A" if firma[0] != "A" else "B") + firma[1:]
    assert verify_token(f"{cabeza}.{cuerpo}.{otra}") is None


def test_alg_none_se_rechaza(clave_test):
    def b64(d):
        return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
    token = f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64({'sub': 'ana@example.com', 'exp': 4102444800})}."
    assert verify_token(token) is None


def test_token_nuevo_mismo_formato(clave_test):
    token = create_access_token({"sub": "ana@example.com", "user_id": 7, "role": "admin"})
    cabeza = json.loads(base64.urlsafe_b64decode(token.split(".")[0] + "=="))
    assert cabeza == {"alg": "HS256", "typ": "JWT"}
    payload = verify_token(token)
    assert payload["sub"] == "ana@example.com"
    assert isinstance(payload["exp"], int) and payload["exp"] > datetime.utcnow().timestamp()
    assert len(payload["jti"]) == 32


def test_link_compartido_de_jose_sigue_valido(clave_test, client):
    c, _ = client
    # El token decodifica bien: llega a buscar el cliente (404), no es rechazado como inválido (401).
    r = c.get(f"/public/cliente/{JOSE_SHARE}")
    assert r.status_code == 404
    r = c.get(f"/public/cliente/{JOSE_SHARE[:-2]}xx")
    assert r.status_code == 401


def test_logout_revoca_token_de_jose_aunque_este_vencido(clave_test, client):
    c, session = client
    r = c.post("/auth/logout", headers={"Authorization": f"Bearer {JOSE_VENCIDO}"})
    assert r.status_code == 200
    rev = session.query(RevokedToken).filter_by(jti="fedcba9876543210fedcba9876543210").first()
    assert rev is not None
    assert rev.user_id == 7
    assert rev.expires_at == datetime(2020, 1, 1)
