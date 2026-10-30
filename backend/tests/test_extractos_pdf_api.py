"""Tests de la API de extractos en PDF (`/extractos-pdf`).

El lector de PDF se reemplaza por uno falso (`svc.lector`) que devuelve un
`ResultadoLectura` armado a mano (Contrato 1): acá se prueba la persistencia, no
la lectura. El cuadre sí lo calcula el `validar_saldos` real (fuente única).

Cubre:
  - importar → listo; necesita IA → procesando → segundo plano → listo; mismo PDF dos
    veces → mismo borrador; errores del archivo; IA no configurada.
  - confirmar → extracto nuevo igual que el Excel (orden 1..N, org, source, banco,
    auditoría); confirmar dos veces; duplicados (mismo archivo / mismos movimientos /
    solapado) y "agregar solo los nuevos" con el merge de UM + asiento.
  - validaciones 422 con mensaje de fila, saldo que no cierra, topes de Numeric(12,2).
  - formato aprendido (molde): se crea, se refuerza, no se aprende si se corrigió > 10 %.
  - permisos, aislamiento multi-tenant, superadmin con ?org_id=, borradores colgados.
  - la predicción de "nuevos" es igual al merge real (vigila que no se desfase).
No toca la red ni Gemini.
"""
import copy
import io
from datetime import date, datetime, timedelta
from decimal import Decimal

import openpyxl
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.auditoria import AuditoriaLog
from app.models.extracto import ExtractoBancario, MovimientoBanco
from app.models.extracto_pdf import BorradorExtractoPdf, MoldeExtractoPdf
from app.models.liquidacion import CierrePeriodo
from app.models.organizacion import Organizacion
from app.models.user import User
from app.routers import extractos_pdf as router_mod
from app.services import extracto_pdf_service as svc
from app.services.auth import create_access_token, get_password_hash
from app.services.extracto_import import crear_extracto_con_movimientos
from app.services.extracto_merger import mergear_movimientos
from app.services.extracto_pdf.saldos import marcar_dudosas, validar_saldos

HOY = date(2026, 10, 16)
FIRMA_GALICIA = "f" * 40

PDF_SEP = b"%PDF-1.4 galicia septiembre"
PDF_OCT = b"%PDF-1.4 galicia octubre"
PDF_ESCANEADO = b"%PDF-1.4 escaneado"

# Galicia septiembre (orden del PDF: el más viejo primero). Saldo inicial 1000.
FILAS_SEP = [
    ("2026-09-02", "TRANSF RECIBIDA PEREZ JUAN 20123456786", "500.00", "1500.00"),
    ("2026-09-03", "PAGO PROVEEDOR ACME SA", "-200.00", "1300.00"),
    ("2026-09-05", "COMISION MANTENIMIENTO CUENTA", "-50.00", "1250.00"),
    ("2026-09-10", "TRANSF RECIBIDA GOMEZ ANA", "750.00", "2000.00"),
]
FILAS_OCT = [
    ("2026-10-01", "TRANSF RECIBIDA LOPEZ MARIA", "300.00", "2300.00"),
    ("2026-10-02", "DEBITO AUTOMATICO SEGURO", "-100.00", "2200.00"),
    ("2026-10-06", "TRANSF RECIBIDA DIAZ PEDRO", "800.00", "3000.00"),
]


def _res(filas, *, saldo_inicial="1000.00", saldo_final=None, metodo="automatico", banco_clave="galicia",
         orden="asc", aprendizaje="auto", molde_id=None, ia_usada=False, alertas=()):
    """ResultadoLectura (Contrato 1) con el cuadre calculado por el validar_saldos real."""
    movs = [{"fecha": date.fromisoformat(f) if f else None, "descripcion": d, "monto": Decimal(m),
             "saldo": Decimal(s) if s else None, "pagina": 1, "dudosa": False, "motivos": []}
            for (f, d, m, s) in filas]
    si = Decimal(saldo_inicial) if saldo_inicial is not None else None
    sf = Decimal(saldo_final) if saldo_final is not None else None
    cuadre = validar_saldos(movs, orden=orden, saldo_inicial=si, saldo_final=sf)
    marcar_dudosas(movs, cuadre)
    fechas = [m["fecha"] for m in movs if m["fecha"]]
    if aprendizaje == "auto":
        aprendizaje = ({"firma": FIRMA_GALICIA, "banco_clave": banco_clave,
                        "layout": {"columnas": {"fecha": [40, 90], "monto": [400, 470]}, "orden": orden}}
                       if metodo in ("automatico", "ia") else None)
    return {
        "metodo": metodo if movs else None, "molde_id": molde_id, "banco_clave": banco_clave,
        "paginas": 1, "escaneado": False, "orden": orden,
        "periodo_desde": min(fechas) if fechas else None, "periodo_hasta": max(fechas) if fechas else None,
        "saldo_inicial": si, "saldo_final": sf if sf is not None else cuadre["saldo_final"],
        "movimientos": movs, "cuadre": cuadre, "alertas": list(alertas),
        "aprendizaje": aprendizaje, "ia_usada": ia_usada, "ia_disponible": False,
    }


class LectorFalso:
    """Reemplaza a `leer_extracto_pdf`: deterministas por contenido, IA aparte."""

    def __init__(self):
        self.det: dict[bytes, dict] = {}
        self.ia: dict[bytes, dict] = {}
        self.llamadas: list[dict] = []
        self.error: Exception | None = None
        self.error_ia: Exception | None = None
        self.usar_moldes = False

    def __call__(self, contenido, *, moldes=(), usar_ia=True, forzar_ia=False, hoy=None, nombre_archivo=None):
        self.llamadas.append({"usar_ia": usar_ia, "forzar_ia": forzar_ia, "moldes": list(moldes), "hoy": hoy})
        if self.error:
            raise self.error
        if usar_ia and self.error_ia:
            raise self.error_ia
        if self.usar_moldes and not forzar_ia:
            molde = next((m for m in moldes if m["firma"] == FIRMA_GALICIA), None)
            if molde and contenido in self.det:
                res = copy.deepcopy(self.det[contenido])
                res.update({"metodo": "molde", "molde_id": molde["id"], "aprendizaje": None})
                return res
        if usar_ia and contenido in self.ia and (forzar_ia or not (self.det.get(contenido) or {}).get("cuadre", {}).get("cierra")):
            return copy.deepcopy(self.ia[contenido])
        if contenido in self.det and not forzar_ia:
            return copy.deepcopy(self.det[contenido])
        return _res([], aprendizaje=None, alertas=[{"nivel": "aviso", "codigo": "sin_movimientos",
                                                    "mensaje": "No se encontraron movimientos."}])


# ── Fixtures ───────────────────────────────────────────────────────

@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    for oid, nombre in [(1, "Org1"), (2, "Org2")]:
        session.add(Organizacion(id=oid, nombre=nombre))
    session.commit()
    usuarios = [
        ("super@pdf.test", 1, "admin", True),
        ("admin@pdf.test", 1, "admin", False),
        ("admin2@pdf.test", 2, "admin", False),
        ("operador@pdf.test", 1, "operador", False),
        ("revisor@pdf.test", 1, "revisor", False),
    ]
    for email, oid, rol, sa in usuarios:
        session.add(User(email=email, full_name=email, hashed_password=get_password_hash("pw"),
                         organizacion_id=oid, is_active=True, role=rol, is_superadmin=sa))
    session.commit()
    yield session
    session.close()


@pytest.fixture
def lector(monkeypatch):
    falso = LectorFalso()
    falso.det[PDF_SEP] = _res(FILAS_SEP)
    falso.det[PDF_OCT] = _res(FILAS_OCT, saldo_inicial="2000.00")
    monkeypatch.setattr(svc, "lector", falso)
    monkeypatch.setattr(svc, "ia_configurada", lambda: False)
    return falso


