"""API: preview de extractos Excel/CSV, upload con mapeo y plantillas por org.

Archivos sintéticos (ver `tests/extracto_sintetico.py`): nunca datos reales.
"""

from __future__ import annotations

import json
from decimal import Decimal as D

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.auditoria import AuditoriaLog
from app.models.extracto import ExtractoBancario, MovimientoBanco
from app.models.extracto_plantilla import PlantillaExtractoExcel
from app.models.organizacion import Organizacion
from app.models.user import User
from app.services.auth import create_access_token, get_password_hash
from tests.extracto_sintetico import movimientos_cronologicos, xlsx_desde_filas, xlsx_estilo_macro

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    session.add_all([Organizacion(id=1, nombre="Uno"), Organizacion(id=2, nombre="Dos")])
    session.commit()
    for email, org, role in [("admin1@t.test", 1, "admin"), ("admin2@t.test", 2, "admin"),
                             ("revisor@t.test", 1, "revisor")]:
        session.add(User(email=email, full_name=email, hashed_password=get_password_hash("pw"),
                         organizacion_id=org, is_active=True, role=role, is_superadmin=False,
                         allowed_org_ids=[]))
    session.commit()
    yield session
    session.close()


@pytest.fixture(autouse=True)
def _sin_rate_limit():
    from app.routers import extractos as _ext
    prev = _ext.limiter.enabled
    _ext.limiter.enabled = False
    yield
    _ext.limiter.enabled = prev


@pytest.fixture
def client(db):
    def _override():
        yield db
    app.dependency_overrides[get_db] = _override
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)


def _h(db, email):
    u = db.query(User).filter(User.email == email).first()
    return {"Authorization": "Bearer " + create_access_token(
        {"sub": u.email, "user_id": u.id, "role": u.role})}


def _sin_titulos(sin_fila: int | None = None) -> bytes:
    """Extracto sin renglón de títulos reconocible (la plantilla lo reconoce por su encabezado).
    `sin_fila`: índice cronológico de un movimiento que se saca (el saldo deja de cuadrar)."""
    filas = [["F. Op", "Glosa x", "Valor x", "Acum x"]]
    for i, m in enumerate(movimientos_cronologicos(4)):
        if i == sin_fila:
            continue
        filas.append([m["fecha"].strftime("%d/%m/%Y"), m["titular"], float(m["monto"]), float(m["saldo"])])
    return xlsx_desde_filas(filas)


MAPEO_SIN_TITULOS = {"fila_encabezado": 0, "signo": "columna_unica",
                     "columnas": {"fecha": 0, "titular": 1, "monto": 2, "saldo": 3}}


def _preview(client, h, contenido, nombre="ext.xlsx", tipo=XLSX, mapeo=None):
    data = {"mapeo": json.dumps(mapeo)} if mapeo is not None else {}
    return client.post("/extractos/preview", headers=h, files={"file": (nombre, contenido, tipo)}, data=data)


def _upload(client, h, contenido, nombre="ext.xlsx", tipo=XLSX, mapeo=None):
    data = {"mapeo": json.dumps(mapeo)} if mapeo is not None else {}
    return client.post("/extractos/upload", headers=h, files={"file": (nombre, contenido, tipo)}, data=data)


# ── Preview ──────────────────────────────────────────────────────────────────

def test_preview_estilo_macro(client, db):
    r = _preview(client, _h(db, "admin1@t.test"), xlsx_estilo_macro(6))
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["origen"] == "heuristica"
    assert b["banco_clave"] == "macro"
    assert b["mapeo"]["fila_encabezado"] == 2
    assert b["mapeo"]["columnas"]["monto"] == 4
    assert b["cuadre"]["cuadra"] is True
    assert b["cuadre"]["orden"] == "desc"
    assert b["necesita_mapeo"] is False
    assert b["total_movimientos"] == 6
    assert b["filas_resumen"] == 1
    assert len(b["grilla"]["filas"]) >= 9
    assert D(b["muestra"][0]["monto"]) == D("-1234.56")
    # No guarda nada
    assert db.query(ExtractoBancario).count() == 0
    assert db.query(PlantillaExtractoExcel).count() == 0


