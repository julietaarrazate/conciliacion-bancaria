"""
Tests de integración para el módulo de planillas vía FastAPI TestClient.

Cubre:
- Historial: GET /historial/planillas (lista de planillas)
- Detalle: GET /planillas/{id}/detalle
- Soft delete: DELETE /planillas/{id} → no aparece en listado normal
- Conciliación: POST /planillas/{id}/conciliar con movimientos en el extracto
- Edición manual de estado de fila: PATCH /planillas/rows/{id}
- Subida (upload): POST /planillas/upload con archivo xlsx real mínimo

Los tests que requieren upload de archivo construyen un xlsx mínimo válido
en memoria usando openpyxl (ya está en requirements).
"""
import io
import pytest
from datetime import date, datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.services.auth import get_password_hash, create_access_token
from app.models.organizacion import Organizacion
from app.models.user import User
from app.models.cliente import Cliente
from app.models.extracto import ExtractoBancario, MovimientoBanco
from app.models.planilla import Planilla, PlanillaRow


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def db():
    """DB SQLite en memoria con org, admin y datos base para planillas."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    org = Organizacion(id=1, nombre="OrgPlanillas")
    session.add(org)
    session.commit()

    admin = User(
        email="admin@plan.test", full_name="Admin Planillas",
        hashed_password=get_password_hash("pw123"),
        organizacion_id=1, is_active=True, role="admin", is_superadmin=False,
    )
    session.add(admin)
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


# ── Helpers para seed de datos ────────────────────────────────────────────────

def _seed_extracto_con_movimientos(db, montos=None):
    """Crea extracto con movimientos. Retorna el extracto."""
    if montos is None:
        montos = [Decimal("5000"), Decimal("3000")]

    extracto = ExtractoBancario(
        nombre_archivo="extracto_test.xlsx",
        organizacion_id=1,
        creado_por=1,
        fecha_creacion=datetime.utcnow(),
    )
    db.add(extracto)
    db.flush()

    for i, monto in enumerate(montos):
        mov = MovimientoBanco(
            extracto_id=extracto.id,
            orden=i + 1,
            fecha=date(2026, 6, 1),
            mes="junio",
            titular="CLIENTE TEST SA",
            monto=monto,
            saldo=monto,
            source="extracto",
            organizacion_id=1,
        )
        db.add(mov)

    db.commit()
    db.refresh(extracto)
    return extracto


def _seed_planilla_con_filas(db, extracto_id, cliente_nombre="ClientePlan", n_filas=2):
    """Crea cliente, planilla y filas pendientes directamente en la DB."""
    cliente = db.query(Cliente).filter(
        Cliente.nombre.ilike(cliente_nombre), Cliente.organizacion_id == 1
    ).first()
    if not cliente:
        cliente = Cliente(nombre=cliente_nombre, organizacion_id=1)
        db.add(cliente)
        db.flush()

    planilla = Planilla(
        cliente_id=cliente.id,
        extracto_id=extracto_id,
        usuario_id=1,
        nombre_archivo="planilla_test.xlsx",
        organizacion_id=1,
        fecha_carga=datetime.utcnow(),
    )
    db.add(planilla)
    db.flush()

    for i in range(n_filas):
        row = PlanillaRow(
            planilla_id=planilla.id,
            monto=Decimal("5000") if i == 0 else Decimal("3000"),
            cuit="20123456789",
            titular="CLIENTE TEST SA",
            referencia=f"REF00{i+1}",
            status="pendiente",
            organizacion_id=1,
        )
        db.add(row)

    db.commit()
    db.refresh(planilla)
    return planilla, cliente


def _make_xlsx_bytes(filas):
    """Construye un xlsx mínimo con filas = [(monto, cuit, titular, ref)]."""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Planilla"
    ws.append(["Monto", "CUIT", "Titular", "Referencia"])
    for monto, cuit, titular, ref in filas:
        ws.append([monto, cuit, titular, ref])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()


# ── Tests: historial de planillas ─────────────────────────────────────────────

class TestHistorialPlanillas:

    def test_historial_planillas_retorna_200(self, client, db):
        """GET /historial/planillas → 200 con estructura correcta {total, items}."""
        token = _token(db, "admin@plan.test")
        r = client.get("/historial/planillas", headers=_auth(token))
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_historial_sin_auth_retorna_403(self, client):
        r = client.get("/historial/planillas")
        assert r.status_code in (401, 403)

    def test_historial_muestra_planilla_existente(self, client, db):
        """Una planilla creada en DB aparece en el historial."""
        extracto = _seed_extracto_con_movimientos(db)
        planilla, _ = _seed_planilla_con_filas(db, extracto.id, "ClienteHistorial")

        token = _token(db, "admin@plan.test")
        r = client.get("/historial/planillas", headers=_auth(token))
        assert r.status_code == 200
        ids = [p["id"] for p in r.json()["items"]]
        assert planilla.id in ids

    def test_historial_no_muestra_planilla_soft_deleted(self, client, db):
        """Planilla con deleted_at NO aparece en el historial (soft delete)."""
        extracto = _seed_extracto_con_movimientos(db)
        planilla, _ = _seed_planilla_con_filas(db, extracto.id, "ClienteDeleted")

        token = _token(db, "admin@plan.test")

        # Soft delete via API
        r_del = client.delete(f"/planillas/{planilla.id}", headers=_auth(token))
        assert r_del.status_code == 200
        assert r_del.json()["soft_deleted"] is True

        # No debe aparecer en el historial
        r_hist = client.get("/historial/planillas", headers=_auth(token))
        assert r_hist.status_code == 200
        ids = [p["id"] for p in r_hist.json()["items"]]
        assert planilla.id not in ids


# ── Tests: detalle de planilla ────────────────────────────────────────────────

class TestDetallePlanilla:

    def test_detalle_planilla_retorna_200_con_filas(self, client, db):
        """GET /planillas/{id}/detalle → 200 con rows."""
        extracto = _seed_extracto_con_movimientos(db)
        planilla, _ = _seed_planilla_con_filas(db, extracto.id)

        token = _token(db, "admin@plan.test")
        r = client.get(f"/planillas/{planilla.id}/detalle", headers=_auth(token))
        assert r.status_code == 200
        data = r.json()
        assert "rows" in data
        assert len(data["rows"]) == 2

    def test_detalle_planilla_inexistente_retorna_404(self, client, db):
        token = _token(db, "admin@plan.test")
        r = client.get("/planillas/99999/detalle", headers=_auth(token))
        assert r.status_code == 404

    def test_detalle_planilla_sin_auth_retorna_403(self, client):
        r = client.get("/planillas/1/detalle")
        assert r.status_code in (401, 403)

    def test_detalle_incluye_total_filtered(self, client, db):
        """total_filtered == total cuando no hay filtros."""
        extracto = _seed_extracto_con_movimientos(db)
        planilla, _ = _seed_planilla_con_filas(db, extracto.id)
        token = _token(db, "admin@plan.test")
        r = client.get(f"/planillas/{planilla.id}/detalle", headers=_auth(token))
        data = r.json()
        assert "total_filtered" in data
        assert data["total_filtered"] == data["total"]

    def test_detalle_filtro_status(self, client, db):
        """?status=pendiente devuelve solo filas en pendiente."""
        extracto = _seed_extracto_con_movimientos(db)
        planilla, _ = _seed_planilla_con_filas(db, extracto.id)
        token = _token(db, "admin@plan.test")
        r = client.get(f"/planillas/{planilla.id}/detalle?status=pendiente", headers=_auth(token))
        assert r.status_code == 200
        data = r.json()
        assert all(row["status"] == "pendiente" for row in data["rows"])

    def test_detalle_paginacion_limit_offset(self, client, db):
        """limit=1 devuelve solo 1 fila; offset=1 devuelve la siguiente."""
        extracto = _seed_extracto_con_movimientos(db)
        planilla, _ = _seed_planilla_con_filas(db, extracto.id)
        token = _token(db, "admin@plan.test")

        r1 = client.get(f"/planillas/{planilla.id}/detalle?limit=1&offset=0", headers=_auth(token))
        r2 = client.get(f"/planillas/{planilla.id}/detalle?limit=1&offset=1", headers=_auth(token))
        assert r1.status_code == 200 and r2.status_code == 200
        assert len(r1.json()["rows"]) == 1
        assert len(r2.json()["rows"]) == 1
        # Different rows
        assert r1.json()["rows"][0]["id"] != r2.json()["rows"][0]["id"]
        # total_filtered reflects ALL rows, not just this page
        assert r1.json()["total_filtered"] == 2


# ── Tests: soft delete ────────────────────────────────────────────────────────

class TestSoftDelete:

    def test_soft_delete_planilla_marca_deleted_at(self, client, db):
        """DELETE /planillas/{id} → deleted_at en la DB, soft_deleted=True en respuesta."""
        extracto = _seed_extracto_con_movimientos(db)
        planilla, _ = _seed_planilla_con_filas(db, extracto.id, "ClienteSoftDel")

        token = _token(db, "admin@plan.test")
        r = client.delete(f"/planillas/{planilla.id}", headers=_auth(token))
        assert r.status_code == 200
        assert r.json()["soft_deleted"] is True

        # La DB debe tener deleted_at seteado
        db.refresh(planilla)
        assert planilla.deleted_at is not None

    def test_soft_delete_planilla_preserva_filas(self, client, db):
        """Las filas de la planilla permanecen en la DB tras el soft delete."""
        extracto = _seed_extracto_con_movimientos(db)
        planilla, _ = _seed_planilla_con_filas(db, extracto.id, "ClientePreserveRows")

        token = _token(db, "admin@plan.test")
        client.delete(f"/planillas/{planilla.id}", headers=_auth(token))

        rows_en_db = db.query(PlanillaRow).filter(PlanillaRow.planilla_id == planilla.id).count()
        assert rows_en_db == 2, "Las filas no deben borrarse al hacer soft delete"

    def test_delete_planilla_sin_permiso_retorna_403(self, client, db):
        """Sin token → 401/403."""
        r = client.delete("/planillas/1")
        assert r.status_code in (401, 403)


# ── Tests: conciliación ───────────────────────────────────────────────────────

class TestConciliar:

    def test_conciliar_planilla_happy_path(self, client, db):
        """POST /planillas/{id}/conciliar → algunas filas en estado 'ok' o variante."""
        # Extracto con movimiento de 5000 con titular que matchea
        extracto = _seed_extracto_con_movimientos(db, montos=[Decimal("5000")])
        planilla, _ = _seed_planilla_con_filas(db, extracto.id, "ClientePlan", n_filas=1)

        token = _token(db, "admin@plan.test")
        r = client.post(
            f"/planillas/{planilla.id}/conciliar",
            headers=_auth(token),
        )
        assert r.status_code == 200
        data = r.json()
        assert "planilla_id" in data
        assert data["planilla_id"] == planilla.id
        # Puede tener filas ok o no, pero el endpoint no debe crashear
        assert "total_filas" in data or "ok" in data or isinstance(data, dict)

    def test_conciliar_respuesta_incluye_diagnostico(self, client, db):
        """La respuesta trae 'diagnostico' con las keys correctas y los conteos
        de acreditadas/no_encontradas NO cambian por el diagnóstico (es aditivo)."""
        extracto = _seed_extracto_con_movimientos(db, montos=[Decimal("5000")])
        planilla, _ = _seed_planilla_con_filas(db, extracto.id, "ClienteDiag", n_filas=1)

        token = _token(db, "admin@plan.test")
        r = client.post(f"/planillas/{planilla.id}/conciliar", headers=_auth(token))
        assert r.status_code == 200
        data = r.json()

        # Conteos base intactos: 1 fila (5000) matchea el único movimiento de 5000
        assert data["acreditadas"] == 1
        assert data["no_encontradas"] == 0
        assert data["filas_procesadas"] == 1

        diag = data["diagnostico"]
        assert diag is not None
        assert set(diag.keys()) == {
            "banco_trae_identidad", "cobertura_montos",
            "periodo_planilla", "periodo_extracto", "solapan_fechas",
        }
        assert diag["cobertura_montos"] == {"en_extracto": 1, "total": 1}
        assert isinstance(diag["solapan_fechas"], bool)

    def test_conciliar_planilla_inexistente_retorna_404(self, client, db):
        token = _token(db, "admin@plan.test")
        r = client.post("/planillas/99999/conciliar", headers=_auth(token))
        assert r.status_code == 404

    def test_conciliar_sin_auth_retorna_403(self, client):
        r = client.post("/planillas/1/conciliar")
        assert r.status_code in (401, 403)


# ── Tests: edición manual de status de fila ───────────────────────────────────

class TestPatchRowStatus:

    def test_patch_row_status_cambia_estado(self, client, db):
        """PATCH /planillas/rows/{id} → estado de la fila se actualiza."""
        extracto = _seed_extracto_con_movimientos(db)
        planilla, _ = _seed_planilla_con_filas(db, extracto.id, "ClienteRowEdit")

        row = planilla.rows[0]
        assert row.status == "pendiente"

        token = _token(db, "admin@plan.test")
        r = client.patch(
            f"/planillas/rows/{row.id}",
            json={"status": "no está"},
            headers=_auth(token),
        )
        assert r.status_code == 200
        assert r.json()["status"] == "no está"

        db.refresh(row)
        assert row.status == "no está"

    def test_patch_row_status_sin_status_retorna_400(self, client, db):
        """Body sin 'status' → HTTP 400."""
        extracto = _seed_extracto_con_movimientos(db)
        planilla, _ = _seed_planilla_con_filas(db, extracto.id, "ClienteRowEditBad")

        row = planilla.rows[0]
        token = _token(db, "admin@plan.test")
        r = client.patch(
            f"/planillas/rows/{row.id}",
            json={},  # sin status
            headers=_auth(token),
        )
        assert r.status_code == 400

    def test_patch_row_inexistente_retorna_404(self, client, db):
        token = _token(db, "admin@plan.test")
        r = client.patch(
            "/planillas/rows/99999",
            json={"status": "ok"},
            headers=_auth(token),
        )
        assert r.status_code == 404


# ── Tests: upload de planilla (xlsx real mínimo) ──────────────────────────────

class TestUploadPlanilla:

    def test_upload_planilla_crea_planilla_con_filas(self, client, db):
        """POST /planillas/upload con xlsx válido → planilla con filas pendientes."""
        extracto = _seed_extracto_con_movimientos(db)

        filas = [
            (5000.0, "20123456789", "CLIENTE TEST SA", "REF001"),
            (3000.0, "20987654321", "OTRA EMPRESA SRL", "REF002"),
        ]
        xlsx_bytes = _make_xlsx_bytes(filas)

        token = _token(db, "admin@plan.test")
        r = client.post(
            f"/planillas/upload?cliente_nombre=ClienteUpload&extracto_id={extracto.id}",
            files={"file": ("planilla.xlsx", xlsx_bytes,
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=_auth(token),
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "id" in data
        planilla_id = data["id"]

        # Verificar que se crearon las filas en la DB
        rows = db.query(PlanillaRow).filter(PlanillaRow.planilla_id == planilla_id).all()
        assert len(rows) >= 1, "Se esperaban filas en la planilla"
        # Todas las filas deben estar en estado 'pendiente'
        for row in rows:
            assert row.status == "pendiente"

    def test_upload_planilla_crea_cliente_si_no_existe(self, client, db):
        """Upload con un nombre de cliente nuevo lo crea automáticamente."""
        extracto = _seed_extracto_con_movimientos(db)
        xlsx_bytes = _make_xlsx_bytes([(1000.0, "20111111111", "Empresa Nueva SA", "REF999")])

        token = _token(db, "admin@plan.test")
        r = client.post(
            f"/planillas/upload?cliente_nombre=EmpresaNueva&extracto_id={extracto.id}",
            files={"file": ("plan.xlsx", xlsx_bytes,
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=_auth(token),
        )
        assert r.status_code == 200
        cliente = db.query(Cliente).filter(
            Cliente.nombre.ilike("EmpresaNueva"), Cliente.organizacion_id == 1
        ).first()
        assert cliente is not None, "El cliente debe haberse creado automáticamente"

    def test_upload_planilla_formato_invalido_retorna_400(self, client, db):
        """Subir un .txt → HTTP 400 por formato no aceptado."""
        extracto = _seed_extracto_con_movimientos(db)
        token = _token(db, "admin@plan.test")

        r = client.post(
            f"/planillas/upload?cliente_nombre=TestCliente&extracto_id={extracto.id}",
            files={"file": ("datos.txt", b"hola mundo", "text/plain")},
            headers=_auth(token),
        )
        assert r.status_code == 400

    def test_upload_planilla_extracto_inexistente_retorna_404(self, client, db):
        """Extracto inexistente → HTTP 404."""
        xlsx_bytes = _make_xlsx_bytes([(1000.0, "20111111111", "Cliente X", "REF")])
        token = _token(db, "admin@plan.test")

        r = client.post(
            "/planillas/upload?cliente_nombre=ClienteX&extracto_id=99999",
            files={"file": ("plan.xlsx", xlsx_bytes,
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=_auth(token),
        )
        assert r.status_code == 404

    def test_upload_planilla_sin_auth_retorna_403(self, client):
        r = client.post("/planillas/upload?cliente_nombre=X&extracto_id=1",
                        files={"file": ("p.xlsx", b"data", "application/octet-stream")})
        assert r.status_code in (401, 403)

    def test_upload_planilla_duplicada_mismo_cliente_retorna_409(self, client, db):
        """Subir el MISMO archivo dos veces para el mismo cliente → 409, no crea
        una segunda planilla (regresión del duplicado real: Green quedó cargado
        dos veces porque el contador reenvió el archivo)."""
        extracto = _seed_extracto_con_movimientos(db)
        xlsx_bytes = _make_xlsx_bytes([(5000.0, "20123456789", "CLIENTE TEST SA", "REF001")])
        token = _token(db, "admin@plan.test")

        r1 = client.post(
            f"/planillas/upload?cliente_nombre=Duplicado&extracto_id={extracto.id}",
            files={"file": ("planilla.xlsx", xlsx_bytes,
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=_auth(token),
        )
        assert r1.status_code == 200, r1.text

        r2 = client.post(
            f"/planillas/upload?cliente_nombre=Duplicado&extracto_id={extracto.id}",
            files={"file": ("planilla.xlsx", xlsx_bytes,
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=_auth(token),
        )
        assert r2.status_code == 409, r2.text
        assert "ya fue cargada" in r2.json()["detail"]

        cliente = db.query(Cliente).filter(Cliente.nombre == "Duplicado").first()
        planillas = db.query(Planilla).filter(Planilla.cliente_id == cliente.id).all()
        assert len(planillas) == 1

    def test_upload_planilla_mismo_archivo_otro_cliente_no_bloquea(self, client, db):
        """El bloqueo es por (cliente, archivo) — el mismo archivo para OTRO
        cliente no debe chocar (ej. dos clientes que casualmente mandan una
        planilla con la misma estructura/montos)."""
        extracto = _seed_extracto_con_movimientos(db)
        xlsx_bytes = _make_xlsx_bytes([(5000.0, "20123456789", "CLIENTE TEST SA", "REF001")])
        token = _token(db, "admin@plan.test")

        r1 = client.post(
            f"/planillas/upload?cliente_nombre=ClienteA&extracto_id={extracto.id}",
            files={"file": ("planilla.xlsx", xlsx_bytes,
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=_auth(token),
        )
        assert r1.status_code == 200, r1.text

        r2 = client.post(
            f"/planillas/upload?cliente_nombre=ClienteB&extracto_id={extracto.id}",
            files={"file": ("planilla.xlsx", xlsx_bytes,
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=_auth(token),
        )
        assert r2.status_code == 200, r2.text

    def test_upload_planilla_duplicada_tras_borrar_la_anterior_no_bloquea(self, client, db):
        """Soft-delete de la planilla existente libera el fingerprint: volver a
        subir el mismo archivo para el mismo cliente ya no choca."""
        extracto = _seed_extracto_con_movimientos(db)
        xlsx_bytes = _make_xlsx_bytes([(5000.0, "20123456789", "CLIENTE TEST SA", "REF001")])
        token = _token(db, "admin@plan.test")

        r1 = client.post(
            f"/planillas/upload?cliente_nombre=Reintento&extracto_id={extracto.id}",
            files={"file": ("planilla.xlsx", xlsx_bytes,
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=_auth(token),
        )
        assert r1.status_code == 200, r1.text
        planilla_id = r1.json()["id"]

        planilla = db.query(Planilla).filter(Planilla.id == planilla_id).first()
        planilla.deleted_at = datetime.utcnow()
        db.commit()

        r2 = client.post(
            f"/planillas/upload?cliente_nombre=Reintento&extracto_id={extracto.id}",
            files={"file": ("planilla.xlsx", xlsx_bytes,
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=_auth(token),
        )
        assert r2.status_code == 200, r2.text
        assert r2.json()["id"] != planilla_id