@pytest.fixture
def con_ia(monkeypatch):
    monkeypatch.setattr(svc, "ia_configurada", lambda: True)


@pytest.fixture(autouse=True)
def _sin_rate_limit():
    from app.routers import extractos as ext_mod
    prev = (router_mod.limiter.enabled, ext_mod.limiter.enabled)
    router_mod.limiter.enabled = False
    ext_mod.limiter.enabled = False
    yield
    router_mod.limiter.enabled, ext_mod.limiter.enabled = prev


@pytest.fixture
def client(db, lector, monkeypatch):
    def _override_db():
        yield db
    app.dependency_overrides[get_db] = _override_db
    # El procesamiento en segundo plano usa una sesión propia sobre la misma DB.
    monkeypatch.setattr(router_mod, "_session_factory", sessionmaker(bind=db.get_bind()))
    c = TestClient(app, raise_server_exceptions=True)
    yield c
    app.dependency_overrides.pop(get_db, None)


def _auth(db, email="admin@pdf.test"):
    u = db.query(User).filter(User.email == email).first()
    tok = create_access_token({"sub": u.email, "user_id": u.id, "role": u.role})
    return {"Authorization": f"Bearer {tok}"}


def _importar(client, headers, contenido=PDF_SEP, nombre="resumen-sep.pdf", **params):
    return client.post("/extractos-pdf/importar", headers=headers, params=params,
                       files={"file": (nombre, contenido, "application/pdf")})


def _payload(borrador, **extra):
    """Lo que manda la pantalla de revisión sin tocar nada."""
    body = {
        "movimientos": [{k: m[k] for k in ("fecha", "descripcion", "monto", "saldo")}
                        for m in borrador["movimientos"]],
        "saldo_inicial": borrador["saldo_inicial"], "saldo_final": borrador["saldo_final"],
        "banco": borrador["banco"], "nombre": None, "destino": "nuevo", "extracto_id": None,
        "confirmar_sin_cuadre": False,
    }
    body.update(extra)
    return body


def _confirmar(client, headers, borrador, **extra):
    params = extra.pop("params", None)
    return client.post(f"/extractos-pdf/borradores/{borrador['id']}/confirmar", headers=headers,
                       params=params, json=_payload(borrador, **extra))


def _listo(client, db, contenido=PDF_SEP, email="admin@pdf.test", **params):
    r = _importar(client, _auth(db, email), contenido, **params)
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["estado"] == "listo", b
    return b


