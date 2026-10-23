"""Permisos y auditoría por organización (revisión de seguridad oct/2026).

- Auditoría por org: cada log guarda `organizacion_id` (migración 035). Un usuario con
  `view_audit` en la org 1 ya no ve lo que hizo el superadmin en la org 2. Los logs viejos
  (sin org) se siguen filtrando por la org del usuario, como antes.
- Escrituras con permiso: el revisor es de solo lectura; los endpoints que escriben y no
  pedían permiso ahora piden el permiso que ya tiene el rol que los usa.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.auditoria import AuditoriaLog
from app.models.cliente import Cliente
from app.models.organizacion import Organizacion
from app.models.user import User
from app.services.auditoria import org_activa, registrar_log
from app.services.auth import create_access_token, get_password_hash


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    s = sessionmaker(bind=engine)()
    s.add_all([Organizacion(id=1, nombre="Org1"), Organizacion(id=2, nombre="Org2")])
    s.commit()
    usuarios = (
        ("super@t.test", 1, "admin", True),
        ("admin1@t.test", 1, "admin", False),
        ("op1@t.test", 1, "operador", False),
        ("rev1@t.test", 1, "revisor", False),
        ("aud1@t.test", 1, "auditor", False),
    )
    for email, org, rol, sa in usuarios:
        s.add(User(
            email=email, full_name=email, hashed_password=get_password_hash("pw123456"),
            organizacion_id=org, is_active=True, role=rol, is_superadmin=sa,
        ))
    s.commit()
    yield s
    s.close()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app, raise_server_exceptions=True)
    app.dependency_overrides.pop(get_db, None)


def _user(db, email):
    return db.query(User).filter(User.email == email).first()


def _auth(db, email):
    u = _user(db, email)
    tok = create_access_token({"sub": u.email, "user_id": u.id, "role": u.role})
    return {"Authorization": f"Bearer {tok}"}


# ── 1. Auditoría por organización ─────────────────────────────────────────

def _acciones(client, db, email, **params):
    r = client.get("/auditoria", headers=_auth(db, email), params=params)
    assert r.status_code == 200, r.text
    return {i["accion"] for i in r.json()["items"]}


def test_auditor_org1_no_ve_log_del_superadmin_en_org2(client, db):
    sa = _user(db, "super@t.test")
    db.add_all([
        AuditoriaLog(usuario_id=sa.id, organizacion_id=2, tabla="clientes", registro_id=1,
                     accion="ACCION_EN_ORG2"),
        AuditoriaLog(usuario_id=sa.id, organizacion_id=1, tabla="clientes", registro_id=1,
                     accion="ACCION_EN_ORG1"),
    ])
    db.commit()
    for email in ("aud1@t.test", "admin1@t.test"):
        acciones = _acciones(client, db, email)
        assert "ACCION_EN_ORG1" in acciones
        assert "ACCION_EN_ORG2" not in acciones
    # El superadmin ve todo sin filtro y filtra por la org que pida.
    assert {"ACCION_EN_ORG1", "ACCION_EN_ORG2"} <= _acciones(client, db, "super@t.test")
    assert _acciones(client, db, "super@t.test", org_id=2) == {"ACCION_EN_ORG2"}


def test_log_viejo_sin_org_sigue_filtrandose_por_el_usuario(client, db):
    """Las filas de antes de la migración 035 (NULL) no desaparecen del historial."""
    op = _user(db, "op1@t.test")
    db.add(AuditoriaLog(usuario_id=op.id, organizacion_id=None, tabla="clientes",
                        registro_id=1, accion="VIEJO_ORG1"))
    db.commit()
    assert "VIEJO_ORG1" in _acciones(client, db, "aud1@t.test")
    # Un usuario de otra org no lo ve.
    db.add(Organizacion(id=3, nombre="Org3"))
    db.add(User(email="aud3@t.test", full_name="aud3", hashed_password=get_password_hash("x"),
                organizacion_id=3, is_active=True, role="auditor", is_superadmin=False))
    db.commit()
    assert "VIEJO_ORG1" not in _acciones(client, db, "aud3@t.test")


def test_registrar_log_toma_la_org_del_registro(db):
    sa = _user(db, "super@t.test")
    c = Cliente(nombre="Cliente org2", organizacion_id=2)
    db.add(c)
    db.commit()
    # Aunque la org activa sea la 1, el registro afectado es de la org 2.
    token = org_activa.set(1)
    try:
        log = registrar_log(db, sa.id, "clientes", c.id, "UPDATE")
        assert log.organizacion_id == 2
        # Tabla con nombre propio (no es una tabla real): usa la org activa.
        log = registrar_log(db, sa.id, "iva_config", 7, "UPDATE")
        assert log.organizacion_id == 1
        # Org explícita gana.
        log = registrar_log(db, sa.id, "iva_config", 7, "UPDATE", organizacion_id=2)
        assert log.organizacion_id == 2
        # La org de una organización es ella misma.
        log = registrar_log(db, sa.id, "organizaciones", 2, "UPDATE")
        assert log.organizacion_id == 2
    finally:
        org_activa.reset(token)
    # Sin request ni registro conocido (p. ej. un scheduler): NULL.
    log = registrar_log(db, sa.id, "sistema", 0, "BACKUP_AUTO_OK")
    assert log.organizacion_id is None


def test_endpoint_marca_el_log_con_la_org_activa(client, db):
    """Un log con tabla de nombre propio, escrito desde un request (endpoint sync), queda con
    la org activa del usuario: la contextvar que setea get_current_user llega al threadpool."""
    from app.models.contabilidad import PlanCuenta
    from app.services.seed_contable import seed_contabilidad_org
    seed_contabilidad_org(db, 2)
    cuenta = db.query(PlanCuenta).filter(
        PlanCuenta.organizacion_id == 2, PlanCuenta.tipo == "resultado").first()
    r = client.put(f"/iva/config/{cuenta.id}", headers=_auth(db, "super@t.test"),
                   params={"org_id": 2}, json={"tasa_iva": 0.21})
    assert r.status_code == 200, r.text
    log = db.query(AuditoriaLog).filter(AuditoriaLog.tabla == "iva_config").one()
    assert log.organizacion_id == 2
    # Y la org 1 no lo ve, aunque el superadmin sea "de" la org 1.
    assert "UPDATE" not in _acciones(client, db, "aud1@t.test")
