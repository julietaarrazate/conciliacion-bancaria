"""Límites de protección (revisión de seguridad oct/2026).

- IP real detrás del proxy de Render: los contadores de slowapi son por cliente, no
  uno solo para todos, y un X-Forwarded-For inventado no permite esquivarlos.
- Cupo diario de IA por organización en la base (`uso_ia_diario`): corta en el tope,
  no lo gasta otra organización y no suma si el pedido no entra.
- Endpoints de IA: chat con cupo por org, tamaño máximo de audio, carga masiva de
  cheques por foto (antes fallaba siempre por un import roto) con cupo por foto.
"""
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

from app.database import Base, get_db
from app.main import app
from app.models.organizacion import Organizacion
from app.models.user import User
from app.models.uso_ia import UsoIaDiario
from app.routers import agente as agente_router
from app.routers import auth as auth_router
from app.routers import cheques_crud as cheques_crud_router
from app.services.auth import create_access_token, get_password_hash
from app.services.limites import consumir_cupo_ia, ip_cliente, uso_ia


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    s = sessionmaker(bind=engine)()
    s.add_all([Organizacion(id=1, nombre="Org1"), Organizacion(id=2, nombre="Org2")])
    s.commit()
    for email, org, rol in (
        ("op1@t.test", 1, "operador"), ("op2@t.test", 2, "operador"), ("rev1@t.test", 1, "revisor"),
    ):
        s.add(User(
            email=email, full_name=email, hashed_password=get_password_hash("pw123456"),
            organizacion_id=org, is_active=True, role=rol, is_superadmin=False,
        ))
    s.commit()
    yield s
    s.close()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    for mod in (auth_router, agente_router, cheques_crud_router):
        lim = getattr(mod, "limiter", None)
        if lim is not None:
            lim.reset()
    yield TestClient(app, raise_server_exceptions=True)
    app.dependency_overrides.pop(get_db, None)


def _auth(db, email):
    u = db.query(User).filter(User.email == email).first()
    tok = create_access_token({"sub": u.email, "user_id": u.id, "role": u.role})
    return {"Authorization": f"Bearer {tok}"}


def _request(xff=None, host="10.0.0.5"):
    headers = [(b"x-forwarded-for", xff.encode())] if xff else []
    return Request({"type": "http", "headers": headers, "client": (host, 1234)})


# ── IP real ──────────────────────────────────────────────────────────────────

def test_ip_cliente_toma_la_ip_que_agrega_el_proxy():
    assert ip_cliente(_request("181.1.2.3")) == "181.1.2.3"


def test_ip_cliente_ignora_lo_que_inventa_el_cliente_a_la_izquierda():
    # El cliente manda "8.8.8.8"; el proxy agrega la IP real al final.
    assert ip_cliente(_request("8.8.8.8, 181.1.2.3")) == "181.1.2.3"


def test_ip_cliente_saltea_ips_privadas_de_la_red_interna():
    assert ip_cliente(_request("181.1.2.3, 10.1.2.3")) == "181.1.2.3"


def test_ip_cliente_sin_header_usa_la_conexion():
    assert ip_cliente(_request()) == "10.0.0.5"
    assert ip_cliente(_request("basura, no-es-ip")) == "10.0.0.5"


def test_login_cuenta_intentos_por_ip_y_no_para_todos(client):
    body = {"email": "op1@t.test", "password": "incorrecta"}
    for _ in range(10):
        r = client.post("/auth/login", json=body, headers={"X-Forwarded-For": "181.1.1.1"})
        assert r.status_code == 401
    r = client.post("/auth/login", json=body, headers={"X-Forwarded-For": "181.1.1.1"})
    assert r.status_code == 429
    # Otra persona (otra IP) puede seguir intentando: antes quedaba bloqueada también.
    r = client.post("/auth/login", json=body, headers={"X-Forwarded-For": "181.2.2.2"})
    assert r.status_code == 401
    # Inventar un X-Forwarded-For a la izquierda no resetea el contador.
    r = client.post("/auth/login", json=body, headers={"X-Forwarded-For": "9.9.9.9, 181.1.1.1"})
    assert r.status_code == 429


# ── Cupo diario de IA por organización ───────────────────────────────────────