def _xlsx(filas):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Fecha", "Titular", "Monto", "Saldo"])
    for f in filas:
        ws.append(list(f))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _subir_excel(client, headers, filas_newest_first, nombre="extracto.xlsx", org_id=None):
    params = {"banco": "Banco Macro"}
    if org_id:
        params["org_id"] = org_id
    filas = [(f, d, float(m), float(s)) for (f, d, m, s) in filas_newest_first]
    r = client.post("/extractos/upload", headers=headers, params=params,
                    files={"file": (nombre, _xlsx(filas),
                                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert r.status_code == 200, r.text
    return r.json()["id"]


# ── Importar ───────────────────────────────────────────────────────

def test_importar_lectura_determinista_queda_lista(client, db, lector):
    b = _listo(client, db)
    assert b["metodo"] == "automatico"
    assert b["banco"] == "Galicia" and b["banco_clave"] == "galicia"
    assert b["periodo_desde"] == "2026-09-02" and b["periodo_hasta"] == "2026-09-10"
    assert b["saldo_inicial"] == "1000.00" and b["saldo_final"] == "2000.00"
    assert b["orden"] == "asc" and b["escaneado"] is False
    assert [m["monto"] for m in b["movimientos"]] == ["500.00", "-200.00", "-50.00", "750.00"]
    assert b["cuadre"]["cierra"] is True and b["cuadre"]["diferencia"] == "0.00"
    assert b["cuadre"]["total_creditos"] == "1250.00" and b["cuadre"]["total_debitos"] == "250.00"
    assert b["duplicado"] is None and b["puede_aprender"] is True
    assert b["ia_disponible"] is False and b["ia_usada"] is False
    # La lectura inline no usa IA; recibe el `hoy` de negocio.
    assert lector.llamadas[-1]["usar_ia"] is False and lector.llamadas[-1]["hoy"] is not None
    fila = db.query(BorradorExtractoPdf).one()
    assert fila.organizacion_id == 1 and fila.contenido_sha256 and fila.tamano_bytes == len(PDF_SEP)
    assert fila.saldo_inicial == Decimal("1000.00")
    assert db.query(ExtractoBancario).count() == 0      # nada impacta hasta confirmar
    assert db.query(AuditoriaLog).filter(AuditoriaLog.accion == "IMPORTAR").count() == 1


def test_importar_que_necesita_ia_pasa_por_segundo_plano(client, db, lector, con_ia):
    # Lo determinista no cierra (falta una fila) → con IA configurada queda procesando.
    lector.det[PDF_SEP] = _res(FILAS_SEP[:3], saldo_final="2000.00")
    lector.ia[PDF_SEP] = _res(FILAS_SEP, metodo="ia", ia_usada=True)
    r = _importar(client, _auth(db))
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "procesando"
    # TestClient corre la tarea en segundo plano al terminar el request.
    assert [ll["usar_ia"] for ll in lector.llamadas] == [False, True]
    b = client.get(f"/extractos-pdf/borradores/{r.json()['id']}", headers=_auth(db)).json()
    assert b["estado"] == "listo" and b["metodo"] == "ia" and b["ia_usada"] is True
    assert len(b["movimientos"]) == 4 and b["cuadre"]["cierra"] is True
    assert b["ia_disponible"] is True


def test_sin_ia_queda_listo_con_lo_que_se_leyo(client, db, lector):
    r = _importar(client, _auth(db), PDF_ESCANEADO, nombre="escaneado.pdf")
    b = r.json()
    assert r.status_code == 200 and b["estado"] == "listo"
    assert b["movimientos"] == [] and b["metodo"] is None
    assert any(a["codigo"] == "sin_movimientos" for a in b["alertas"])
    assert [ll["usar_ia"] for ll in lector.llamadas] == [False]


def test_mismo_pdf_dos_veces_devuelve_el_mismo_borrador(client, db, lector):
    b1 = _listo(client, db)
    b2 = _listo(client, db)
    assert b1["id"] == b2["id"]
    assert db.query(BorradorExtractoPdf).count() == 1
    # Otra org con el mismo PDF tiene su propio borrador.
    b3 = _listo(client, db, email="admin2@pdf.test")
    assert b3["id"] != b1["id"]


def test_mismo_pdf_ya_confirmado_devuelve_el_confirmado(client, db, lector):
    b = _listo(client, db)
    assert _confirmar(client, _auth(db), b).status_code == 200
    r = _importar(client, _auth(db))
    assert r.json()["id"] == b["id"] and r.json()["estado"] == "confirmado"
    assert r.json()["extracto_id"] is not None
    assert db.query(BorradorExtractoPdf).count() == 1
    # Si se borra el extracto, el mismo PDF se puede volver a importar.
    ext = db.get(ExtractoBancario, r.json()["extracto_id"])
    ext.deleted_at = datetime(2026, 10, 16, 12, 0)
    db.commit()
    r2 = _importar(client, _auth(db))
    assert r2.json()["id"] != b["id"] and r2.json()["estado"] == "listo"


def test_archivo_invalido(client, db, lector):
    h = _auth(db)
    r = client.post("/extractos-pdf/importar", headers=h,
                    files={"file": ("resumen.xlsx", b"PK\x03\x04", "application/octet-stream")})
    assert r.status_code == 400 and r.json()["detail"] == "Solo se aceptan archivos PDF."
    r = _importar(client, h, b"hola, no soy un pdf", nombre="falso.pdf")
    assert r.status_code == 400 and r.json()["detail"] == "El archivo no es un PDF válido."
    r = _importar(client, h, b"", nombre="vacio.pdf")
    assert r.status_code == 400
    assert db.query(BorradorExtractoPdf).count() == 0


def test_error_del_lector_no_crea_borrador(client, db, lector):
    from app.services.extracto_pdf.errores import ExtractoPdfError
    lector.error = ExtractoPdfError("El PDF tiene contraseña: abrilo y usá Imprimir → Guardar como PDF.", 400)
    r = _importar(client, _auth(db))
    assert r.status_code == 400 and "contraseña" in r.json()["detail"]
    lector.error = ExtractoPdfError("El PDF tiene demasiadas páginas.", 413)
    assert _importar(client, _auth(db)).status_code == 413
    assert db.query(BorradorExtractoPdf).count() == 0


def test_archivo_demasiado_grande(client, db, lector, monkeypatch):
    from app.config import Settings
    monkeypatch.setattr(router_mod, "get_settings", lambda: Settings(max_file_size=10))
    r = _importar(client, _auth(db))
    assert r.status_code == 413
    assert db.query(BorradorExtractoPdf).count() == 0


def test_forzar_ia_sin_ia_configurada_da_503(client, db, lector):
    r = _importar(client, _auth(db), forzar_ia=True)
    assert r.status_code == 503 and "GEMINI_API_KEY" in r.json()["detail"]


def test_forzar_ia_relee_el_mismo_borrador(client, db, lector, con_ia):
    b = _listo(client, db)
    lector.ia[PDF_SEP] = _res(FILAS_SEP, metodo="ia", ia_usada=True)
    r = _importar(client, _auth(db), forzar_ia=True)
    assert r.status_code == 200 and r.json()["id"] == b["id"] and r.json()["estado"] == "procesando"
    assert lector.llamadas[-1] == {**lector.llamadas[-1], "usar_ia": True, "forzar_ia": True}
    b2 = client.get(f"/extractos-pdf/borradores/{b['id']}", headers=_auth(db)).json()
    assert b2["estado"] == "listo" and b2["metodo"] == "ia"
    assert db.query(BorradorExtractoPdf).count() == 1


def test_falla_en_segundo_plano_deja_error_y_no_lanza(client, db, lector, con_ia):
    lector.det[PDF_SEP] = _res(FILAS_SEP[:3], saldo_final="2000.00")
    lector.error_ia = RuntimeError("Gemini caído")
    r = _importar(client, _auth(db))
    assert r.status_code == 200 and r.json()["estado"] == "procesando"
    b = client.get(f"/extractos-pdf/borradores/{r.json()['id']}", headers=_auth(db)).json()
    assert b["estado"] == "error" and b["error"] == svc.MSG_ERROR_LECTURA


def test_segundo_plano_no_pisa_un_borrador_descartado(client, db, lector):
    b = _listo(client, db)
    fila = db.get(BorradorExtractoPdf, b["id"])
    fila.estado = "descartado"
    db.commit()
    svc.procesar_en_fondo(sessionmaker(bind=db.get_bind()), borrador_id=b["id"], contenido=PDF_SEP)
    db.expire_all()
    assert db.get(BorradorExtractoPdf, b["id"]).estado == "descartado"


def test_borrador_colgado_se_informa_como_error(client, db, lector):
    viejo = datetime.utcnow() - timedelta(minutes=svc.MINUTOS_COLGADO + 1)
    b = BorradorExtractoPdf(organizacion_id=1, creado_por=1, nombre_archivo="x.pdf", estado="procesando",
                            creado_at=viejo, actualizado_at=viejo, datos={"movimientos": []})
    reciente = BorradorExtractoPdf(organizacion_id=1, creado_por=1, nombre_archivo="y.pdf", estado="procesando",
                                   datos={"movimientos": []})
    db.add_all([b, reciente])
    db.commit()
    r = client.get(f"/extractos-pdf/borradores/{b.id}", headers=_auth(db))
    assert r.json()["estado"] == "error" and r.json()["error"] == svc.MSG_COLGADO
    items = client.get("/extractos-pdf/borradores", headers=_auth(db)).json()["items"]
    assert {i["id"]: i["estado"] for i in items} == {b.id: "error", reciente.id: "procesando"}


def test_alerta_de_periodo_cerrado(client, db, lector):
    org = db.get(Organizacion, 1)
    org.configuracion = {**(org.configuracion or {}), "requiere_cierre_periodo": True}
    db.add(CierrePeriodo(organizacion_id=1, periodo_inicio=date(2026, 9, 1), periodo_fin=date(2026, 9, 30),
                         cerrado_by=1))
    db.commit()
    b = _listo(client, db)
    alerta = next(a for a in b["alertas"] if a["codigo"] == "periodo_cerrado")
    assert alerta["nivel"] == "aviso" and "4 movimientos" in alerta["mensaje"]
    # Aviso, no bloqueo: se puede confirmar igual.
    assert _confirmar(client, _auth(db), b).status_code == 200


# ── Confirmar: extracto nuevo ──────────────────────────────────────

def test_confirmar_nuevo_crea_extracto_igual_que_excel(client, db, lector):
    b = _listo(client, db)
    r = _confirmar(client, _auth(db), b, nombre="Galicia sep 2026")
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["destino"] == "nuevo" and out["ya_existia"] is False
    assert out["agregados"] == 4 and out["duplicados"] == 0 and out["contabilidad_ok"] is True
    assert out["mensaje"] == "Extracto guardado: 4 movimientos."
    ext = db.get(ExtractoBancario, out["extracto_id"])
    assert ext.organizacion_id == 1 and ext.nombre_archivo == "Galicia sep 2026"
    assert ext.banco == "Galicia" and ext.fingerprint and ext.creado_por is not None
    movs = db.query(MovimientoBanco).filter(MovimientoBanco.extracto_id == ext.id) \
        .order_by(MovimientoBanco.orden).all()
    # orden 1..N: 1 = el más viejo, N = el más reciente (igual que el Excel/UM).
    assert [m.orden for m in movs] == [1, 2, 3, 4]
    assert [m.fecha.isoformat() for m in movs] == [f[0] for f in FILAS_SEP]
    assert [m.monto for m in movs] == [Decimal("500.00"), Decimal("-200.00"), Decimal("-50.00"), Decimal("750.00")]
    assert movs[-1].saldo == Decimal("2000.00") and movs[0].mes == "9"
    assert movs[0].titular == "TRANSF RECIBIDA PEREZ JUAN 20123456786"
    assert all(m.source == "extracto" and m.um_lote is None and m.organizacion_id == 1 for m in movs)
    log = db.query(AuditoriaLog).filter(AuditoriaLog.tabla == "extractos_bancarios",
                                        AuditoriaLog.accion == "INSERT").one()
    assert log.registro_id == ext.id
    assert log.cambios["origen"] == "pdf" and log.cambios["metodo"] == "automatico"
    assert log.cambios["movimientos"] == 4
    fila = db.get(BorradorExtractoPdf, b["id"])
    assert fila.estado == "confirmado" and fila.extracto_id == ext.id and fila.confirmado_at


def test_confirmar_orden_desc_respeta_el_orden_del_pdf(client, db, lector):
    lector.det[PDF_SEP] = _res(list(reversed(FILAS_SEP)), orden="desc")
    b = _listo(client, db)
    out = _confirmar(client, _auth(db), b).json()
    movs = db.query(MovimientoBanco).filter(MovimientoBanco.extracto_id == out["extracto_id"]) \
        .order_by(MovimientoBanco.orden).all()
    assert [m.fecha.isoformat() for m in movs] == [f[0] for f in FILAS_SEP]


def test_banco_elegido_por_la_persona_se_respeta(client, db, lector):
    b = _listo(client, db, banco="Banco Galicia (cta sueldo)")
    assert b["banco"] == "Banco Galicia (cta sueldo)"
    out = _confirmar(client, _auth(db), b, banco="Galicia empresa").json()
    assert db.get(ExtractoBancario, out["extracto_id"]).banco == "Galicia empresa"


def test_confirmar_dos_veces_no_duplica(client, db, lector):
    b = _listo(client, db)
    r1 = _confirmar(client, _auth(db), b)
    r2 = _confirmar(client, _auth(db), b)
    assert r1.status_code == r2.status_code == 200
    assert r2.json()["ya_existia"] is True and r2.json()["extracto_id"] == r1.json()["extracto_id"]
    assert db.query(ExtractoBancario).count() == 1
    assert db.query(MovimientoBanco).count() == 4


def test_confirmando_en_curso_da_409(client, db, lector):
    b = _listo(client, db)
    fila = db.get(BorradorExtractoPdf, b["id"])
    fila.estado = "confirmando"
    db.commit()
    r = _confirmar(client, _auth(db), b)
    assert r.status_code == 409 and isinstance(r.json()["detail"], str)
    # Una confirmación colgada > 10 min se libera sola.
    fila.actualizado_at = datetime.utcnow() - timedelta(minutes=svc.MINUTOS_COLGADO + 1)
    db.commit()
    assert _confirmar(client, _auth(db), b).status_code == 200


def test_mismos_movimientos_que_un_extracto_excel_vincula(client, db, lector):
    newest_first = list(reversed(FILAS_SEP))
    ext_id = _subir_excel(client, _auth(db), newest_first)
    b = _listo(client, db)
    assert b["duplicado"]["tipo"] == "mismos_movimientos"
    assert b["duplicado"]["extracto_id"] == ext_id and b["duplicado"]["nuevos"] == 0
    out = _confirmar(client, _auth(db), b).json()
    assert out["ya_existia"] is True and out["extracto_id"] == ext_id and out["agregados"] == 0
    assert db.query(ExtractoBancario).count() == 1
    assert db.query(MovimientoBanco).count() == 4
    assert db.get(BorradorExtractoPdf, b["id"]).extracto_id == ext_id


def test_mismo_contenido_con_huella_distinta_tambien_es_duplicado(client, db, lector):
    # El mismo extracto ya cargado pero con otra huella (p. ej. un Excel con columna de
    # número de comprobante, que entra en la huella): se detecta por contenido.
    ext = crear_extracto_con_movimientos(
        db, movs=svc.a_filas_parser([{"fecha": date.fromisoformat(f), "descripcion": d, "monto": Decimal(m),
                                      "saldo": Decimal(s)} for (f, d, m, s) in FILAS_SEP], "asc"),
        nombre_archivo="cargado a mano", banco="Galicia", huella="otra-huella", org_id=1, usuario_id=1)
    b = _listo(client, db)
    assert b["duplicado"]["tipo"] == "mismos_movimientos" and b["duplicado"]["extracto_id"] == ext.id
    out = _confirmar(client, _auth(db), b).json()
    assert out["ya_existia"] is True and db.query(ExtractoBancario).count() == 1


def test_huella_igual_de_otro_mes_no_es_duplicado(client, db, lector):
    # Cuenta sin movimiento: todos los meses la misma comisión + IVA → misma cantidad y
    # misma suma → misma huella del Excel. No es el mismo extracto: no hay que perderlo.
    sep = [("2026-09-30", "COMISION MANTENIMIENTO", "-100.00", "4900.00"),
           ("2026-09-30", "IVA 21%", "-21.00", "4879.00")]
    octubre = [("2026-10-31", "COMISION MANTENIMIENTO", "-100.00", "4779.00"),
               ("2026-10-31", "IVA 21%", "-21.00", "4758.00")]
    lector.det[PDF_SEP] = _res(sep, saldo_inicial="5000.00")
    lector.det[PDF_OCT] = _res(octubre, saldo_inicial="4879.00")
    e1 = _confirmar(client, _auth(db), _listo(client, db)).json()["extracto_id"]
    b2 = _listo(client, db, PDF_OCT)
    assert b2["duplicado"] is None
    out = _confirmar(client, _auth(db), b2).json()
    assert out["ya_existia"] is False and out["extracto_id"] != e1
    huellas = {e.fingerprint for e in db.query(ExtractoBancario).all()}
    assert len(huellas) == 2          # el índice único (fingerprint, org) no choca en Postgres
    assert db.query(MovimientoBanco).count() == 4


def test_mismo_archivo_confirmado_en_otro_borrador(client, db, lector):
    b1 = _listo(client, db)
    # Un segundo borrador del mismo archivo (p. ej. dos pestañas) queda pendiente.
    otro = BorradorExtractoPdf(organizacion_id=1, creado_por=1, nombre_archivo="dup.pdf", estado="listo",
                               contenido_sha256=db.get(BorradorExtractoPdf, b1["id"]).contenido_sha256,
                               datos=copy.deepcopy(db.get(BorradorExtractoPdf, b1["id"]).datos))
    db.add(otro)
    db.commit()
    ext_id = _confirmar(client, _auth(db), b1).json()["extracto_id"]
    b2 = client.get(f"/extractos-pdf/borradores/{otro.id}", headers=_auth(db)).json()
    assert b2["duplicado"]["tipo"] == "mismo_archivo" and b2["duplicado"]["extracto_id"] == ext_id
    out = _confirmar(client, _auth(db), b2).json()
    assert out["ya_existia"] is True and out["extracto_id"] == ext_id
    assert db.query(ExtractoBancario).count() == 1


# ── Confirmar: agregar a un extracto existente ─────────────────────

FILAS_SOLAPADAS = FILAS_SEP + [
    ("2026-09-12", "TRANSF RECIBIDA RUIZ LUIS", "100.00", "2100.00"),
]


def test_solapado_agrega_solo_los_nuevos(client, db, lector, monkeypatch):
    # El extracto ya tiene del 02 al 05 (cargado por Excel, del más reciente al más viejo).
    ext_id = _subir_excel(client, _auth(db), list(reversed(FILAS_SEP[:3])))
    lector.det[PDF_SEP] = _res(FILAS_SOLAPADAS)
    b = _listo(client, db)
    dup = b["duplicado"]
    assert dup["tipo"] == "solapado" and dup["extracto_id"] == ext_id
    assert dup["coincidencias"] == 3 and dup["nuevos"] == 2

    llamados = []

    def _asiento(db_, *, extracto, nuevo_lote, usuario_id, modo_asiento=None):
        llamados.append((extracto.id, nuevo_lote))
        return True
    monkeypatch.setattr(svc, "registrar_asiento_um", _asiento)
    r = _confirmar(client, _auth(db), b, destino="existente", extracto_id=ext_id)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["destino"] == "existente" and out["agregados"] == 2 and out["duplicados"] == 3
    assert out["contabilidad_ok"] is True and "2 movimientos nuevos" in out["mensaje"]
    assert llamados == [(ext_id, 1)]
    movs = db.query(MovimientoBanco).filter(MovimientoBanco.extracto_id == ext_id) \
        .order_by(MovimientoBanco.orden).all()
    assert [m.fecha.isoformat() for m in movs] == ["2026-09-02", "2026-09-03", "2026-09-05",
                                                   "2026-09-10", "2026-09-12"]
    assert [m.orden for m in movs] == [1, 2, 3, 4, 5]
    nuevos = [m for m in movs if m.source == "um"]
    assert len(nuevos) == 2 and all(m.um_lote == 1 and m.organizacion_id == 1 for m in nuevos)
    assert db.query(ExtractoBancario).count() == 1
    log = db.query(AuditoriaLog).filter(AuditoriaLog.accion == "APPEND_PDF").one()
    assert log.registro_id == ext_id and log.cambios["agregados"] == 2 and log.cambios["origen"] == "pdf"
    # Confirmar de nuevo no vuelve a agregar.
    r2 = _confirmar(client, _auth(db), b, destino="existente", extracto_id=ext_id)
    assert r2.json()["ya_existia"] is True and len(llamados) == 1
    assert db.query(MovimientoBanco).filter(MovimientoBanco.extracto_id == ext_id).count() == 5


def test_agregar_a_existente_con_asiento_real(client, db, lector):
    ext_id = _subir_excel(client, _auth(db), list(reversed(FILAS_SEP[:3])))
    lector.det[PDF_SEP] = _res(FILAS_SOLAPADAS)
    b = _listo(client, db)
    out = _confirmar(client, _auth(db), b, destino="existente", extracto_id=ext_id).json()
    assert out["agregados"] == 2 and out["contabilidad_ok"] is True


def test_destino_archivado_da_409(client, db, lector):
    ext_id = _subir_excel(client, _auth(db), list(reversed(FILAS_SEP[:3])))
    db.get(ExtractoBancario, ext_id).archivado_at = datetime(2026, 10, 1)
    db.commit()
    lector.det[PDF_SEP] = _res(FILAS_SOLAPADAS)
    b = _listo(client, db)
    # Se avisa que se pisa con un extracto archivado, pero no se le pueden agregar filas.
    assert b["duplicado"]["tipo"] == "solapado" and b["duplicado"]["archivado"] is True
    r = _confirmar(client, _auth(db), b, destino="existente", extracto_id=ext_id)
    assert r.status_code == 409 and "archivado" in r.json()["detail"]
    assert db.get(BorradorExtractoPdf, b["id"]).estado == "listo"
    assert db.query(MovimientoBanco).filter(MovimientoBanco.extracto_id == ext_id).count() == 3


def test_destino_existente_sin_extracto_o_de_otra_org(client, db, lector):
    otro = _subir_excel(client, _auth(db, "admin2@pdf.test"), list(reversed(FILAS_OCT)))
    b = _listo(client, db)
    r = _confirmar(client, _auth(db), b, destino="existente", extracto_id=None)
    assert r.status_code == 422 and isinstance(r.json()["detail"], str)
    r = _confirmar(client, _auth(db), b, destino="existente", extracto_id=otro)
    assert r.status_code == 404
    r = _confirmar(client, _auth(db), b, destino="cualquiera")
    assert r.status_code == 422


@pytest.mark.parametrize("existentes,pdf,esperado", [
    # cola: el PDF trae lo que ya estaba + lo nuevo
    (FILAS_SEP[:3], FILAS_SOLAPADAS, (3, 2)),
    # cabeza: el PDF es más viejo que el extracto → el merge no agrega lo anterior
    (FILAS_SEP[2:] + FILAS_SOLAPADAS[4:], FILAS_SEP[:3], (1, 0)),
    # sin superposición
    (FILAS_OCT, FILAS_SEP, (0, 4)),
    # filas sin saldo (cae al criterio fecha + monto + titular)
    ([(f, d, m, None) for (f, d, m, _) in FILAS_SEP[:2]], [(f, d, m, None) for (f, d, m, _) in FILAS_SEP], (2, 2)),
])
def test_prediccion_igual_al_merge_real(db, existentes, pdf, esperado):
    def _filas(tuplas):
        return [{"fecha": date.fromisoformat(f), "descripcion": d, "monto": Decimal(m),
                 "saldo": Decimal(s) if s else None} for (f, d, m, s) in tuplas]
    ext = crear_extracto_con_movimientos(
        db, movs=svc.a_filas_parser(_filas(existentes), "asc"), nombre_archivo="base", banco="Galicia",
        huella="h-base", org_id=1, usuario_id=1)
    filas_pdf = svc.a_filas_parser(_filas(pdf), "asc")
    rows = [(m.orden, m.monto, m.saldo, m.fecha, m.titular)
            for m in db.query(MovimientoBanco).filter(MovimientoBanco.extracto_id == ext.id).all()]
    coincidencias, nuevos = svc.simular_merge(rows, filas_pdf)
    stats = mergear_movimientos(db, ext.id, filas_pdf)
    assert nuevos == stats["agregados"]
    assert (coincidencias, nuevos) == esperado


# ── Validaciones al confirmar ──────────────────────────────────────

def test_saldo_que_no_cierra_pide_confirmacion(client, db, lector):
    b = _listo(client, db)
    b["movimientos"][1]["monto"] = "-300.00"          # la persona tipeó mal
    r = _confirmar(client, _auth(db), b)
    assert r.status_code == 422
    assert r.json()["detail"] == ("El saldo no cierra: hay una diferencia de $ 100,00. "
                                  "Revisá los movimientos o confirmá igual.")
    assert db.get(BorradorExtractoPdf, b["id"]).estado == "listo"
    r = _confirmar(client, _auth(db), b, confirmar_sin_cuadre=True)
    assert r.status_code == 200
    assert r.json()["molde_aprendido"] is False         # no se aprende de algo que no cierra


@pytest.mark.parametrize("cambio,mensaje", [
    ({"fecha": None}, "Fila 2: la fecha falta o no es válida."),
    ({"fecha": "31/02/2026"}, "Fila 2: la fecha falta o no es válida."),
    ({"fecha": "2026-09-03T00:00:00"}, None),
    ({"fecha": "03/09/2026"}, None),
    ({"monto": "0"}, "Fila 2: el importe no puede ser cero."),
    ({"monto": "abc"}, "Fila 2: el importe falta o no es válido."),
    ({"monto": None}, "Fila 2: el importe falta o no es válido."),
    ({"monto": "10000000000.00"}, "Fila 2: el importe es demasiado grande (máximo $ 9.999.999.999,99)."),
    ({"monto": -1e10}, "Fila 2: el importe es demasiado grande (máximo $ 9.999.999.999,99)."),
    ({"saldo": "xx"}, "Fila 2: el saldo no es válido."),
    ({"saldo": "99999999999"}, "Fila 2: el saldo es demasiado grande (máximo $ 9.999.999.999,99)."),
    ({"monto": "-200", "saldo": ""}, None),
    ({"monto": "-1.200,00", "saldo": "1.300,00"}, "El saldo no cierra"),   # formato AR → parse_importe_ar
])
def test_validacion_de_filas(client, db, lector, cambio, mensaje):
    b = _listo(client, db)
    b["movimientos"][1].update(cambio)
    r = _confirmar(client, _auth(db), b)
    if mensaje is None:
        assert r.status_code == 200, r.text
    else:
        assert r.status_code == 422, r.text
        assert isinstance(r.json()["detail"], str) and r.json()["detail"].startswith(mensaje)
        assert db.query(ExtractoBancario).count() == 0
        assert db.get(BorradorExtractoPdf, b["id"]).estado == "listo"


def test_sin_filas_o_demasiadas(client, db, lector, monkeypatch):
    b = _listo(client, db)
    r = client.post(f"/extractos-pdf/borradores/{b['id']}/confirmar", headers=_auth(db),
                    json={**_payload(b), "movimientos": []})
    assert r.status_code == 422 and r.json()["detail"] == "No hay movimientos para guardar."
    monkeypatch.setattr(svc, "MAX_MOVIMIENTOS", 3)
    r = _confirmar(client, _auth(db), b)
    assert r.status_code == 422 and "máximo 3" in r.json()["detail"]


def test_filas_cargadas_a_mano_en_un_borrador_vacio(client, db, lector):
    r = _importar(client, _auth(db), PDF_ESCANEADO, nombre="escaneado.pdf")
    b = r.json()
    b["movimientos"] = [{"fecha": "2026-09-02", "descripcion": "DEPOSITO", "monto": "100,50", "saldo": None}]
    b["saldo_inicial"], b["saldo_final"] = "0", "100.50"
    out = _confirmar(client, _auth(db), b)
    assert out.status_code == 200, out.text
    mov = db.query(MovimientoBanco).one()
    assert mov.monto == Decimal("100.50") and mov.titular == "DEPOSITO"


# ── Formato aprendido ──────────────────────────────────────────────

def test_aprende_el_formato_y_lo_refuerza(client, db, lector):
    b = _listo(client, db)
    out = _confirmar(client, _auth(db), b).json()
    assert out["molde_aprendido"] is True
    molde = db.query(MoldeExtractoPdf).one()
    assert molde.organizacion_id == 1 and molde.firma == FIRMA_GALICIA and molde.confirmaciones == 1
    assert molde.origen == "automatico" and molde.banco_clave == "galicia" and molde.layout["columnas"]
    assert molde.ultimo_uso_at is not None

    # El PDF siguiente del mismo banco se lee con el formato aprendido.
    lector.usar_moldes = True
    b2 = _listo(client, db, PDF_OCT)
    assert b2["metodo"] == "molde" and b2["puede_aprender"] is False
    assert lector.llamadas[-1]["moldes"][0]["firma"] == FIRMA_GALICIA
    out2 = _confirmar(client, _auth(db), b2).json()
    assert out2["molde_aprendido"] is True
    db.expire_all()
    assert db.query(MoldeExtractoPdf).one().confirmaciones == 2

    lista = client.get("/extractos-pdf/moldes", headers=_auth(db)).json()["items"]
    assert lista == [{**lista[0], "id": molde.id, "banco": "Galicia", "banco_clave": "galicia",
                      "origen": "automatico", "confirmaciones": 2}]


def test_no_aprende_si_se_corrigio_mas_del_10_por_ciento(client, db, lector):
    b = _listo(client, db)
    b["movimientos"][0]["fecha"] = "2026-09-01"        # 1 de 4 filas = 25 %
    out = _confirmar(client, _auth(db), b).json()
    assert out["molde_aprendido"] is False
    assert db.query(MoldeExtractoPdf).count() == 0


def test_aprende_si_se_corrigio_hasta_el_10_por_ciento(client, db, lector):
    filas, saldo = [], Decimal("1000.00")
    for i in range(10):
        saldo += Decimal("10.00")
        filas.append((f"2026-09-{i + 1:02d}", f"TRANSF {i}", "10.00", f"{saldo:.2f}"))
    lector.det[PDF_SEP] = _res(filas)
    b = _listo(client, db)
    b["movimientos"][3]["fecha"] = "2026-09-05"        # 1 de 10 = 10 %
    assert _confirmar(client, _auth(db), b).json()["molde_aprendido"] is True
    assert db.query(MoldeExtractoPdf).count() == 1


def test_no_aprende_sin_candidato(client, db, lector):
    lector.det[PDF_SEP] = _res(FILAS_SEP, aprendizaje=None)
    b = _listo(client, db)
    assert b["puede_aprender"] is False
    assert _confirmar(client, _auth(db), b).json()["molde_aprendido"] is False
    assert db.query(MoldeExtractoPdf).count() == 0


def test_borrar_molde_permisos_y_org(client, db, lector):
    _confirmar(client, _auth(db), _listo(client, db))
    molde = db.query(MoldeExtractoPdf).one()
    assert client.get("/extractos-pdf/moldes", headers=_auth(db, "revisor@pdf.test")).status_code == 200
    assert client.get("/extractos-pdf/moldes", headers=_auth(db, "admin2@pdf.test")).json()["items"] == []
    assert client.delete(f"/extractos-pdf/moldes/{molde.id}", headers=_auth(db, "revisor@pdf.test")).status_code == 403
    assert client.delete(f"/extractos-pdf/moldes/{molde.id}", headers=_auth(db, "operador@pdf.test")).status_code == 403
    assert client.delete(f"/extractos-pdf/moldes/{molde.id}", headers=_auth(db, "admin2@pdf.test")).status_code == 404
    r = client.delete(f"/extractos-pdf/moldes/{molde.id}", headers=_auth(db))
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert db.query(MoldeExtractoPdf).count() == 0
    assert db.query(AuditoriaLog).filter(AuditoriaLog.tabla == "moldes_extracto_pdf").count() == 1


# ── Descartar ──────────────────────────────────────────────────────

def test_descartar(client, db, lector):
    b = _listo(client, db)
    r = client.post(f"/extractos-pdf/borradores/{b['id']}/descartar", headers=_auth(db))
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert db.get(BorradorExtractoPdf, b["id"]).estado == "descartado"
    assert client.get("/extractos-pdf/borradores", headers=_auth(db)).json()["items"] == []
    r = _confirmar(client, _auth(db), b)
    assert r.status_code == 409
    # Volver a subirlo crea un borrador nuevo.
    assert _listo(client, db)["id"] != b["id"]


def test_descartar_confirmado_da_409(client, db, lector):
    b = _listo(client, db)
    _confirmar(client, _auth(db), b)
    r = client.post(f"/extractos-pdf/borradores/{b['id']}/descartar", headers=_auth(db))
    assert r.status_code == 409 and isinstance(r.json()["detail"], str)


# ── Permisos y multi-tenant ────────────────────────────────────────

def test_revisor_lee_pero_no_escribe(client, db, lector):
    b = _listo(client, db)
    h = _auth(db, "revisor@pdf.test")
    assert _importar(client, h).status_code == 403
    assert _confirmar(client, h, b).status_code == 403
    assert client.post(f"/extractos-pdf/borradores/{b['id']}/descartar", headers=h).status_code == 403
    assert client.get("/extractos-pdf/borradores", headers=h).status_code == 200
    assert client.get(f"/extractos-pdf/borradores/{b['id']}", headers=h).status_code == 200


def test_operador_puede_importar_y_confirmar(client, db, lector):
    b = _listo(client, db, email="operador@pdf.test")
    assert _confirmar(client, _auth(db, "operador@pdf.test"), b).status_code == 200


def test_otra_org_da_404(client, db, lector):
    b = _listo(client, db)
    h2 = _auth(db, "admin2@pdf.test")
    assert client.get(f"/extractos-pdf/borradores/{b['id']}", headers=h2).status_code == 404
    assert _confirmar(client, h2, b).status_code == 404
    assert client.post(f"/extractos-pdf/borradores/{b['id']}/descartar", headers=h2).status_code == 404
    assert client.get("/extractos-pdf/borradores", headers=h2).json()["items"] == []
    # Un ?org_id= sin permiso se ignora (como en /extractos/upload): sigue siendo su org.
    assert client.get(f"/extractos-pdf/borradores/{b['id']}", headers=h2, params={"org_id": 1}).status_code == 404
    assert db.get(BorradorExtractoPdf, b["id"]).estado == "listo"


def test_superadmin_con_org_id_trabaja_en_esa_org(client, db, lector):
    h = _auth(db, "super@pdf.test")
    b = _listo(client, db, email="super@pdf.test", org_id=2)
    assert db.get(BorradorExtractoPdf, b["id"]).organizacion_id == 2
    # Sin ?org_id= el superadmin está en su org (1): no lo ve.
    assert client.get(f"/extractos-pdf/borradores/{b['id']}", headers=h).status_code == 404
    out = _confirmar(client, h, b, params={"org_id": 2}).json()
    ext = db.get(ExtractoBancario, out["extracto_id"])
    assert ext.organizacion_id == 2
    assert {m.organizacion_id for m in ext.movimientos} == {2}
    assert db.query(MoldeExtractoPdf).one().organizacion_id == 2


def test_listado_de_borradores_por_estado(client, db, lector):
    b = _listo(client, db)
    items = client.get("/extractos-pdf/borradores", headers=_auth(db)).json()["items"]
    assert items == [{**items[0], "id": b["id"], "estado": "listo", "cantidad": 4, "cierra": True}]
    _confirmar(client, _auth(db), b)
    assert client.get("/extractos-pdf/borradores", headers=_auth(db)).json()["items"] == []
    conf = client.get("/extractos-pdf/borradores", headers=_auth(db), params={"estado": "confirmado"}).json()
    assert [i["id"] for i in conf["items"]] == [b["id"]]
    r = client.get("/extractos-pdf/borradores", headers=_auth(db), params={"estado": "otro"})
    assert r.status_code == 422 and isinstance(r.json()["detail"], str)


# ── Helpers puros ──────────────────────────────────────────────────

def test_a_dinero_y_formatos():
    assert svc.a_dinero("-1234.56") == Decimal("-1234.56")
    assert svc.a_dinero("1.234,56-") == Decimal("-1234.56")
    assert svc.a_dinero(1234.5) == Decimal("1234.50")
    assert svc.a_dinero(Decimal("0.005")) == Decimal("0.01")
    assert svc.a_dinero("") is None and svc.a_dinero(None) is None and svc.a_dinero(True) is None
    assert svc.a_dinero(float("nan")) is None and svc.a_dinero("abc") is None
    assert svc.dinero_str(Decimal("-0.00")) == "0.00"
    assert svc.dinero_str(Decimal("1E+3")) == "1000.00"
    assert svc.formato_ar(Decimal("-1234567.5")) == "-1.234.567,50"


def test_huella_igual_a_la_del_excel():
    from app.services.extracto_import import fingerprint
    excel = [{"orden": None, "monto": 750.0}, {"orden": None, "monto": -50.0}, {"orden": None, "monto": 0.1},
             {"orden": None, "monto": 0.2}]
    pdf = [{"orden": None, "monto": Decimal("750.00")}, {"orden": None, "monto": Decimal("-50.00")},
           {"orden": None, "monto": Decimal("0.10")}, {"orden": None, "monto": Decimal("0.20")}]
    assert svc.huella(pdf) == fingerprint(excel)


# ── Punta a punta con el lector real (PDF generado con reportlab) ──

def _pdf_galicia(mes: int, filas, saldo_anterior: str, saldo_final: str) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    _, h = A4
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, h - 50, "Banco de Galicia y Buenos Aires S.A.U.")
    c.setFont("Helvetica", 9)
    c.drawString(40, h - 65, "Resumen de Cuenta Corriente en Pesos")
    c.drawString(40, h - 80, f"Período: 01/{mes:02d}/2026 al 30/{mes:02d}/2026")
    y = h - 120
    for x, titulo in [(40, "Fecha"), (100, "Descripción"), (360, "Débitos"), (440, "Créditos"), (520, "Saldo")]:
        c.drawString(x, y, titulo)
    y -= 15
    c.drawString(100, y, "SALDO ANTERIOR")
    c.drawRightString(560, y, saldo_anterior)
    for fecha, desc, debito, credito, saldo in filas:
        y -= 14
        c.drawString(40, y, fecha)
        c.drawString(100, y, desc)
        if debito:
            c.drawRightString(400, y, debito)
        if credito:
            c.drawRightString(480, y, credito)
        c.drawRightString(560, y, saldo)
    y -= 15
    c.drawString(100, y, "SALDO FINAL")
    c.drawRightString(560, y, saldo_final)
    c.showPage()
    c.save()
    return buf.getvalue()


@pytest.fixture
def client_real(db, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(svc, "lector", None)
    monkeypatch.setattr(svc, "ia_configurada", lambda: False)

    def _override_db():
        yield db
    app.dependency_overrides[get_db] = _override_db
    monkeypatch.setattr(router_mod, "_session_factory", sessionmaker(bind=db.get_bind()))
    yield TestClient(app, raise_server_exceptions=True)
    app.dependency_overrides.pop(get_db, None)


def test_punta_a_punta_con_el_lector_real(client_real, db):
    client = client_real
    sep = _pdf_galicia(9, [
        ("02/09/2026", "TRANSF RECIBIDA PEREZ JUAN", "", "500,00", "1.500,00"),
        ("03/09/2026", "PAGO PROVEEDOR ACME SA", "200,00", "", "1.300,00"),
        ("05/09/2026", "COMISION MANTENIMIENTO", "50,00", "", "1.250,00"),
        ("10/09/2026", "TRANSF RECIBIDA GOMEZ ANA", "", "750,00", "2.000,00"),
    ], "1.000,00", "2.000,00")
    b = _listo(client, db, sep)
    assert b["metodo"] == "automatico" and b["banco"] == "Galicia" and b["puede_aprender"] is True
    assert b["cuadre"]["cierra"] is True and len(b["movimientos"]) == 4
    assert b["periodo_desde"] == "2026-09-01" and b["periodo_hasta"] == "2026-09-30"
    out = _confirmar(client, _auth(db), b)
    assert out.status_code == 200, out.text
    assert out.json()["molde_aprendido"] is True
    molde = db.query(MoldeExtractoPdf).one()
    assert len(molde.firma) <= 64 and molde.confirmaciones == 1

    # Mismo banco, otro mes: se lee con el formato aprendido.
    octubre = _pdf_galicia(10, [
        ("01/10/2026", "TRANSF RECIBIDA LOPEZ MARIA", "", "300,00", "2.300,00"),
        ("06/10/2026", "DEBITO AUTOMATICO SEGURO", "100,00", "", "2.200,00"),
    ], "2.000,00", "2.200,00")
    b2 = _listo(client, db, octubre, nombre="resumen-oct.pdf")
    assert b2["metodo"] == "molde" and b2["cuadre"]["cierra"] is True
    assert b2["duplicado"] is None
    assert _confirmar(client, _auth(db), b2).json()["molde_aprendido"] is True
    db.expire_all()
    assert db.query(MoldeExtractoPdf).one().confirmaciones == 2
    assert db.query(ExtractoBancario).count() == 2

    # El mismo PDF otra vez: ya importado, no se duplica nada.
    r = _importar(client, _auth(db), sep)
    assert r.json()["estado"] == "confirmado" and r.json()["id"] == b["id"]
    assert db.query(MovimientoBanco).count() == 6


# ── Regresiones de la revisión adversaria ──────────────────────────

@pytest.fixture
def client_500(db, lector, monkeypatch):
    """Cliente que devuelve los 500 como respuesta (para comprobar que no los hay)."""
    def _override_db():
        yield db
    app.dependency_overrides[get_db] = _override_db
    monkeypatch.setattr(router_mod, "_session_factory", sessionmaker(bind=db.get_bind()))
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.pop(get_db, None)


@pytest.mark.parametrize("monto", ["1" + "0" * 30, 1e30, "1.000.000.000.000.000.000.000.000.000,00", "12000000000"])
def test_importe_absurdo_al_confirmar_da_422(client_500, db, lector, monto):
    b = _listo(client_500, db)
    body = _payload(b)
    body["movimientos"][0]["monto"] = monto
    r = client_500.post(f"/extractos-pdf/borradores/{b['id']}/confirmar", headers=_auth(db), json=body)
    assert r.status_code == 422 and "Fila 1" in r.json()["detail"]
    body = _payload(b, saldo_inicial="1" + "0" * 40)
    r = client_500.post(f"/extractos-pdf/borradores/{b['id']}/confirmar", headers=_auth(db), json=body)
    assert r.status_code == 422 and "saldo inicial" in r.json()["detail"]


def test_lectura_con_numero_absurdo_no_rompe_importar(client_500, db, lector):
    res = _res(FILAS_SEP)
    res["movimientos"][0]["saldo"] = Decimal("1E+40")
    lector.det[PDF_SEP] = res
    r = _importar(client_500, _auth(db))
    assert r.status_code == 200 and r.json()["movimientos"][0]["saldo"] is None


def test_agregar_pdf_con_filas_mas_viejas_que_el_extracto_avisa(client, db, lector):
    """El extracto tiene solo desde el día 5 (un "Últimos movimientos"); el PDF del mes
    trae además el 2 y el 3. El merge de UM solo agrega lo más nuevo: la respuesta
    tiene que decir que esas filas no se agregaron, no que "ya los tenía todos"."""
    ext_id = _subir_excel(client, _auth(db), list(reversed(FILAS_SEP[2:])))
    b = _listo(client, db)
    assert b["duplicado"]["tipo"] == "solapado" and b["duplicado"]["anteriores"] == 2
    out = _confirmar(client, _auth(db), b, destino="existente", extracto_id=ext_id).json()
    assert out["agregados"] == 0 and out["no_agregados"] == 2
    assert "ya los tenía todos" not in out["mensaje"] and "son anteriores" in out["mensaje"]


def test_si_falla_la_auditoria_el_agregado_queda_confirmado_y_con_asiento(client, db, lector, monkeypatch):
    ext_id = _subir_excel(client, _auth(db), list(reversed(FILAS_SEP[:3])))
    lector.det[PDF_SEP] = _res(FILAS_SOLAPADAS)
    b = _listo(client, db)
    asientos = []
    monkeypatch.setattr(svc, "registrar_asiento_um",
                        lambda db_, *, extracto, nuevo_lote, usuario_id, modo_asiento=None:
                        asientos.append(nuevo_lote) or True)

    def _log_roto(*a, **k):
        raise RuntimeError("se cortó la conexión")
    monkeypatch.setattr(svc, "registrar_log", _log_roto)

    out = _confirmar(client, _auth(db), b, destino="existente", extracto_id=ext_id).json()

    assert out["agregados"] == 2 and asientos
    db.expire_all()
    assert db.get(BorradorExtractoPdf, b["id"]).estado == "confirmado"


def test_reintento_tras_un_corte_genera_el_asiento_que_falto(client, db, lector, monkeypatch):
    """Se cae todo justo después del merge (que commitea solo): el reintento no
    agrega nada nuevo, pero genera el asiento del lote que quedó sin asiento y
    cuenta como agregados los movimientos de ese intento."""
    ext_id = _subir_excel(client, _auth(db), list(reversed(FILAS_SEP[:3])))
    lector.det[PDF_SEP] = _res(FILAS_SOLAPADAS)
    b = _listo(client, db)
    asientos = []
    llamadas = {"n": 0}

    def _asiento(db_, *, extracto, nuevo_lote, usuario_id, modo_asiento=None):
        llamadas["n"] += 1
        if llamadas["n"] == 1:
            raise RuntimeError("se cayó el servidor")
        asientos.append(nuevo_lote)
        return True
    monkeypatch.setattr(svc, "registrar_asiento_um", _asiento)

    with pytest.raises(RuntimeError):
        _confirmar(client, _auth(db), b, destino="existente", extracto_id=ext_id)
    db.expire_all()
    assert db.get(BorradorExtractoPdf, b["id"]).estado == "listo"
    assert db.query(MovimientoBanco).filter(MovimientoBanco.extracto_id == ext_id).count() == 5

    out = _confirmar(client, _auth(db), b, destino="existente", extracto_id=ext_id).json()
    assert asientos and out["agregados"] == 2
    assert db.query(MovimientoBanco).filter(MovimientoBanco.extracto_id == ext_id).count() == 5


def _cargar_como_excel_macro(db, filas, nombre="macro-sep.xlsx"):
    """Como el upload de Excel de Macro: el número de orden del banco entra en la huella,
    así que la huella del PDF (sin orden) no coincide."""
    movs = svc.a_filas_parser([{"fecha": date.fromisoformat(f), "descripcion": d, "monto": Decimal(m),
                                "saldo": Decimal(s)} for (f, d, m, s) in filas], "asc")
    for i, m in enumerate(movs):
        m["orden"] = 9000 - i
    return crear_extracto_con_movimientos(db, movs=movs, nombre_archivo=nombre, banco="Galicia",
                                          huella=f"macro-{nombre}", org_id=1, usuario_id=1)


def test_pdf_de_un_mes_archivado_no_duplica_el_extracto(client, db, lector):
    ext = _cargar_como_excel_macro(db, FILAS_SEP)
    ext.archivado_at = datetime(2026, 10, 1)          # mes cerrado → archivado (v3.28)
    db.commit()
    b = _listo(client, db)
    assert b["duplicado"]["tipo"] == "mismos_movimientos" and b["duplicado"]["archivado"] is True
    out = _confirmar(client, _auth(db), b).json()
    assert out["ya_existia"] is True and db.query(ExtractoBancario).count() == 1


def test_pdf_de_un_extracto_viejo_no_duplica(client, db, lector):
    _cargar_como_excel_macro(db, FILAS_SEP)
    for i in range(12):   # otras cuentas / meses cargados después
        crear_extracto_con_movimientos(
            db, movs=[{"orden": None, "fecha": date(2026, 10, 1), "mes": "10", "titular": f"X{i}",
                       "monto": Decimal(10 + i), "saldo": Decimal("1"), "cliente_acreditado": None,
                       "fecha_acred": None}],
            nombre_archivo=f"otro{i}.xlsx", banco="BBVA", huella=f"h{i}", org_id=1, usuario_id=1)
    b = _listo(client, db)
    assert b["duplicado"]["tipo"] == "mismos_movimientos"
    _confirmar(client, _auth(db), b)
    assert db.query(ExtractoBancario).filter(ExtractoBancario.banco == "Galicia").count() == 1


@pytest.mark.parametrize("sep,octubre", [
    # Cuenta de débito automático: el dueño transfiere justo lo que se debita cada mes.
    ([("2026-09-05", "TRANSF PROPIA", "121.00", "5121.00"), ("2026-09-30", "COMISION", "-100.00", "5021.00"),
      ("2026-09-30", "IVA 21%", "-21.00", "5000.00")],
     [("2026-10-05", "TRANSF PROPIA", "121.00", "5121.00"), ("2026-10-31", "COMISION", "-100.00", "5021.00"),
      ("2026-10-31", "IVA 21%", "-21.00", "5000.00")]),
    # Misma cantidad y suma, la mitad de las filas con el mismo (importe, saldo).
    ([("2026-09-01", "TRANSF A", "500.00", "5500.00"), ("2026-09-02", "PAGO B", "-500.00", "5000.00"),
      ("2026-09-03", "TRANSF C", "300.00", "5300.00"), ("2026-09-04", "PAGO D", "-300.00", "5000.00")],
     [("2026-10-01", "TRANSF A", "500.00", "5500.00"), ("2026-10-02", "PAGO B", "-500.00", "5000.00"),
      ("2026-10-03", "TRANSF X", "250.00", "5250.00"), ("2026-10-04", "PAGO Y", "-250.00", "5000.00")]),
])
def test_otro_mes_con_los_mismos_importes_y_saldos_no_se_pierde(client, db, lector, sep, octubre):
    lector.det[PDF_SEP] = _res(sep, saldo_inicial="5000.00")
    lector.det[PDF_OCT] = _res(octubre, saldo_inicial="5000.00")
    _confirmar(client, _auth(db), _listo(client, db))
    b2 = _listo(client, db, PDF_OCT, nombre="resumen-oct.pdf")
    assert b2["duplicado"] is None
    out = _confirmar(client, _auth(db), b2).json()
    assert out["ya_existia"] is False and out["agregados"] == len(octubre)
    assert db.query(ExtractoBancario).count() == 2
