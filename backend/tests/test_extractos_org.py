"""
Regresión: el upload de extracto/planilla ignoraba la organización activa
seleccionada por el usuario (siempre usaba current_user.organizacion_id o el
default=1 del modelo). Esto causaba dos bugs reales reportados:

1. El archivo se guardaba siempre en la org "home" del usuario, nunca en la
   org que el superadmin tenía seleccionada en el selector (ej. "prueba").
2. Si el mismo archivo se subía dos veces apuntando a orgs distintas, ambas
   filas terminaban con organizacion_id=1 (default), violando el unique index
   (fingerprint, organizacion_id) de la migración 006 y devolviendo un 400
   genérico ("Error al procesar el archivo...") en vez de guardarse en la org
   correcta.

Fix: ambos endpoints aceptan `org_id` (igual que el resto de la API),
validado con `can_switch_org`, y lo usan para el dedupe + para asignar
organizacion_id explícitamente en el insert.
"""
import io
import openpyxl
import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.services.auth import get_password_hash, create_access_token
from app.models.organizacion import Organizacion
from app.models.user import User
from app.models.extracto import ExtractoBancario


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

    session.add(Organizacion(id=1, nombre="Principal"))
    session.add(Organizacion(id=2, nombre="Prueba"))
    session.commit()

    superadmin = User(
        email="super@org.test", full_name="Superadmin",
        hashed_password=get_password_hash("pw123"),
        organizacion_id=1, is_active=True, role="admin", is_superadmin=True,
    )
    contador = User(
        email="contador@org.test", full_name="Contador",
        hashed_password=get_password_hash("pw123"),
        organizacion_id=1, is_active=True, role="admin", is_superadmin=False,
        allowed_org_ids=[],
    )
    session.add_all([superadmin, contador])
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


def _xlsx_bytes(filas):
    """parsear_extracto_bancario ignora hojas con menos de 3 filas (ws.max_row < 3),
    así que siempre incluye al menos 2 filas de datos además del header."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Fecha", "Titular", "Monto", "Saldo"])
    for fecha, titular, monto, saldo in filas:
        ws.append([fecha, titular, monto, saldo])
    if len(filas) < 2:
        ws.append(["2026-06-02", "Relleno", 1, 1])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()


class TestUploadExtractoOrg:

    def test_superadmin_sube_a_org_seleccionada(self, client, db):
        """org_id=2 ("prueba") en el upload → el extracto queda en esa org, no en la home (1)."""
        token = _token(db, "super@org.test")
        xlsx = _xlsx_bytes([("2026-06-01", "Cliente Test", 5000, 5000)])
        r = client.post(
            "/extractos/upload?org_id=2",
            files={"file": ("extracto.xlsx", xlsx,
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=_auth(token),
        )
        assert r.status_code == 200, r.text
        extracto = db.query(ExtractoBancario).filter(ExtractoBancario.id == r.json()["id"]).first()
        assert extracto.organizacion_id == 2

    def test_mismo_archivo_en_dos_orgs_no_rompe_unique_constraint(self, client, db):
        """Subir el mismo xlsx a la org 1 y después a la org 2 no debe tirar el
        error genérico de "procesar el archivo" (regresión: antes ambos
        insertaban con organizacion_id=1 y violaban el unique index)."""
        token = _token(db, "super@org.test")
        xlsx = _xlsx_bytes([("2026-06-01", "Cliente Test", 5000, 5000)])

        r1 = client.post(
            "/extractos/upload?org_id=1",
            files={"file": ("extracto.xlsx", xlsx,
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=_auth(token),
        )
        assert r1.status_code == 200, r1.text

        r2 = client.post(
            "/extractos/upload?org_id=2",
            files={"file": ("extracto.xlsx", xlsx,
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=_auth(token),
        )
        assert r2.status_code == 200, r2.text
        assert r1.json()["id"] != r2.json()["id"]

        orgs = {
            db.query(ExtractoBancario).filter(ExtractoBancario.id == r1.json()["id"]).first().organizacion_id,
            db.query(ExtractoBancario).filter(ExtractoBancario.id == r2.json()["id"]).first().organizacion_id,
        }
        assert orgs == {1, 2}

    def test_usuario_sin_permiso_no_puede_forzar_otra_org(self, client, db):
        """Un usuario no-superadmin sin esa org en allowed_org_ids no puede
        subir a org_id=2 — cae a su propia org (1), no a la solicitada."""
        token = _token(db, "contador@org.test")
        xlsx = _xlsx_bytes([("2026-06-01", "Cliente Test", 5000, 5000)])
        r = client.post(
            "/extractos/upload?org_id=2",
            files={"file": ("extracto.xlsx", xlsx,
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=_auth(token),
        )
        assert r.status_code == 200, r.text
        extracto = db.query(ExtractoBancario).filter(ExtractoBancario.id == r.json()["id"]).first()
        assert extracto.organizacion_id == 1