def test_preview_sin_titulos_pide_mapeo(client, db):
    r = _preview(client, _h(db, "admin1@t.test"), _sin_titulos())
    assert r.status_code == 200
    b = r.json()
    assert b["necesita_mapeo"] is True
    assert b["origen"] in ("sugerencia", "ninguno")


def test_preview_con_mapeo_manual_recalcula_cuadre(client, db):
    r = _preview(client, _h(db, "admin1@t.test"), _sin_titulos(), mapeo=MAPEO_SIN_TITULOS)
    b = r.json()
    assert b["origen"] == "manual"
    assert b["cuadre"]["cuadra"] is True
    assert b["total_movimientos"] == 4


def test_preview_mapeo_invalido_400(client, db):
    h = _h(db, "admin1@t.test")
    r = _preview(client, h, _sin_titulos(), mapeo={"columnas": {"fecha": 0}})
    assert r.status_code == 400
    assert "importe" in r.json()["detail"]
    r = client.post("/extractos/preview", headers=h,
                    files={"file": ("e.xlsx", _sin_titulos(), XLSX)}, data={"mapeo": "{no json"})
    assert r.status_code == 400


def test_preview_csv_y_tsv(client, db):
    h = _h(db, "admin1@t.test")
    csv_ = "Fecha;Concepto;Importe;Saldo\n01/05/2026;Cobro;1.000,00;2.000,00\n02/05/2026;Pago;-500,00;1.500,00\n"
    r = _preview(client, h, csv_.encode(), "e.csv", "text/csv")
    assert r.status_code == 200 and r.json()["cuadre"]["cuadra"] is True
    tsv = csv_.replace(";", "\t")
    r = _preview(client, h, tsv.encode(), "e.tsv", "text/tab-separated-values")
    assert r.status_code == 200 and r.json()["total_movimientos"] == 2


def test_preview_extension_no_aceptada(client, db):
    r = _preview(client, _h(db, "admin1@t.test"), b"hola", "e.doc", "application/msword")
    assert r.status_code == 400


# ── Upload ───────────────────────────────────────────────────────────────────

def test_upload_sin_deteccion_devuelve_422(client, db):
    r = _upload(client, _h(db, "admin1@t.test"), _sin_titulos())
    assert r.status_code == 422
    assert r.json()["detail"]["codigo"] == "necesita_mapeo"
    assert db.query(ExtractoBancario).count() == 0


def test_upload_con_mapeo_importa_y_guarda_plantilla(client, db):
    h = _h(db, "admin1@t.test")
    r = _upload(client, h, _sin_titulos(), mapeo=MAPEO_SIN_TITULOS)
    assert r.status_code == 200, r.text
    assert len(r.json()["movimientos"]) == 4
    movs = db.query(MovimientoBanco).all()
    assert sorted(m.monto for m in movs) == sorted(m["monto"] for m in movimientos_cronologicos(4))
    plantillas = db.query(PlantillaExtractoExcel).all()
    assert len(plantillas) == 1
    p = plantillas[0]
    assert p.organizacion_id == 1
    assert p.mapeo["columnas"] == MAPEO_SIN_TITULOS["columnas"]
    assert "fila_encabezado" not in p.mapeo
    assert p.encabezados[:2] == ["F. Op", "Glosa x"]
    assert db.query(AuditoriaLog).filter(AuditoriaLog.tabla == "plantillas_extracto_excel").count() == 1


def test_plantilla_se_reusa_en_la_misma_org(client, db):
    h = _h(db, "admin1@t.test")
    assert _upload(client, h, _sin_titulos(), mapeo=MAPEO_SIN_TITULOS).status_code == 200
    r = _preview(client, h, _sin_titulos())
    b = r.json()
    assert b["origen"] == "plantilla"
    assert b["necesita_mapeo"] is False
    assert b["cuadre"]["cuadra"] is True
    # Y el upload sin mapeo ya funciona (un clic).
    db.query(MovimientoBanco).delete()
    db.query(ExtractoBancario).delete()
    db.commit()
    r = _upload(client, h, _sin_titulos())
    assert r.status_code == 200, r.text
    assert db.query(PlantillaExtractoExcel).one().usos == 2


