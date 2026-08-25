"""
Tests E2E para /pagos usando FastAPI TestClient.

Cubren lo que los tests unitarios de test_pagos_v312.py NO pueden:
  - Routing HTTP real — habría detectado el @router.delete faltante
  - Auth middleware: 401 sin token, 403 por permiso insuficiente
  - Serialización JSON request/response completa
  - Flujo completo: token → crear → editar → eliminar

Se sobreescribe get_db con SQLite en memoria vía app.dependency_overrides.
Los tokens se generan directamente (sin HTTP login) para evitar el rate
limiter de /auth/login (10/minute). Un test separado cubre el login real.
"""
import pytest
from decimal import Decimal
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Importar app registra todos los modelos en Base.metadata (via imports en main.py)
from app.main import app
from app.database import Base, get_db
from app.services.auth import get_password_hash, create_access_token
from app.models.organizacion import Organizacion
from app.models.user import User
from app.models.egreso import Egreso


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def db():
    """DB SQLite en memoria con org y dos usuarios por cada test.

    Usa StaticPool para que todas las conexiones al mismo engine compartan
    la misma BD en memoria. Sin StaticPool, create_all() y cada Session
    obtendrían conexiones distintas → BDs distintas → 'no such table'.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    org = Organizacion(id=1, nombre="OrgE2E")
    session.add(org)

    # Admin: tiene reconcile + delete_records
    admin = User(
        email="admin@e2e.test", full_name="Admin E2E",
        hashed_password=get_password_hash("pw123"),
        organizacion_id=1, is_active=True, role="admin", is_superadmin=False,
    )
    # Operador: tiene reconcile, NO delete_records
    operador = User(
        email="op@e2e.test", full_name="Operador E2E",
        hashed_password=get_password_hash("pw123"),
        organizacion_id=1, is_active=True, role="operador", is_superadmin=False,
    )
    session.add_all([admin, operador])
    session.commit()

    yield session
    session.close()


@pytest.fixture
def client(db):
    """TestClient con get_db sobreescrito para usar la DB en memoria.

    Nota: NO usamos 'with TestClient(app)' como context manager porque eso
    dispara el lifespan de producción (_init_db en background thread), lo que
    puede interferir con nuestra DB en memoria. Sin context manager, los
    endpoints funcionan igual pero sin el startup/shutdown de prod.
    """
    def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    c = TestClient(app, raise_server_exceptions=True)
    yield c
    app.dependency_overrides.pop(get_db, None)


def _token(db, email):
    """Genera un JWT válido para el usuario dado sin pasar por /auth/login."""
    user = db.query(User).filter(User.email == email).first()
    return create_access_token({"sub": user.email, "user_id": user.id, "role": user.role})


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _crear_egreso(db, monto=1000, org_id=1):
    """Inserta un egreso directamente en la DB y retorna su id."""
    e = Egreso(
        organizacion_id=org_id, tipo="proveedor", forma_pago="banco",
        monto=Decimal(str(monto)), fecha=date(2026, 6, 1),
        beneficiario="Proveedor Original", compartido_whatsapp=False,
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return e.id


# ── Login real ───────────────────────────────────────────────────────────────

class TestLoginHTTP:
    """Verifica el login real via HTTP (cubre serialización y schema)."""

    def test_login_admin_retorna_token(self, client):
        r = client.post("/auth/login", json={"email": "admin@e2e.test", "password": "pw123"})
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_password_incorrecta_devuelve_401(self, client):
        r = client.post("/auth/login", json={"email": "admin@e2e.test", "password": "malo"})
        assert r.status_code == 401


# ── Autenticación / Autorización ─────────────────────────────────────────────

class TestAuth:

    def test_sin_token_get_devuelve_403_o_401(self, client):
        r = client.get("/pagos")
        assert r.status_code in (401, 403)

    def test_sin_token_patch_devuelve_403_o_401(self, client, db):
        eid = _crear_egreso(db)
        r = client.patch(f"/pagos/{eid}", json={"monto": 100})
        assert r.status_code in (401, 403)

    def test_sin_token_delete_devuelve_403_o_401(self, client, db):
        eid = _crear_egreso(db)
        r = client.delete(f"/pagos/{eid}")
        assert r.status_code in (401, 403)

    def test_token_invalido_devuelve_401_o_403(self, client):
        r = client.get("/pagos", headers={"Authorization": "Bearer token.falso.abc"})
        assert r.status_code in (401, 403)

    def test_operador_puede_listar(self, client, db):
        token = _token(db, "op@e2e.test")
        r = client.get("/pagos", headers=_auth(token))
        assert r.status_code == 200

    def test_operador_no_puede_eliminar(self, client, db):
        """Operador carece de delete_records → 403."""
        eid = _crear_egreso(db)
        token = _token(db, "op@e2e.test")
        r = client.delete(f"/pagos/{eid}", headers=_auth(token))
        assert r.status_code == 403

    def test_admin_puede_eliminar(self, client, db):
        eid = _crear_egreso(db)
        token = _token(db, "admin@e2e.test")
        r = client.delete(f"/pagos/{eid}", headers=_auth(token))
        assert r.status_code == 200


# ── GET /pagos ────────────────────────────────────────────────────────────────

class TestListarEgresos:

    def test_listar_devuelve_estructura_correcta(self, client, db):
        token = _token(db, "admin@e2e.test")
        r = client.get("/pagos", headers=_auth(token))
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert "total" in data

    def test_listar_incluye_egreso_creado(self, client, db):
        _crear_egreso(db, monto=750)
        token = _token(db, "admin@e2e.test")
        r = client.get("/pagos", headers=_auth(token))
        assert r.json()["total"] >= 1

    def test_filtro_tipo(self, client, db):
        _crear_egreso(db)
        token = _token(db, "admin@e2e.test")
        r = client.get("/pagos?tipo=proveedor", headers=_auth(token))
        assert r.status_code == 200
        for item in r.json()["items"]:
            assert item["tipo"] == "proveedor"


# ── POST /pagos ───────────────────────────────────────────────────────────────

class TestCrearEgreso:

    def test_crear_ok(self, client, db):
        token = _token(db, "admin@e2e.test")
        r = client.post("/pagos", headers=_auth(token), json={
            "tipo": "gasto",
            "forma_pago": "banco",
            "monto": 1500,
            "fecha": "2026-06-01",
            "beneficiario": "Proveedor ABC",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert data["egreso"]["monto"] == 1500.0
        assert data["egreso"]["beneficiario"] == "Proveedor ABC"
        assert "id" in data["egreso"]

    def test_crear_monto_cero_devuelve_400(self, client, db):
        token = _token(db, "admin@e2e.test")
        r = client.post("/pagos", headers=_auth(token), json={
            "tipo": "gasto", "forma_pago": "banco", "monto": 0,
        })
        assert r.status_code == 400

    def test_crear_monto_negativo_devuelve_400(self, client, db):
        token = _token(db, "admin@e2e.test")
        r = client.post("/pagos", headers=_auth(token), json={
            "tipo": "gasto", "forma_pago": "banco", "monto": -50,
        })
        assert r.status_code == 400

    def test_crear_tipo_invalido_devuelve_400(self, client, db):
        token = _token(db, "admin@e2e.test")
        r = client.post("/pagos", headers=_auth(token), json={
            "tipo": "invalido", "forma_pago": "banco", "monto": 100,
        })
        assert r.status_code == 400

    def test_operador_puede_crear(self, client, db):
        """Operador tiene 'reconcile' → puede crear."""
        token = _token(db, "op@e2e.test")
        r = client.post("/pagos", headers=_auth(token), json={
            "tipo": "gasto", "forma_pago": "banco", "monto": 200,
        })
        assert r.status_code == 200


# ── PATCH /pagos/{id} ────────────────────────────────────────────────────────

class TestEditarEgresoHTTP:

    def test_editar_monto_devuelve_200_y_valor_actualizado(self, client, db):
        eid = _crear_egreso(db, monto=1000)
        token = _token(db, "admin@e2e.test")

        r = client.patch(f"/pagos/{eid}", headers=_auth(token), json={"monto": 2500})

        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert data["egreso"]["monto"] == 2500.0
        assert data["egreso"]["id"] == eid

    def test_editar_beneficiario(self, client, db):
        eid = _crear_egreso(db)
        token = _token(db, "admin@e2e.test")

        r = client.patch(f"/pagos/{eid}", headers=_auth(token),
                         json={"beneficiario": "Nuevo Proveedor"})

        assert r.status_code == 200
        assert r.json()["egreso"]["beneficiario"] == "Nuevo Proveedor"

    def test_editar_multiples_campos(self, client, db):
        eid = _crear_egreso(db, monto=500)
        token = _token(db, "admin@e2e.test")

        r = client.patch(f"/pagos/{eid}", headers=_auth(token), json={
            "monto": 750,
            "fecha": "2026-05-20",
            "concepto": "Factura corregida",
            "referencia": "REF-001",
        })

        assert r.status_code == 200
        egreso = r.json()["egreso"]
        assert egreso["monto"] == 750.0
        assert egreso["fecha"] == "2026-05-20"
        assert egreso["concepto"] == "Factura corregida"
        assert egreso["referencia"] == "REF-001"

    def test_editar_monto_cero_devuelve_400(self, client, db):
        eid = _crear_egreso(db)
        token = _token(db, "admin@e2e.test")

        r = client.patch(f"/pagos/{eid}", headers=_auth(token), json={"monto": 0})

        assert r.status_code == 400

    def test_editar_monto_negativo_devuelve_400(self, client, db):
        eid = _crear_egreso(db)
        token = _token(db, "admin@e2e.test")

        r = client.patch(f"/pagos/{eid}", headers=_auth(token), json={"monto": -1})

        assert r.status_code == 400

    def test_editar_fecha_invalida_devuelve_400(self, client, db):
        eid = _crear_egreso(db)
        token = _token(db, "admin@e2e.test")

        r = client.patch(f"/pagos/{eid}", headers=_auth(token), json={"fecha": "no-es-fecha"})

        assert r.status_code == 400

    def test_editar_inexistente_devuelve_404(self, client, db):
        token = _token(db, "admin@e2e.test")

        r = client.patch("/pagos/99999", headers=_auth(token), json={"monto": 100})

        assert r.status_code == 404

    def test_operador_puede_editar(self, client, db):
        """Operador tiene 'reconcile' → puede editar."""
        eid = _crear_egreso(db)
        token = _token(db, "op@e2e.test")

        r = client.patch(f"/pagos/{eid}", headers=_auth(token), json={"monto": 800})

        assert r.status_code == 200

    def test_patch_persiste_en_db(self, client, db):
        """Verifica que el cambio se persiste, no solo se retorna en el response."""
        eid = _crear_egreso(db, monto=100)
        token = _token(db, "admin@e2e.test")

        client.patch(f"/pagos/{eid}", headers=_auth(token), json={"monto": 999})

        db.expire_all()
        e = db.query(Egreso).filter(Egreso.id == eid).first()
        assert float(e.monto) == 999.0


# ── DELETE /pagos/{id} ───────────────────────────────────────────────────────

class TestEliminarEgresoHTTP:

    def test_eliminar_devuelve_200_y_ok(self, client, db):
        eid = _crear_egreso(db)
        token = _token(db, "admin@e2e.test")

        r = client.delete(f"/pagos/{eid}", headers=_auth(token))

        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert data["egreso_id"] == eid

    def test_eliminar_borra_de_db(self, client, db):
        eid = _crear_egreso(db)
        token = _token(db, "admin@e2e.test")

        client.delete(f"/pagos/{eid}", headers=_auth(token))

        db.expire_all()
        assert db.query(Egreso).filter(Egreso.id == eid).first() is None

    def test_eliminar_inexistente_devuelve_404(self, client, db):
        token = _token(db, "admin@e2e.test")

        r = client.delete("/pagos/99999", headers=_auth(token))

        assert r.status_code == 404

    def test_operador_sin_delete_records_devuelve_403(self, client, db):
        eid = _crear_egreso(db)
        token = _token(db, "op@e2e.test")

        r = client.delete(f"/pagos/{eid}", headers=_auth(token))

        assert r.status_code == 403
        # El egreso no fue borrado
        assert db.query(Egreso).filter(Egreso.id == eid).first() is not None

    def test_eliminar_segunda_vez_devuelve_404(self, client, db):
        eid = _crear_egreso(db)
        token = _token(db, "admin@e2e.test")

        client.delete(f"/pagos/{eid}", headers=_auth(token))
        r = client.delete(f"/pagos/{eid}", headers=_auth(token))

        assert r.status_code == 404


# ── Regresión: routing ───────────────────────────────────────────────────────

class TestRoutingRegresion:
    """Tests de regresión que habrían detectado el bug del @router.delete faltante."""

    def test_ruta_delete_registrada(self):
        """@router.delete('/{egreso_id}') debe estar declarado en el router."""
        from app.routers.pagos import router
        rutas_delete = [
            r for r in router.routes
            if hasattr(r, "methods") and "DELETE" in r.methods
        ]
        assert len(rutas_delete) >= 1, (
            "No existe ninguna ruta DELETE en el router de pagos — "
            "el decorador @router.delete faltaba y no fue corregido"
        )
        paths = [r.path for r in rutas_delete]
        assert any("{" in p for p in paths), (
            f"Ruta DELETE encontrada pero sin path variable: {paths}"
        )

    def test_ruta_patch_registrada(self):
        """@router.patch('/{egreso_id}') debe estar declarado en el router."""
        from app.routers.pagos import router
        rutas_patch = [
            r for r in router.routes
            if hasattr(r, "methods") and "PATCH" in r.methods
        ]
        assert len(rutas_patch) >= 1, "No existe ninguna ruta PATCH en el router de pagos"

    def test_delete_responde_200_no_404_de_routing(self, client, db):
        """
        Regresión directa: antes del fix, DELETE /pagos/1 devolvía 404 porque
        el decorador @router.delete faltaba (el handler existía como función
        Python pero no estaba registrado como ruta HTTP). Este test lo verifica
        haciendo una llamada HTTP real — algo que los tests unitarios directos
        no pueden detectar.
        """
        eid = _crear_egreso(db)
        token = _token(db, "admin@e2e.test")

        r = client.delete(f"/pagos/{eid}", headers=_auth(token))

        # 404 de routing (ruta no registrada) vs 200 de éxito
        # Si el decorador faltara, FastAPI devolvería 404 — mismo código que
        # "egreso no encontrado", pero con detail distinto.
        assert r.status_code == 200, (
            f"Esperado 200. ¿Falta @router.delete? Detail: {r.json()}"
        )


# ── Flujo E2E completo ────────────────────────────────────────────────────────

class TestFlujoCompleto:

    def test_crear_editar_verificar_eliminar(self, client, db):
        """
        Ciclo CRUD completo via HTTP:
          1. Crear egreso  → POST /pagos
          2. Verificar     → GET /pagos
          3. Editar monto  → PATCH /pagos/{id}
          4. Verificar     → GET /pagos/{id} implícito via listado
          5. Eliminar      → DELETE /pagos/{id}
          6. Confirmar     → egreso ya no aparece en listado
        """
        token = _token(db, "admin@e2e.test")
        h = _auth(token)

        # 1. Crear
        r = client.post("/pagos", headers=h, json={
            "tipo": "proveedor",
            "forma_pago": "banco",
            "monto": 1000,
            "fecha": "2026-06-01",
            "beneficiario": "Proveedor XYZ",
            "concepto": "Factura junio",
        })
        assert r.status_code == 200
        eid = r.json()["egreso"]["id"]

        # 2. Verificar en listado
        r = client.get("/pagos", headers=h)
        ids = [item["id"] for item in r.json()["items"]]
        assert eid in ids

        # 3. Editar monto
        r = client.patch(f"/pagos/{eid}", headers=h, json={
            "monto": 1200,
            "concepto": "Factura junio (revisada)",
        })
        assert r.status_code == 200
        assert r.json()["egreso"]["monto"] == 1200.0

        # 4. Confirmar en DB
        db.expire_all()
        e = db.query(Egreso).filter(Egreso.id == eid).first()
        assert float(e.monto) == 1200.0
        assert e.concepto == "Factura junio (revisada)"

        # 5. Eliminar
        r = client.delete(f"/pagos/{eid}", headers=h)
        assert r.status_code == 200

        # 6. Confirmar borrado en listado
        r = client.get("/pagos", headers=h)
        ids = [item["id"] for item in r.json()["items"]]
        assert eid not in ids
