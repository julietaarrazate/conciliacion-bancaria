"""Tests del módulo ARCA (ex-AFIP) — facturación electrónica, integración propia WSFEv1/WSAA.

Cubre:
  - arca_crypto: roundtrip cifrar/descifrar, error explícito sin ARCA_ENCRYPTION_KEY.
  - config: no se puede activar sin certificado cargado; permisos admin_accounting.
  - certificado: subir/borrar, nunca se devuelve en las respuestas.
  - comprobantes: crear requiere módulo activo; permisos manage_finance/view_accounting.
  - emitir: WSAA/WSFEv1 mockeados — éxito genera asiento contable balanceado; rechazo/error
    de ARCA no rompe y deja el comprobante en el estado correspondiente.
  - inmutabilidad: un comprobante emitido no se puede re-emitir.
  - aislamiento multi-org.
"""
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
from app.models.organizacion import Organizacion
from app.models.user import User
from app.models.cliente import Cliente
from app.models.contabilidad import PlanCuenta, AsientoDetalle
from app.models.arca import ArcaConfig, ComprobanteArca
from app.services import arca_crypto
from app.services.arca_wsfe import ArcaWsfeRechazo, ArcaWsfeError
from app.routers import arca as arca_router

TEST_KEY = "3pjU0i9o7Bw3o6F0bU9nQ8b1qk6m1n0Q3z2x1y4w5z0="  # 32-byte base64, formato Fernet


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

    org = Organizacion(id=1, nombre="OrgArca")
    org2 = Organizacion(id=2, nombre="OrgArca2")
    session.add_all([org, org2])
    session.commit()

    seed_contabilidad_org(session, 1)
    seed_contabilidad_org(session, 2)

    cliente = Cliente(id=1, nombre="Cliente ARCA", organizacion_id=1)
    session.add(cliente)
    session.commit()

    admin = User(
        email="admin@arca.test", full_name="Admin Arca",
        hashed_password=get_password_hash("pw123"),
        organizacion_id=1, is_active=True, role="admin", is_superadmin=False,
    )
    revisor = User(
        email="rev@arca.test", full_name="Revisor Arca",
        hashed_password=get_password_hash("pw123"),
        organizacion_id=1, is_active=True, role="revisor", is_superadmin=False,
    )
    operador = User(
        email="op@arca.test", full_name="Operador Arca",
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


@pytest.fixture(autouse=True)
def _arca_key(monkeypatch):
    """Fuerza una ARCA_ENCRYPTION_KEY válida durante los tests, sin tocar el entorno real."""
    from app.config import Settings

    fake_settings = Settings(arca_encryption_key=TEST_KEY)
    monkeypatch.setattr(arca_crypto, "get_settings", lambda: fake_settings)


def _token(db, email):
    user = db.query(User).filter(User.email == email).first()
    return create_access_token({"sub": user.email, "user_id": user.id, "role": user.role})


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _cuenta(db, codigo, org=1):
    return db.query(PlanCuenta).filter(
        PlanCuenta.codigo == codigo, PlanCuenta.organizacion_id == org
    ).first()


# ── arca_crypto ───────────────────────────────────────────────────

def test_crypto_roundtrip():
    cifrado = arca_crypto.encriptar("-----BEGIN CERTIFICATE-----\nabc\n-----END CERTIFICATE-----")
    assert cifrado and cifrado != "abc"
    claro = arca_crypto.desencriptar(cifrado)
    assert claro == "-----BEGIN CERTIFICATE-----\nabc\n-----END CERTIFICATE-----"


def test_crypto_sin_key_falla(monkeypatch):
    from app.config import Settings
    monkeypatch.setattr(arca_crypto, "get_settings", lambda: Settings(arca_encryption_key=""))
    with pytest.raises(arca_crypto.ArcaCryptoError):
        arca_crypto.encriptar("algo")


# ── config ────────────────────────────────────────────────────────

def test_config_default_apagada(client, db):
    tok = _token(db, "admin@arca.test")
    r = client.get("/arca/config", headers=_auth(tok))
    assert r.status_code == 200
    assert r.json() == {
        "activo": False, "cuit": None, "ambiente": "homologacion",
        "punto_venta": 1, "tiene_certificado": False,
    }


def test_config_sin_permiso_403(client, db):
    tok = _token(db, "rev@arca.test")
    r = client.get("/arca/config", headers=_auth(tok))
    assert r.status_code == 403


def test_no_se_puede_activar_sin_certificado(client, db):
    tok = _token(db, "admin@arca.test")
    r = client.put("/arca/config", json={
        "activo": True, "cuit": "20111111112", "ambiente": "homologacion", "punto_venta": 1,
    }, headers=_auth(tok))
    assert r.status_code == 422


def test_certificado_nunca_se_devuelve(client, db):
    tok = _token(db, "admin@arca.test")
    r = client.post("/arca/certificado", json={
        "certificado_pem": "CERT-PEM-DATA", "clave_privada_pem": "KEY-PEM-DATA",
    }, headers=_auth(tok))
    assert r.status_code == 200
    body = r.json()
    assert body["tiene_certificado"] is True
    assert "certificado_pem" not in body
    assert "clave_privada_pem" not in body
    assert "certificado_enc" not in body

    cfg = db.query(ArcaConfig).filter(ArcaConfig.organizacion_id == 1).first()
    assert cfg.certificado_enc != "CERT-PEM-DATA"
    assert arca_crypto.desencriptar(cfg.certificado_enc) == "CERT-PEM-DATA"

    r2 = client.put("/arca/config", json={
        "activo": True, "cuit": "20111111112", "ambiente": "homologacion", "punto_venta": 1,
    }, headers=_auth(tok))
    assert r2.status_code == 200
    assert r2.json()["activo"] is True


def test_borrar_certificado_desactiva(client, db):
    tok = _token(db, "admin@arca.test")
    client.post("/arca/certificado", json={
        "certificado_pem": "CERT", "clave_privada_pem": "KEY",
    }, headers=_auth(tok))
    client.put("/arca/config", json={
        "activo": True, "cuit": "20111111112", "ambiente": "homologacion", "punto_venta": 1,
    }, headers=_auth(tok))

    r = client.delete("/arca/certificado", headers=_auth(tok))
    assert r.status_code == 200
    body = r.json()
    assert body["tiene_certificado"] is False
    assert body["activo"] is False


# ── comprobantes ──────────────────────────────────────────────────

def _activar(client, tok):
    client.post("/arca/certificado", json={
        "certificado_pem": "CERT", "clave_privada_pem": "KEY",
    }, headers=_auth(tok))
    client.put("/arca/config", json={
        "activo": True, "cuit": "20111111112", "ambiente": "homologacion", "punto_venta": 1,
    }, headers=_auth(tok))


def test_crear_comprobante_requiere_modulo_activo(client, db):
    tok = _token(db, "admin@arca.test")
    r = client.post("/arca/comprobantes", json={
        "tipo_comprobante": 11, "importe_total": 1000.0,
    }, headers=_auth(tok))
    assert r.status_code == 422


def test_crear_comprobante_ok(client, db):
    tok_admin = _token(db, "admin@arca.test")
    _activar(client, tok_admin)
    tok_op = _token(db, "op@arca.test")
    r = client.post("/arca/comprobantes", json={
        "cliente_id": 1, "tipo_comprobante": 11, "concepto": 2,
        "importe_neto": 826.45, "importe_iva": 173.55, "importe_total": 1000.0,
        "fecha_serv_desde": "2026-06-01", "fecha_serv_hasta": "2026-06-30",
        "fecha_vto_pago": "2026-07-10",
    }, headers=_auth(tok_op))
    assert r.status_code == 200
    body = r.json()
    assert body["estado"] == "borrador"
    assert body["cae"] is None
    assert body["fecha_serv_desde"] == "2026-06-01"


def test_crear_comprobante_servicios_sin_fechas_falla(client, db):
    tok_admin = _token(db, "admin@arca.test")
    _activar(client, tok_admin)
    r = client.post("/arca/comprobantes", json={
        "tipo_comprobante": 11, "concepto": 2, "importe_total": 1000.0,
    }, headers=_auth(tok_admin))
    assert r.status_code == 422


def test_crear_comprobante_sin_permiso_403(client, db):
    tok_admin = _token(db, "admin@arca.test")
    _activar(client, tok_admin)
    tok_rev = _token(db, "rev@arca.test")
    r = client.post("/arca/comprobantes", json={
        "tipo_comprobante": 11, "importe_total": 1000.0,
    }, headers=_auth(tok_rev))
    assert r.status_code == 403


def test_listar_comprobantes_view_accounting(client, db):
    tok_admin = _token(db, "admin@arca.test")
    _activar(client, tok_admin)
    client.post("/arca/comprobantes", json={
        "tipo_comprobante": 11, "importe_total": 500.0,
    }, headers=_auth(tok_admin))

    tok_rev = _token(db, "rev@arca.test")
    r = client.get("/arca/comprobantes", headers=_auth(tok_rev))
    assert r.status_code == 200
    assert r.json()["total"] == 1


# ── emitir (WSAA/WSFEv1 mockeados) ───────────────────────────────

def test_emitir_exito_genera_asiento_balanceado(client, db, monkeypatch):
    tok_admin = _token(db, "admin@arca.test")
    _activar(client, tok_admin)

    monkeypatch.setattr(arca_router, "obtener_token_sign", lambda db, cfg: ("TOKEN", "SIGN"))
    monkeypatch.setattr(arca_router, "consultar_ultimo_autorizado", lambda *a, **k: 41)
    monkeypatch.setattr(arca_router, "solicitar_cae", lambda *a, **k: {
        "cae": "75312345678901", "cae_vencimiento": "20260710", "observaciones": [],
    })

    r = client.post("/arca/comprobantes", json={
        "cliente_id": 1, "tipo_comprobante": 11, "concepto": 2,
        "importe_neto": 826.45, "importe_iva": 173.55, "importe_total": 1000.0,
        "fecha_serv_desde": "2026-06-01", "fecha_serv_hasta": "2026-06-30",
        "fecha_vto_pago": "2026-07-10",
    }, headers=_auth(tok_admin))
    comprobante_id = r.json()["id"]

    r2 = client.post(f"/arca/comprobantes/{comprobante_id}/emitir", headers=_auth(tok_admin))
    assert r2.status_code == 200
    body = r2.json()
    assert body["estado"] == "emitido"
    assert body["cae"] == "75312345678901"
    assert body["numero"] == 42

    c = db.query(ComprobanteArca).filter(ComprobanteArca.id == comprobante_id).first()
    assert c.asiento_id is not None
    detalles = db.query(AsientoDetalle).filter(AsientoDetalle.asiento_id == c.asiento_id).all()
    total_debe = sum(Decimal(str(d.debe)) for d in detalles)
    total_haber = sum(Decimal(str(d.haber)) for d in detalles)
    assert total_debe == total_haber == Decimal("1000.00")


def test_emitir_dos_veces_falla(client, db, monkeypatch):
    tok_admin = _token(db, "admin@arca.test")
    _activar(client, tok_admin)
    monkeypatch.setattr(arca_router, "obtener_token_sign", lambda db, cfg: ("TOKEN", "SIGN"))
    monkeypatch.setattr(arca_router, "consultar_ultimo_autorizado", lambda *a, **k: 0)
    monkeypatch.setattr(arca_router, "solicitar_cae", lambda *a, **k: {
        "cae": "75312345678901", "cae_vencimiento": "20260710", "observaciones": [],
    })

    r = client.post("/arca/comprobantes", json={
        "tipo_comprobante": 11, "importe_total": 500.0,
    }, headers=_auth(tok_admin))
    cid = r.json()["id"]
    client.post(f"/arca/comprobantes/{cid}/emitir", headers=_auth(tok_admin))

    r2 = client.post(f"/arca/comprobantes/{cid}/emitir", headers=_auth(tok_admin))
    assert r2.status_code == 409


def test_emitir_rechazo_arca(client, db, monkeypatch):
    tok_admin = _token(db, "admin@arca.test")
    _activar(client, tok_admin)
    monkeypatch.setattr(arca_router, "obtener_token_sign", lambda db, cfg: ("TOKEN", "SIGN"))
    monkeypatch.setattr(arca_router, "consultar_ultimo_autorizado", lambda *a, **k: 0)

    def _rechaza(*a, **k):
        raise ArcaWsfeRechazo("Comprobante rechazado", ["10015: CUIT inválido"])
    monkeypatch.setattr(arca_router, "solicitar_cae", _rechaza)

    r = client.post("/arca/comprobantes", json={
        "tipo_comprobante": 11, "importe_total": 500.0,
    }, headers=_auth(tok_admin))
    cid = r.json()["id"]

    r2 = client.post(f"/arca/comprobantes/{cid}/emitir", headers=_auth(tok_admin))
    assert r2.status_code == 422

    c = db.query(ComprobanteArca).filter(ComprobanteArca.id == cid).first()
    assert c.estado == "rechazado"
    assert "CUIT inválido" in c.error_detalle


def test_emitir_error_tecnico(client, db, monkeypatch):
    tok_admin = _token(db, "admin@arca.test")
    _activar(client, tok_admin)
    monkeypatch.setattr(arca_router, "obtener_token_sign", lambda db, cfg: ("TOKEN", "SIGN"))

    def _falla(*a, **k):
        raise ArcaWsfeError("timeout")
    monkeypatch.setattr(arca_router, "consultar_ultimo_autorizado", _falla)

    r = client.post("/arca/comprobantes", json={
        "tipo_comprobante": 11, "importe_total": 500.0,
    }, headers=_auth(tok_admin))
    cid = r.json()["id"]

    r2 = client.post(f"/arca/comprobantes/{cid}/emitir", headers=_auth(tok_admin))
    assert r2.status_code == 502
    c = db.query(ComprobanteArca).filter(ComprobanteArca.id == cid).first()
    assert c.estado == "error"


# ── aislamiento multi-org ────────────────────────────────────────

def test_aislamiento_multi_org(client, db):
    cfg2 = ArcaConfig(organizacion_id=2, activo=False)
    db.add(cfg2)
    db.commit()

    tok_admin = _token(db, "admin@arca.test")
    r = client.get("/arca/comprobantes", headers=_auth(tok_admin))
    assert r.status_code == 200
    assert r.json()["total"] == 0


# ── arca_wsfe: FchServDesde/FchServHasta/FchVtoPago obligatorios para servicios ──

def test_solicitar_cae_servicios_sin_fechas_falla():
    from app.services.arca_wsfe import solicitar_cae, DatosComprobante

    datos = DatosComprobante(
        cuit="20111111112", punto_venta=1, tipo_comprobante=11, numero=1, concepto=2,
        doc_tipo=99, doc_nro="0", fecha_emision="20260625",
        importe_neto=Decimal("826.45"), importe_iva=Decimal("173.55"), importe_total=Decimal("1000.00"),
    )
    with pytest.raises(ArcaWsfeError):
        solicitar_cae("TOKEN", "SIGN", "homologacion", datos)


def test_solicitar_cae_productos_no_requiere_fechas(monkeypatch):
    from app.services import arca_wsfe
    from app.services.arca_wsfe import solicitar_cae, DatosComprobante

    capturado = {}

    def _fake_soap_call(ambiente, soap_action, body_xml):
        capturado["body"] = body_xml
        import xml.etree.ElementTree as ET
        return ET.fromstring(
            "<r><Resultado>A</Resultado><CAE>123</CAE><CAEFchVto>20260710</CAEFchVto></r>"
        )

    monkeypatch.setattr(arca_wsfe, "_soap_call", _fake_soap_call)

    datos = DatosComprobante(
        cuit="20111111112", punto_venta=1, tipo_comprobante=11, numero=1, concepto=1,
        doc_tipo=99, doc_nro="0", fecha_emision="20260625",
        importe_neto=Decimal("826.45"), importe_iva=Decimal("173.55"), importe_total=Decimal("1000.00"),
    )
    resultado = solicitar_cae("TOKEN", "SIGN", "homologacion", datos)
    assert resultado["cae"] == "123"
    assert "FchServDesde" not in capturado["body"]
