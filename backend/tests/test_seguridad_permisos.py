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


# ── 2. Escrituras con permiso: el revisor es de solo lectura ──────────────

_XLSX = {"file": ("x.xlsx", b"PK\x03\x04",
                  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}

# (método, path, kwargs del request). El permiso se chequea antes de validar el body,
# así que alcanza con un body mínimo: lo que importa es que el revisor reciba 403.
ESCRITURAS_REVISOR = [
    ("post", "/extractos/upload", {"files": _XLSX}),
    ("patch", "/extractos/1/renombrar", {"json": {"nombre": "x"}}),
    ("post", "/extractos/1/agregar-um", {"files": _XLSX}),
    ("patch", "/extractos/1/movimientos/1", {"json": {"titular": "x"}}),
    ("delete", "/extractos", {}),
    ("post", "/planillas/1/revision/1/resolver", {"json": {}}),
    ("patch", "/planillas/rows/1", {"json": {"status": "ok"}}),
    ("put", "/planillas/1/comision", {"json": {"porcentaje": 0.01}}),
    ("post", "/auditoria/patrones/importar-historico", {"json": {"patrones": []}}),
    ("post", "/clientes", {"json": {"nombre": "Nuevo"}}),
    ("put", "/clientes/1/renombrar", {"json": {"nombre": "Otro"}}),
    ("post", "/clientes/1/fusionar", {"json": {"target_id": 2}}),
    ("put", "/clientes/1/comision", {"json": {"porcentaje": 0.01}}),
    ("post", "/clientes/movimientos/1/acreditar", {"json": {"cliente_id": 1}}),
    ("post", "/clientes/1/share-link", {}),
    ("put", "/caja/arqueo/hoy", {"json": {"saldo_inicial": 1}}),
    ("post", "/cheques", {"json": {}}),
    ("post", "/cheques/bulk-crear", {"json": {"cheques": []}}),
    ("post", "/cheques/portadores", {"json": {"nombre": "P"}}),
    ("patch", "/cheques/1", {"json": {"monto": 1}}),
    ("post", "/cheques/1/foto", {"json": {"foto": "x"}}),
    ("post", "/cheques/importar", {"files": _XLSX}),
    ("post", "/cheques/1/acreditar", {"json": {}}),
    ("post", "/cheques/acreditar", {"json": {"ids": [1]}}),
    ("post", "/cheques/1/rechazar", {"json": {}}),
    ("post", "/pagos/1/compartir", {}),
    ("post", "/contabilidad/reset-y-rebuild", {}),
    ("post", "/push/test", {}),
    ("post", "/push/setup", {}),
]


@pytest.mark.parametrize("metodo,path,kwargs", ESCRITURAS_REVISOR,
                         ids=[f"{m.upper()} {p}" for m, p, _ in ESCRITURAS_REVISOR])
def test_revisor_no_puede_escribir(client, db, metodo, path, kwargs):
    r = getattr(client, metodo)(path, headers=_auth(db, "rev1@t.test"), **kwargs)
    assert r.status_code == 403, f"{metodo.upper()} {path} → {r.status_code}: {r.text[:200]}"


def test_operador_sigue_pudiendo_escribir(client, db):
    h = _auth(db, "op1@t.test")
    r = client.post("/clientes", headers=h, json={"nombre": "Cliente del operador"})
    assert r.status_code == 200, r.text
    cid = r.json()["id"]
    r = client.put(f"/clientes/{cid}/renombrar", headers=h, json={"nombre": "Renombrado"})
    assert r.status_code == 200, r.text
    r = client.post("/cheques/portadores", headers=h, json={"nombre": "Portador op"})
    assert r.status_code in (200, 201), r.text
    # Sin datos: no es 403 (pasa el permiso y falla después por otra razón).
    assert client.put("/caja/arqueo/hoy", headers=h, json={"saldo_inicial": 1}).status_code != 403
    assert client.patch("/extractos/999/renombrar", headers=h,
                        json={"nombre": "x"}).status_code == 404
    assert client.patch("/planillas/rows/999", headers=h,
                        json={"status": "ok"}).status_code != 403


def test_auditor_conserva_finanzas(client, db):
    """El auditor tiene manage_finance: cheques y caja le siguen andando."""
    r = client.post("/cheques/portadores", headers=_auth(db, "aud1@t.test"),
                    json={"nombre": "Portador aud"})
    assert r.status_code in (200, 201), r.text


# ── 3. Meta-test: toda ruta que escribe pide permiso o está en la lista ───

# Rutas que escriben sin require_permission / require_superadmin, a propósito.
# Clave: "<módulo del router>.<función>" (no depende del prefijo ni de la versión de FastAPI).
SIN_PERMISO_A_PROPOSITO = {
    # Públicas (sin JWT): login, recuperación de contraseña, 2FA, Google, logout.
    "auth.login", "auth.forgot_password", "auth.reset_password", "auth.logout",
    "auth.verify_2fa", "google_auth.google_login",
    # Webhook de Resend Inbound: firma Svix, sin JWT (SECURITY_MODEL §8b).
    "comprobantes_compra.webhook_resend",
    # Autoservicio del propio usuario.
    "me.change_password", "me.update_profile",
    "push_router.subscribe", "push_router.unsubscribe",
    # Asistente IA: solo lee y devuelve datos; no escribe en la base (cupo diario por org).
    "agente.chat", "agente.ocr_cheque", "agente.ocr_transferencia", "agente.transcribir_audio",
    # POST de solo lectura: busca candidatos o devuelve un archivo, no modifica la base.
    "clientes_dir.buscar_movimiento_para_acreditar",
    "clientes_dir.guardar_planilla_en_carpeta",
}


def _rutas(routes):
    """APIRoutes de la app. FastAPI ≥0.150 anida los routers incluidos (`original_router`)."""
    from fastapi.routing import APIRoute
    for r in routes:
        if isinstance(r, APIRoute):
            yield r
        elif hasattr(r, "original_router"):
            yield from _rutas(r.original_router.routes)


def _dependencias(dependant):
    for sub in dependant.dependencies:
        yield sub.call
        yield from _dependencias(sub)


def _pide_permiso(route) -> bool:
    for call in _dependencias(route.dependant):
        nombre = getattr(call, "__qualname__", "")
        if nombre.startswith("require_permission.") or nombre == "require_superadmin":
            return True
    return False


def test_toda_ruta_que_escribe_pide_permiso():
    mutantes = [r for r in _rutas(app.routes) if r.methods - {"GET", "HEAD", "OPTIONS"}]
    assert len(mutantes) > 100, "no se encontraron las rutas: ¿cambió la estructura de FastAPI?"
    vistas, faltan = set(), []
    for r in mutantes:
        clave = f"{r.endpoint.__module__.rsplit('.', 1)[-1]}.{r.endpoint.__name__}"
        if _pide_permiso(r):
            continue
        vistas.add(clave)
        if clave not in SIN_PERMISO_A_PROPOSITO:
            faltan.append(f"{sorted(r.methods)} {r.path} ({clave})")
    assert not faltan, (
        "Rutas que escriben sin require_permission/require_superadmin. Agregá el permiso "
        "o, si es autoservicio/pública, sumala a SIN_PERMISO_A_PROPOSITO:\n  - "
        + "\n  - ".join(faltan)
    )
    # La lista no acumula entradas muertas.
    assert not (SIN_PERMISO_A_PROPOSITO - vistas), SIN_PERMISO_A_PROPOSITO - vistas