def test_plantilla_aislada_por_org(client, db):
    assert _upload(client, _h(db, "admin1@t.test"), _sin_titulos(), mapeo=MAPEO_SIN_TITULOS).status_code == 200
    h2 = _h(db, "admin2@t.test")
    b = _preview(client, h2, _sin_titulos()).json()
    assert b["origen"] != "plantilla"
    assert b["necesita_mapeo"] is True
    assert _upload(client, h2, _sin_titulos()).status_code == 422


def test_org_ajena_por_parametro_no_usa_su_plantilla(client, db):
    """Un admin de la org 2 no puede elegir la org 1 con `org_id` para usar sus plantillas."""
    assert _upload(client, _h(db, "admin1@t.test"), _sin_titulos(), mapeo=MAPEO_SIN_TITULOS).status_code == 200
    r = client.post("/extractos/preview?org_id=1", headers=_h(db, "admin2@t.test"),
                    files={"file": ("e.xlsx", _sin_titulos(), XLSX)})
    assert r.json()["origen"] != "plantilla"


def test_upload_estilo_macro_sin_mapeo_sigue_en_un_clic(client, db):
    r = _upload(client, _h(db, "admin1@t.test"), xlsx_estilo_macro(6))
    assert r.status_code == 200, r.text
    ext = db.query(ExtractoBancario).one()
    assert ext.banco == "Banco Macro"
    assert db.query(MovimientoBanco).count() == 6           # la fila TOTAL no entra
    # Sin mapeo confirmado no se guarda plantilla.
    assert db.query(PlantillaExtractoExcel).count() == 0


def test_resubir_mismo_extracto_con_mapeo_no_duplica(client, db):
    h = _h(db, "admin1@t.test")
    assert _upload(client, h, _sin_titulos(), mapeo=MAPEO_SIN_TITULOS).status_code == 200
    assert _upload(client, h, _sin_titulos(), mapeo=MAPEO_SIN_TITULOS).status_code == 200
    assert db.query(ExtractoBancario).count() == 1
    assert db.query(PlantillaExtractoExcel).count() == 1


def test_um_usa_plantilla_de_la_org(client, db):
    h = _h(db, "admin1@t.test")
    r = _upload(client, h, _sin_titulos(), mapeo=MAPEO_SIN_TITULOS)
    ext_id = r.json()["id"]
    r = client.post(f"/extractos/{ext_id}/agregar-um", headers=h,
                    files={"file": ("um.xlsx", _sin_titulos(), XLSX)})
    assert r.status_code == 200, r.text
    assert r.json()["agregados"] == 0


# ── Permisos ─────────────────────────────────────────────────────────────────

def test_permisos_revisor_no_puede(client, db):
    h = _h(db, "revisor@t.test")
    assert _preview(client, h, xlsx_estilo_macro(3)).status_code == 403
    assert _upload(client, h, xlsx_estilo_macro(3)).status_code == 403


def test_sin_login(client, db):
    r = client.post("/extractos/preview", files={"file": ("e.xlsx", xlsx_estilo_macro(3), XLSX)})
    assert r.status_code in (401, 403)


# ── Plantilla guardada + saldos que no cuadran: importa igual, con aviso ─────

def test_plantilla_con_saldos_que_no_cuadran_importa_con_aviso(client, db):
    h = _h(db, "admin1@t.test")
    assert _upload(client, h, _sin_titulos(), mapeo=MAPEO_SIN_TITULOS).status_code == 200
    db.query(MovimientoBanco).delete()
    db.query(ExtractoBancario).delete()
    db.commit()
    incompleto = _sin_titulos(sin_fila=2)       # le falta un movimiento en el medio

    b = _preview(client, h, incompleto).json()
    assert b["origen"] == "plantilla"
    assert b["cuadre"]["cuadra"] is False
    assert b["necesita_mapeo"] is False          # no se fuerza la pantalla de columnas
    aviso = "Los saldos no cuadran desde la fila 4: puede que falten movimientos en este archivo"
    assert b["aviso_saldos"] == aviso

    r = _upload(client, h, incompleto)           # un clic, sin mapeo
    assert r.status_code == 200, r.text
    assert r.json()["aviso_saldos"] == aviso
    assert db.query(ExtractoBancario).one().aviso_saldos == aviso
    item = client.get("/extractos", headers=h).json()["items"][0]
    assert item["aviso_saldos"] == aviso


