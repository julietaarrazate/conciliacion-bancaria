"""Revisión de seguridad oct/2026 — lote 4.

1. La contraseña de la superadmin sale de `SUPERADMIN_PASSWORD` solo al crearla; un
   cambio desde /perfil ya no se pisa en cada arranque (salvo `SUPERADMIN_PASSWORD_RESET=1`).
"""
import logging
import secrets

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import SUPERADMIN_EMAIL, app, seed_superadmin
from app.models.cliente import Cliente
from app.models.organizacion import Organizacion
from app.models.user import User
from app.services.auth import create_access_token, get_password_hash, verify_password

# Valores de prueba generados al correr (no hay claves escritas en el código).
CLAVE_ENV = secrets.token_urlsafe(12)
CLAVE_PERFIL = secrets.token_urlsafe(12)
CLAVE_OLVIDADA = secrets.token_urlsafe(12)
CLAVE_EMERGENCIA = secrets.token_urlsafe(12)


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
        ("cont1@t.test", 1, "contador", False),
        ("op1@t.test", 1, "operador", False),
        ("rev1@t.test", 1, "revisor", False),
        ("admin2@t.test", 2, "admin", False),
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


# ── 1. Contraseña de la superadmin al arrancar ────────────────────────────

def _julieta(db):
    return db.query(User).filter(User.email == SUPERADMIN_EMAIL).first()


def test_superadmin_se_crea_con_la_env_si_no_existe(db, monkeypatch):
    monkeypatch.setenv("SUPERADMIN_PASSWORD", CLAVE_ENV)
    monkeypatch.delenv("SUPERADMIN_PASSWORD_RESET", raising=False)
    assert seed_superadmin(db) == "creada"
    j = _julieta(db)
    assert j.is_superadmin and j.is_active and j.role == "admin" and j.organizacion_id == 1
    assert verify_password(CLAVE_ENV, j.hashed_password)


def test_superadmin_sin_env_y_sin_usuario_no_se_crea(db, monkeypatch):
    monkeypatch.delenv("SUPERADMIN_PASSWORD", raising=False)
    assert seed_superadmin(db) == "sin_password"
    assert _julieta(db) is None


def test_superadmin_existente_conserva_la_contrasena_de_perfil(db, monkeypatch):
    monkeypatch.setenv("SUPERADMIN_PASSWORD", CLAVE_ENV)
    monkeypatch.delenv("SUPERADMIN_PASSWORD_RESET", raising=False)
    seed_superadmin(db)
    j = _julieta(db)
    # La cambia desde /perfil y le tocan los flags
    j.hashed_password = get_password_hash(CLAVE_PERFIL)
    j.is_active = False
    j.role = "operador"
    db.commit()

    assert seed_superadmin(db) == "actualizada"
    j = _julieta(db)
    assert verify_password(CLAVE_PERFIL, j.hashed_password)
    assert not verify_password(CLAVE_ENV, j.hashed_password)
    # El resto del paso sigue igual: flags asegurados
    assert j.is_active and j.is_superadmin and j.role == "admin"


def test_superadmin_reset_explicito_pisa_una_vez_y_avisa(db, monkeypatch, caplog):
    monkeypatch.setenv("SUPERADMIN_PASSWORD", CLAVE_ENV)
    seed_superadmin(db)
    j = _julieta(db)
    j.hashed_password = get_password_hash(CLAVE_OLVIDADA)
    db.commit()

    monkeypatch.setenv("SUPERADMIN_PASSWORD", CLAVE_EMERGENCIA)
    monkeypatch.setenv("SUPERADMIN_PASSWORD_RESET", "1")
    with caplog.at_level(logging.WARNING, logger="app.main"):
        assert seed_superadmin(db) == "reseteada"
    j = _julieta(db)
    assert verify_password(CLAVE_EMERGENCIA, j.hashed_password)
    assert j.password_changed_at is not None  # corta las sesiones abiertas
    assert any("SUPERADMIN_PASSWORD_RESET" in r.message for r in caplog.records)

    # Siguiente arranque con la variable todavía puesta: no vuelve a re-hashear
    marca = j.password_changed_at
    hash_actual = j.hashed_password
    assert seed_superadmin(db) == "actualizada"
    j = _julieta(db)
    assert j.hashed_password == hash_actual
    assert j.password_changed_at == marca


