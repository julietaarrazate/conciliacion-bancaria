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
from app.models.extracto import ExtractoBancario, MovimientoBanco


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


@pytest.fixture(autouse=True)
def _sin_rate_limit():
    # Varios tests suben más de 10 extractos/min; el rate limit (10/min) es de
    # producción, no relevante acá. Se desactiva durante los tests.
    from app.routers import extractos as _ext
    prev = _ext.limiter.enabled
    _ext.limiter.enabled = False
    yield
    _ext.limiter.enabled = prev


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

    def test_orden_arranca_en_1_por_extracto(self, client, db):
        """Cada extracto numera desde 1, sin importar la org ni cuántos extractos
        ya existan (regresión: el orden continuaba la numeración global de Banco
        Macro en vez de arrancar nuevo)."""
        MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        token = _token(db, "super@org.test")

        def subir(org, filas, nombre):
            return client.post(f"/extractos/upload?org_id={org}",
                               files={"file": (nombre, _xlsx_bytes(filas), MIME)}, headers=_auth(token))

        def ordenes(extracto_id):
            return sorted(m.orden for m in db.query(MovimientoBanco)
                          .filter(MovimientoBanco.extracto_id == extracto_id).all())

        # Org 1 con movimientos
        subir(1, [("2026-06-01", "M1", 1000, 1000), ("2026-06-02", "M2", 2000, 2000)], "macro.xlsx")
        # Org 2, extracto distinto → arranca en 1 (no continúa desde org 1)
        r2 = subir(2, [("2026-06-03", "C1", 3000, 3000), ("2026-06-04", "C2", 4000, 4000)], "comercio.xlsx")
        assert r2.status_code == 200, r2.text
        assert ordenes(r2.json()["id"]) == [1, 2]
        # SEGUNDO extracto distinto en la MISMA org 2 → también arranca en 1 (per-extracto)
        r3 = subir(2, [("2026-07-01", "C3", 7000, 7000), ("2026-07-02", "C4", 8000, 8000)], "comercio2.xlsx")
        assert r3.status_code == 200, r3.text
        assert ordenes(r3.json()["id"]) == [1, 2], "el 2do extracto de la org debe arrancar en 1"

    def test_listado_de_extractos_aislado_por_org(self, client, db):
        """GET /extractos?org_id=N devuelve SOLO los extractos de esa org, incluso
        para un superadmin (regresión: el front pedía sin org_id y un superadmin
        veía extractos de otras empresas — fuga de tenant)."""
        token = _token(db, "super@org.test")
        xlsx = _xlsx_bytes([("2026-06-01", "X", 1000, 1000)])

        client.post("/extractos/upload?org_id=1",
                    files={"file": ("a.xlsx", xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                    headers=_auth(token))
        client.post("/extractos/upload?org_id=2",
                    files={"file": ("b.xlsx", xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                    headers=_auth(token))

        r = client.get("/extractos?org_id=2", headers=_auth(token))
        assert r.status_code == 200, r.text
        ids = {e["id"] for e in r.json()["items"]}
        orgs = {
            db.query(ExtractoBancario).filter(ExtractoBancario.id == i).first().organizacion_id
            for i in ids
        }
        assert orgs == {2}, f"el listado de la org 2 trajo extractos de orgs {orgs}"

    def test_resubir_mismo_archivo_tras_borrar_crea_uno_nuevo(self, client, db):
        """Subir un extracto, borrarlo (soft delete) y re-subir el MISMO archivo
        crea uno NUEVO y limpio (numerado desde 1), no resucita la fila borrada.
        Antes caía con 400 'Error al procesar el archivo' por una resta
        Decimal - float en la rama de upsert que matcheaba la fila borrada."""
        token = _token(db, "super@org.test")
        # saldos con decimales → Numeric(12,2) llega como Decimal a la rama de upsert
        xlsx = _xlsx_bytes([("2026-06-01", "Cli A", 5000, 12345.67),
                            ("2026-06-02", "Cli B", 6000, 18345.67)])
        f = {"file": ("e.xlsx", xlsx,
                      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}

        r1 = client.post("/extractos/upload?org_id=2", files=f, headers=_auth(token))
        assert r1.status_code == 200, r1.text
        eid1 = r1.json()["id"]

        assert client.delete(f"/extractos/{eid1}?org_id=2", headers=_auth(token)).status_code == 200

        r2 = client.post("/extractos/upload?org_id=2", files=f, headers=_auth(token))
        assert r2.status_code == 200, r2.text  # antes: 400 "Error al procesar el archivo"
        eid2 = r2.json()["id"]
        assert eid2 != eid1, "re-subir tras borrar debe crear un extracto nuevo"

        # el nuevo aparece activo, el borrado no
        ids = {e["id"] for e in client.get("/extractos?org_id=2", headers=_auth(token)).json()["items"]}
        assert eid2 in ids and eid1 not in ids
        # numerado desde 1 (per-extracto)
        ordenes = sorted(m.orden for m in db.query(MovimientoBanco).filter(MovimientoBanco.extracto_id == eid2).all())
        assert ordenes == [1, 2], f"esperaba [1, 2], obtuve {ordenes}"

    def test_listar_movimientos_default_acota_a_100(self, client, db):
        """GET /extractos/{id}/movimientos sin `limit` acota a 100 (default), para que
        un consumidor que olvide paginar no se lleve el extracto entero. `limit=0` es
        el opt-in explícito de 'sin límite' (lo usa Movimientos.tsx para paginar en
        cliente). Regresión: antes el default era 0 = sin límite."""
        token = _token(db, "super@org.test")
        # 105 movimientos únicos (titular/monto/saldo distintos → no colapsan por dedup)
        filas = [(f"2026-06-{(i % 28) + 1:02d}", f"Cli {i}", 1000 + i, 100000 + i)
                 for i in range(105)]
        r = client.post("/extractos/upload?org_id=2",
                        files={"file": ("grande.xlsx", _xlsx_bytes(filas),
                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                        headers=_auth(token))
        assert r.status_code == 200, r.text
        eid = r.json()["id"]

        # sin limit → default 100, pero total refleja los 105
        d = client.get(f"/extractos/{eid}/movimientos", headers=_auth(token)).json()
        assert d["total"] == 105
        assert len(d["items"]) == 100, "el default debe acotar a 100"

        # limit explícito
        d10 = client.get(f"/extractos/{eid}/movimientos?limit=10", headers=_auth(token)).json()
        assert len(d10["items"]) == 10

        # limit=0 = escape hatch sin límite → trae los 105
        d0 = client.get(f"/extractos/{eid}/movimientos?limit=0", headers=_auth(token)).json()
        assert len(d0["items"]) == 105, "limit=0 debe traer todo (opt-in)"