def test_sin_plantilla_y_saldos_que_no_cuadran_sigue_pidiendo_columnas(client, db):
    filas = [["Fecha", "Concepto", "Importe", "Saldo"]]
    for i, m in enumerate(movimientos_cronologicos(4)):
        if i != 2:
            filas.append([m["fecha"].strftime("%d/%m/%Y"), m["titular"], float(m["monto"]), float(m["saldo"])])
    b = _preview(client, _h(db, "admin1@t.test"), xlsx_desde_filas(filas)).json()
    assert b["origen"] == "heuristica"
    assert b["necesita_mapeo"] is True
    assert b["aviso_saldos"]


def test_extracto_que_cuadra_no_tiene_aviso(client, db):
    r = _upload(client, _h(db, "admin1@t.test"), xlsx_estilo_macro(6))
    assert r.json()["aviso_saldos"] is None


# ── Extractos "del más viejo al más nuevo": se guardan igual que Macro ──────

def _ascendente(n: int) -> bytes:
    filas = [["Fecha", "Concepto", "Importe", "Saldo"]]
    for m in movimientos_cronologicos(n):
        filas.append([m["fecha"].strftime("%d/%m/%Y"), m["titular"], float(m["monto"]), float(m["saldo"])])
    return xlsx_desde_filas(filas)


def _movs_por_orden(db):
    return db.query(MovimientoBanco).order_by(MovimientoBanco.orden).all()


def test_ascendente_numera_como_macro(client, db):
    r = _upload(client, _h(db, "admin1@t.test"), _ascendente(4))
    assert r.status_code == 200, r.text
    movs = _movs_por_orden(db)
    cronologicos = movimientos_cronologicos(4)
    # orden 1 = el más viejo, orden 4 = el más nuevo (igual que un extracto Macro)
    assert [m.orden for m in movs] == [1, 2, 3, 4]
    assert [m.fecha for m in movs] == [c["fecha"] for c in cronologicos]
    assert [m.saldo for m in movs] == [c["saldo"] for c in cronologicos]


def test_ascendente_y_descendente_quedan_iguales(client, db):
    h = _h(db, "admin1@t.test")
    assert _upload(client, h, _ascendente(6)).status_code == 200
    asc = [(m.orden, m.fecha, m.monto) for m in _movs_por_orden(db)]
    db.query(MovimientoBanco).delete()
    db.query(ExtractoBancario).delete()
    db.commit()
    assert _upload(client, h, xlsx_estilo_macro(6)).status_code == 200
    desc = [(m.orden, m.fecha, m.monto) for m in _movs_por_orden(db)]
    assert asc == desc


def test_ascendente_um_agrega_los_nuevos(client, db):
    h = _h(db, "admin1@t.test")
    ext_id = _upload(client, h, _ascendente(4)).json()["id"]
    r = client.post(f"/extractos/{ext_id}/agregar-um", headers=h,
                    files={"file": ("um.xlsx", _ascendente(6), XLSX)})
    assert r.status_code == 200, r.text
    assert r.json()["agregados"] == 2
    movs = _movs_por_orden(db)
    cronologicos = movimientos_cronologicos(6)
    assert [m.orden for m in movs] == [1, 2, 3, 4, 5, 6]
    assert [m.fecha for m in movs] == [c["fecha"] for c in cronologicos]
    assert [m.source for m in movs[-2:]] == ["um", "um"]


def test_ascendente_resubido_se_reconoce_como_duplicado(client, db):
    h = _h(db, "admin1@t.test")
    a = _upload(client, h, _ascendente(4)).json()["id"]
    b = _upload(client, h, _ascendente(4)).json()["id"]
    assert a == b
    assert db.query(ExtractoBancario).count() == 1
    assert db.query(MovimientoBanco).count() == 4