def test_superadmin_reset_con_otro_valor_no_resetea(db, monkeypatch):
    monkeypatch.setenv("SUPERADMIN_PASSWORD", CLAVE_ENV)
    seed_superadmin(db)
    j = _julieta(db)
    j.hashed_password = get_password_hash(CLAVE_PERFIL)
    db.commit()
    monkeypatch.setenv("SUPERADMIN_PASSWORD_RESET", "true")  # solo "1" activa el reset
    assert seed_superadmin(db) == "actualizada"
    assert verify_password(CLAVE_PERFIL, _julieta(db).hashed_password)


# ── 2. Fusionar clientes pide delete_records ──────────────────────────────

def _dos_clientes(db, org=1):
    a = Cliente(nombre="Origen", organizacion_id=org)
    b = Cliente(nombre="Destino", organizacion_id=org)
    db.add_all([a, b])
    db.commit()
    return a.id, b.id


@pytest.mark.parametrize("email", ["op1@t.test", "cont1@t.test", "rev1@t.test"])
def test_fusionar_sin_delete_records_es_403(client, db, email):
    src, dst = _dos_clientes(db)
    r = client.post(f"/clientes/{src}/fusionar", headers=_auth(db, email), json={"target_id": dst})
    assert r.status_code == 403, r.text
    assert db.get(Cliente, src) is not None  # no borró nada


@pytest.mark.parametrize("email", ["admin1@t.test", "super@t.test"])
def test_fusionar_con_delete_records_funciona(client, db, email):
    src, dst = _dos_clientes(db)
    r = client.post(f"/clientes/{src}/fusionar", headers=_auth(db, email), json={"target_id": dst})
    assert r.status_code == 200, r.text
    db.expire_all()
    assert db.get(Cliente, src) is None


def test_fusionar_admin_de_otra_org_sigue_bloqueado(client, db):
    src, dst = _dos_clientes(db, org=1)
    r = client.post(f"/clientes/{src}/fusionar", headers=_auth(db, "admin2@t.test"),
                    json={"target_id": dst})
    assert r.status_code == 403, r.text


# ── 3. Push: el endpoint de otro usuario se reasigna ──────────────────────

_SUB = {"endpoint": "https://push.example/abc", "keys": {"p256dh": "k1", "auth": "a1"}}


def _subs(db):
    from app.models.push_subscription import PushSubscription
    db.expire_all()
    return db.query(PushSubscription).filter(PushSubscription.endpoint == _SUB["endpoint"]).all()


def test_push_subscribe_mismo_usuario_ya_suscripto(client, db):
    h = _auth(db, "op1@t.test")
    assert client.post("/push/subscribe", headers=h, json=_SUB).json()["status"] == "subscribed"
    assert client.post("/push/subscribe", headers=h, json=_SUB).json()["status"] == "already_subscribed"
    subs = _subs(db)
    assert len(subs) == 1 and subs[0].user_id == _user(db, "op1@t.test").id


def test_push_subscribe_endpoint_de_otro_usuario_se_reasigna(client, db):
    client.post("/push/subscribe", headers=_auth(db, "op1@t.test"), json=_SUB)
    nuevo = {"endpoint": _SUB["endpoint"], "keys": {"p256dh": "k2", "auth": "a2"}}
    r = client.post("/push/subscribe", headers=_auth(db, "rev1@t.test"), json=nuevo)
    assert r.status_code == 200 and r.json()["status"] == "reassigned"
    subs = _subs(db)
    assert len(subs) == 1
    assert subs[0].user_id == _user(db, "rev1@t.test").id
    assert (subs[0].p256dh, subs[0].auth) == ("k2", "a2")
    # El usuario anterior ya no la puede borrar (no es suya); el nuevo sí.
    client.request("DELETE", "/push/subscribe", headers=_auth(db, "op1@t.test"), json=_SUB)
    assert len(_subs(db)) == 1
    client.request("DELETE", "/push/subscribe", headers=_auth(db, "rev1@t.test"), json=_SUB)
    assert _subs(db) == []


# ── 4. GET /caja/arqueo/hoy no escribe ────────────────────────────────────

def _arqueos(db):
    from app.models.caja import ArqueoDiario
    db.expire_all()
    return db.query(ArqueoDiario).order_by(ArqueoDiario.fecha).all()


def _arqueo_anterior(db, fecha="2026-06-01"):
    """Arqueo del día anterior con $1.500 en caja y 1 billete de $1000 + 1 de $500."""
    from datetime import date
    from decimal import Decimal
    from app.models.caja import ArqueoDiario, denominaciones_vacias
    dens = denominaciones_vacias()
    dens.update({"1000": 1, "500": 1})
    db.add(ArqueoDiario(organizacion_id=1, fecha=date.fromisoformat(fecha),
                        saldo_inicial=Decimal("1500"), pesos_agregados=0, ingresos=0,
                        denominaciones=dens, creado_por=_user(db, "op1@t.test").id))
    db.commit()


