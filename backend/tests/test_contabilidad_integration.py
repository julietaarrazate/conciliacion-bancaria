"""
Tests de integración para el módulo de contabilidad vía FastAPI TestClient.

Cubre los endpoints de los 4 sub-módulos (ctb_plan, ctb_libro, ctb_clientes,
ctb_ctas_corrientes) expuestos bajo /contabilidad:
  - GET  /contabilidad/plan-cuentas
  - GET  /contabilidad/stats
  - GET  /contabilidad/asientos
  - POST /contabilidad/asiento-manual  (partida doble válida e inválida)
  - GET  /contabilidad/cuentas-corrientes
"""
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
from app.models.contabilidad import PlanCuenta


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def db():
    """DB SQLite en memoria con org, admin y plan de cuentas semilleado."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    org = Organizacion(id=1, nombre="OrgCtb")
    session.add(org)
    session.commit()

    # Plan de cuentas completo (necesario para asiento-manual)
    seed_contabilidad_org(session, 1)

    # Admin: tiene admin_accounting + manage_finance + view_accounting
    admin = User(
        email="admin@ctb.test", full_name="Admin Ctb",
        hashed_password=get_password_hash("pw123"),
        organizacion_id=1, is_active=True, role="admin", is_superadmin=False,
    )
    # Operador: manage_finance + view_accounting, NO admin_accounting
    operador = User(
        email="op@ctb.test", full_name="Operador Ctb",
        hashed_password=get_password_hash("pw123"),
        organizacion_id=1, is_active=True, role="operador", is_superadmin=False,
    )
    session.add_all([admin, operador])
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


def _token(db, email):
    user = db.query(User).filter(User.email == email).first()
    return create_access_token({"sub": user.email, "user_id": user.id, "role": user.role})


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _cuentas_hoja(db):
    """Retorna dos cuentas hoja distintas (sin hijos) para usar en asiento-manual."""
    # Cuentas hoja típicas del plan base: 1-1-1-3-1 (Banco Macro) y 3-2-0-0 (Gastos)
    # Buscamos cuentas que no tengan hijos
    all_parents = {
        c.parent_id for c in db.query(PlanCuenta).filter(
            PlanCuenta.organizacion_id == 1,
            PlanCuenta.parent_id.isnot(None)
        ).all()
    }
    hojas = db.query(PlanCuenta).filter(
        PlanCuenta.organizacion_id == 1,
        PlanCuenta.activo == True,
        PlanCuenta.id.notin_(all_parents),
    ).limit(2).all()
    assert len(hojas) >= 2, "El plan de cuentas debe tener al menos 2 cuentas hoja"
    return hojas[0].id, hojas[1].id


# ── Tests: plan de cuentas ────────────────────────────────────────────────────

class TestPlanCuentas:

    def test_get_plan_cuentas_retorna_200_lista_no_vacia(self, client, db):
        """GET /contabilidad/plan-cuentas → 200 y lista paginada con cuentas semilleadas."""
        token = _token(db, "admin@ctb.test")
        r = client.get("/contabilidad/plan-cuentas", headers=_auth(token))
        assert r.status_code == 200
        data = r.json()
        assert "items" in data, "La respuesta debe tener clave 'items'"
        assert "total" in data, "La respuesta debe tener clave 'total'"
        assert isinstance(data["items"], list)
        assert len(data["items"]) > 0
        assert data["total"] > 0

    def test_plan_cuentas_contiene_campos_esperados(self, client, db):
        token = _token(db, "admin@ctb.test")
        r = client.get("/contabilidad/plan-cuentas", headers=_auth(token))
        assert r.status_code == 200
        item = r.json()["items"][0]
        for campo in ("id", "codigo", "nombre", "tipo", "nivel"):
            assert campo in item, f"Campo '{campo}' faltante en la respuesta"

    def test_plan_cuentas_requiere_auth(self, client):
        r = client.get("/contabilidad/plan-cuentas")
        assert r.status_code in (401, 403)


# ── Tests: stats ──────────────────────────────────────────────────────────────

class TestStats:

    def test_get_stats_retorna_200(self, client, db):
        """GET /contabilidad/stats → 200 con conteos."""
        token = _token(db, "admin@ctb.test")
        r = client.get("/contabilidad/stats", headers=_auth(token))
        assert r.status_code == 200
        data = r.json()
        assert "plan_cuentas" in data
        assert "reglas" in data
        assert "asientos" in data
        assert data["plan_cuentas"] > 0  # el seed crea cuentas

    def test_stats_requiere_auth(self, client):
        r = client.get("/contabilidad/stats")
        assert r.status_code in (401, 403)


# ── Tests: asientos ───────────────────────────────────────────────────────────

class TestAsientos:

    def test_get_asientos_retorna_200(self, client, db):
        """GET /contabilidad/asientos → 200 con paginación."""
        token = _token(db, "admin@ctb.test")
        r = client.get("/contabilidad/asientos", headers=_auth(token))
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)

    def test_asientos_requiere_auth(self, client):
        r = client.get("/contabilidad/asientos")
        assert r.status_code in (401, 403)

    def test_asientos_filtro_modulo(self, client, db):
        """El filtro ?modulo= funciona y no retorna 500."""
        token = _token(db, "admin@ctb.test")
        r = client.get("/contabilidad/asientos?modulo=um_lote", headers=_auth(token))
        assert r.status_code == 200
        # Sin datos previos de ese módulo, debe devolver lista vacía
        assert r.json()["total"] == 0


# ── Tests: asiento-manual ─────────────────────────────────────────────────────

class TestAsientoManual:

    def test_asiento_manual_partida_doble_valida(self, client, db):
        """POST /contabilidad/asiento-manual con monto > 0 → 200, crea asiento."""
        token = _token(db, "admin@ctb.test")
        debe_id, haber_id = _cuentas_hoja(db)

        r = client.post(
            "/contabilidad/asiento-manual",
            json={
                "cuenta_debe_id": debe_id,
                "cuenta_haber_id": haber_id,
                "monto": 1000.0,
                "fecha": "2026-06-10",
                "descripcion": "Ajuste test integración",
            },
            headers=_auth(token),
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["ok"] is True
        assert "asiento_id" in data
        assert isinstance(data["asiento_id"], int)

    def test_asiento_manual_cuentas_iguales_retorna_400(self, client, db):
        """Debe y Haber iguales → HTTP 400."""
        token = _token(db, "admin@ctb.test")
        debe_id, _ = _cuentas_hoja(db)

        r = client.post(
            "/contabilidad/asiento-manual",
            json={
                "cuenta_debe_id": debe_id,
                "cuenta_haber_id": debe_id,  # ← misma cuenta
                "monto": 500.0,
                "fecha": "2026-06-10",
                "descripcion": "Inválido",
            },
            headers=_auth(token),
        )
        assert r.status_code == 400

    def test_asiento_manual_monto_cero_retorna_400(self, client, db):
        """Monto = 0 → HTTP 400."""
        token = _token(db, "admin@ctb.test")
        debe_id, haber_id = _cuentas_hoja(db)

        r = client.post(
            "/contabilidad/asiento-manual",
            json={
                "cuenta_debe_id": debe_id,
                "cuenta_haber_id": haber_id,
                "monto": 0.0,
                "fecha": "2026-06-10",
                "descripcion": "Monto cero",
            },
            headers=_auth(token),
        )
        assert r.status_code == 400

    def test_asiento_manual_requiere_permiso_admin_accounting(self, client, db):
        """El operador NO tiene admin_accounting → 403."""
        token = _token(db, "op@ctb.test")
        debe_id, haber_id = _cuentas_hoja(db)

        r = client.post(
            "/contabilidad/asiento-manual",
            json={
                "cuenta_debe_id": debe_id,
                "cuenta_haber_id": haber_id,
                "monto": 100.0,
                "fecha": "2026-06-10",
                "descripcion": "Sin permiso",
            },
            headers=_auth(token),
        )
        assert r.status_code == 403

    def test_asiento_manual_cuenta_inexistente_retorna_404(self, client, db):
        """Cuenta que no existe → HTTP 404."""
        token = _token(db, "admin@ctb.test")
        _, haber_id = _cuentas_hoja(db)

        r = client.post(
            "/contabilidad/asiento-manual",
            json={
                "cuenta_debe_id": 99999,
                "cuenta_haber_id": haber_id,
                "monto": 100.0,
                "fecha": "2026-06-10",
                "descripcion": "Cuenta inexistente",
            },
            headers=_auth(token),
        )
        assert r.status_code == 404


# ── Tests: cuentas corrientes ─────────────────────────────────────────────────

class TestCuentasCorrientes:

    def test_get_cuentas_corrientes_retorna_200(self, client, db):
        """GET /contabilidad/cuentas-corrientes → 200 (lista o dict con items)."""
        token = _token(db, "admin@ctb.test")
        r = client.get("/contabilidad/cuentas-corrientes", headers=_auth(token))
        assert r.status_code == 200
        data = r.json()
        # La respuesta puede ser una lista o un dict con 'items'
        assert isinstance(data, (list, dict))

    def test_cuentas_corrientes_requiere_manage_finance(self, client, db):
        """Sin token → 401/403."""
        r = client.get("/contabilidad/cuentas-corrientes")
        assert r.status_code in (401, 403)

    def test_operador_puede_ver_cuentas_corrientes(self, client, db):
        """El operador tiene manage_finance → puede ver cuentas corrientes."""
        token = _token(db, "op@ctb.test")
        r = client.get("/contabilidad/cuentas-corrientes", headers=_auth(token))
        assert r.status_code == 200


# ── Tests: caché de reportes (sumas-saldo / balance) e invalidación ───────────

class TestReportesCache:
    """El caché de sumas-saldo/balance no debe servir datos viejos: tras crear
    un asiento manual, los reportes tienen que reflejar el nuevo movimiento
    (la mutación invalida el caché). También chequea el N+1-fixed /reglas."""

    def test_sumas_saldo_se_actualiza_tras_asiento_manual(self, client, db):
        from app.routers.ctb_libro import _reportes_cache
        _reportes_cache.clear()  # arranque determinístico

        token = _token(db, "admin@ctb.test")
        debe_id, haber_id = _cuentas_hoja(db)

        def total_debe_de(cuenta_id):
            r = client.get("/contabilidad/sumas-saldo", headers=_auth(token))
            assert r.status_code == 200, r.text
            fila = next((x for x in r.json() if x["id"] == cuenta_id), None)
            return fila["total_debe"] if fila else 0.0

        antes = total_debe_de(debe_id)  # primer GET → puebla el caché

        monto = 1234.56
        r = client.post(
            "/contabilidad/asiento-manual",
            json={"cuenta_debe_id": debe_id, "cuenta_haber_id": haber_id,
                  "monto": monto, "fecha": "2026-06-15", "descripcion": "test cache"},
            headers=_auth(token),
        )
        assert r.status_code == 200, r.text

        # Sin invalidación, este GET devolvería el caché viejo y el delta sería 0.
        despues = total_debe_de(debe_id)
        assert round(despues - antes, 2) == monto

    def test_reglas_incluye_cuentas_debe_haber(self, client, db):
        """El /reglas (con selectinload) sigue serializando debe/haber completos."""
        token = _token(db, "admin@ctb.test")
        r = client.get("/contabilidad/reglas", headers=_auth(token))
        assert r.status_code == 200
        for regla in r.json()["items"]:
            for lado in ("debe", "haber"):
                assert regla[lado] is not None
                for campo in ("id", "codigo", "nombre"):
                    assert campo in regla[lado]