def test_cupo_corta_en_el_tope_y_es_por_organizacion(db, monkeypatch):
    monkeypatch.setenv("IA_TOPE_DIARIO_CHAT", "3")
    for esperado in (1, 2, 3):
        assert consumir_cupo_ia(db, 1, "chat") == esperado
    with pytest.raises(HTTPException) as e:
        consumir_cupo_ia(db, 1, "chat")
    assert e.value.status_code == 429
    # La org 2 tiene su propio cupo.
    assert consumir_cupo_ia(db, 2, "chat") == 1
    assert uso_ia(db, 1, "chat")["used"] == 3
    assert uso_ia(db, 1, "chat")["remaining"] == 0


def test_cupo_no_suma_si_el_pedido_no_entra_entero(db, monkeypatch):
    monkeypatch.setenv("IA_TOPE_DIARIO_OCR", "5")
    assert consumir_cupo_ia(db, 1, "ocr", cantidad=4) == 4
    with pytest.raises(HTTPException):
        consumir_cupo_ia(db, 1, "ocr", cantidad=2)
    assert db.query(UsoIaDiario).filter_by(organizacion_id=1, tipo="ocr").one().cantidad == 4
    with pytest.raises(HTTPException):
        consumir_cupo_ia(db, 2, "ocr", cantidad=6)  # más que el tope desde cero
    assert db.query(UsoIaDiario).filter_by(organizacion_id=2).count() == 0


# ── Endpoints de IA ──────────────────────────────────────────────────────────

def test_chat_corta_por_organizacion(client, db, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    monkeypatch.setenv("IA_TOPE_DIARIO_CHAT", "2")
    monkeypatch.setattr(agente_router, "_run_chat_message", lambda *a, **k: "ok")
    for _ in range(2):
        r = client.post("/agente/chat", json={"mensaje": "hola"}, headers=_auth(db, "op1@t.test"))
        assert r.status_code == 200
    r = client.post("/agente/chat", json={"mensaje": "hola"}, headers=_auth(db, "op1@t.test"))
    assert r.status_code == 429
    r = client.post("/agente/chat", json={"mensaje": "hola"}, headers=_auth(db, "op2@t.test"))
    assert r.status_code == 200


def test_chat_rechaza_mensajes_enormes_sin_gastar_cupo(client, db, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    r = client.post("/agente/chat", json={"mensaje": "x" * 5000}, headers=_auth(db, "op1@t.test"))
    assert r.status_code == 413
    assert uso_ia(db, 1, "chat")["used"] == 0


def test_transcribir_rechaza_audios_de_mas_de_10mb(client, db, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    audio = b"0" * (10 * 1024 * 1024 + 1)
    r = client.post(
        "/agente/transcribir", files={"audio": ("a.webm", audio, "audio/webm")},
        headers=_auth(db, "op1@t.test"),
    )
    assert r.status_code == 413
    assert uso_ia(db, 1, "audio")["used"] == 0


def test_bulk_ocr_descuenta_una_lectura_por_foto(client, db, monkeypatch):
    """Antes el endpoint fallaba siempre (import de `routers.agente` inexistente)."""
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    monkeypatch.setenv("IA_TOPE_DIARIO_OCR", "1")
    fotos = [("fotos", (f"f{i}.jpg", b"jpg", "image/jpeg")) for i in range(2)]
    r = client.post("/cheques/bulk-ocr", files=fotos, headers=_auth(db, "op1@t.test"))
    assert r.status_code == 429
    assert uso_ia(db, 1, "ocr")["used"] == 0


def test_bulk_ocr_requiere_permiso_de_carga(client, db, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    fotos = [("fotos", ("f.jpg", b"jpg", "image/jpeg"))]
    r = client.post("/cheques/bulk-ocr", files=fotos, headers=_auth(db, "rev1@t.test"))
    assert r.status_code == 403


def test_uso_de_ia_se_muestra_por_organizacion(client, db):
    consumir_cupo_ia(db, 2, "chat")
    r = client.get("/agente/ocr-usage", headers=_auth(db, "op1@t.test"))
    assert r.status_code == 200
    assert r.json()["chat"]["used"] == 0
    r = client.get("/agente/ocr-usage", headers=_auth(db, "op2@t.test"))
    assert r.json()["chat"]["used"] == 1