def test_get_arqueo_hoy_no_crea_y_devuelve_borrador(client, db):
    _arqueo_anterior(db)
    r = client.get("/caja/arqueo/hoy", headers=_auth(db, "rev1@t.test"),
                   params={"fecha_str": "2026-06-02"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["id"] is None and data["guardado"] is False
    assert float(data["saldo_inicial"]) == 1500  # arrastra el saldo del día anterior
    assert data["denominaciones"]["1000"] == 1
    assert len(_arqueos(db)) == 1  # no se creó nada


def test_put_arqueo_hoy_crea_el_arqueo_con_el_saldo_arrastrado(client, db):
    _arqueo_anterior(db)
    r = client.put("/caja/arqueo/hoy", headers=_auth(db, "op1@t.test"),
                   json={"fecha": "2026-06-02", "notas": "abro caja"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["id"] is not None and data["guardado"] is True
    assert float(data["saldo_inicial"]) == 1500
    assert data["notas"] == "abro caja"
    arqueos = _arqueos(db)
    assert len(arqueos) == 2 and str(arqueos[1].fecha) == "2026-06-02"
    # El GET ahora devuelve el guardado
    r = client.get("/caja/arqueo/hoy", headers=_auth(db, "op1@t.test"),
                   params={"fecha_str": "2026-06-02"})
    assert r.json()["id"] == data["id"] and r.json()["guardado"] is True


def test_put_arqueo_hoy_revisor_sigue_sin_poder_crear(client, db):
    r = client.put("/caja/arqueo/hoy", headers=_auth(db, "rev1@t.test"),
                   json={"fecha": "2026-06-02", "saldo_inicial": 1})
    assert r.status_code == 403
    assert _arqueos(db) == []


def test_pago_en_efectivo_crea_el_arqueo_con_el_saldo_arrastrado(db):
    """El pago en efectivo usa el mismo armado que el PUT (antes arrancaba en 0)."""
    from datetime import date
    from app.services.arqueo import obtener_o_crear_arqueo
    _arqueo_anterior(db)
    a = obtener_o_crear_arqueo(db, 1, date(2026, 6, 2), _user(db, "op1@t.test").id)
    db.commit()
    assert a.id is not None and float(a.saldo_inicial) == 1500
    assert obtener_o_crear_arqueo(db, 1, date(2026, 6, 2), 1).id == a.id


# ── 5. Backup y reset filtran la auditoría por la org del log ─────────────

def _logs_cruzados(db):
    """El superadmin (usuario de la org 1) trabaja en la org 2; el admin de la org 1 en la 1;
    y un log viejo sin org hecho por el admin de la org 1."""
    from app.models.auditoria import AuditoriaLog
    sa, a1 = _user(db, "super@t.test"), _user(db, "admin1@t.test")
    db.add_all([
        AuditoriaLog(usuario_id=sa.id, organizacion_id=2, tabla="clientes", registro_id=1,
                     accion="SA_EN_ORG2"),
        AuditoriaLog(usuario_id=a1.id, organizacion_id=1, tabla="clientes", registro_id=1,
                     accion="ADMIN_EN_ORG1"),
        AuditoriaLog(usuario_id=a1.id, organizacion_id=None, tabla="clientes", registro_id=1,
                     accion="VIEJO_SIN_ORG"),
    ])
    db.commit()


def test_backup_respalda_la_auditoria_por_la_org_del_log(db):
    from app.services.backup_service import export_org_backup
    _logs_cruzados(db)
    acciones_1 = {a["accion"] for a in export_org_backup(db, 1)["auditoria"]}
    acciones_2 = {a["accion"] for a in export_org_backup(db, 2)["auditoria"]}
    assert acciones_1 == {"ADMIN_EN_ORG1", "VIEJO_SIN_ORG"}  # sin lo del superadmin en la 2
    assert acciones_2 == {"SA_EN_ORG2"}


def test_reset_borra_la_auditoria_por_la_org_del_log(db):
    from app.models.auditoria import AuditoriaLog
    from app.services.reset_operativo import reset_datos_operativos
    _logs_cruzados(db)
    res = reset_datos_operativos(db, [2], dry_run=True)
    assert res.get("auditoria") == 1
    reset_datos_operativos(db, [2])
    db.commit()
    quedan = {a.accion for a in db.query(AuditoriaLog).all()}
    # Se borró lo hecho en la org 2 aunque el usuario sea de la org 1; la org 1 intacta.
    assert quedan == {"ADMIN_EN_ORG1", "VIEJO_SIN_ORG"}
