"""Grilla de vencimientos por organización (benchmark Ola 2, punto 5).

- Calendario general (no por org) cargado mes a mes desde la web de ARCA:
  impuesto + período + bloque de terminación de CUIT → fecha.
- Monotributo: día 20 del mes, o el día hábil siguiente si cae sábado/domingo
  (salvo que el calendario cargado diga otra cosa).
- Qué le toca a cada org sale de los módulos activos (o de configuracion["obligaciones"]).
- "Presentado" sale de los módulos (IVA, IIBB, F931) o de una marca manual.
"""
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.contabilidad import PlanCuenta
from app.models.iibb import IIBBConfig, ProyeccionIIBB
from app.models.iva_liquidacion import LiquidacionIva
from app.models.monotributo import MonotributoConfig
from app.models.organizacion import Organizacion
from app.models.sueldos import ConfigSueldos, LiquidacionSueldoPeriodo
from app.models.user import User
from app.models.vencimientos import CalendarioVencimiento, VencimientoMarcado
from app.services import vencimientos as svc
from app.services.auth import create_access_token, get_password_hash

HOY = date(2026, 10, 21)   # miércoles


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    s = sessionmaker(bind=engine)()
    s.add_all([
        Organizacion(id=1, nombre="Estudio", configuracion={"cuit": "30700000008"}),   # termina en 8
        Organizacion(id=2, nombre="Cliente Dos", configuracion={"cuit": "20111111112"}),  # termina en 2
        Organizacion(id=3, nombre="Ajena", configuracion={}),
    ])
    s.commit()
    for email, oid, rol, supa, permitidas in [
        ("supa@v.test", 1, "admin", True, []),
        ("admin@v.test", 1, "admin", False, [2]),
        ("contador@v.test", 1, "contador", False, [2]),
        ("revisor@v.test", 1, "revisor", False, []),
    ]:
        s.add(User(email=email, full_name=email, hashed_password=get_password_hash("pw"),
                   organizacion_id=oid, is_active=True, role=rol, is_superadmin=supa,
                   allowed_org_ids=permitidas))
    s.commit()
    yield s
    s.close()


@pytest.fixture
def client(db):
    def _override():
        yield db
    app.dependency_overrides[get_db] = _override
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)


def _auth(db, email):
    u = db.query(User).filter(User.email == email).first()
    return {"Authorization": f"Bearer {create_access_token({'sub': u.email, 'user_id': u.id, 'role': u.role})}"}


def _cargar_octubre(db):
    """IVA, F931 y Convenio Multilateral del período 2026-09 (vencen en octubre)."""
    filas = [
        ("iva", 0, 1, 19), ("iva", 2, 3, 20), ("iva", 4, 5, 21), ("iva", 6, 7, 22), ("iva", 8, 9, 23),
        ("f931", 0, 3, 9), ("f931", 4, 6, 13), ("f931", 7, 9, 14),
        ("iibb_cm", 0, 2, 15), ("iibb_cm", 3, 5, 16), ("iibb_cm", 6, 7, 19), ("iibb_cm", 8, 9, 20),
    ]
    for imp, desde, hasta, dia in filas:
        db.add(CalendarioVencimiento(impuesto=imp, periodo="2026-09", terminacion_desde=desde,
                                     terminacion_hasta=hasta, fecha=date(2026, 10, dia), fuente="test"))
    db.commit()


def _usa_iva(db, org_id):
    db.add(PlanCuenta(organizacion_id=org_id, codigo="4-1-1", nombre="Ventas", tipo="ingreso",
                      tasa_iva=0.21))
    db.commit()


# ── Fechas ───────────────────────────────────────────────────────────────────

def test_dia_habil_siguiente():
    assert svc.dia_habil(date(2026, 6, 20)) == date(2026, 6, 22)    # sábado → lunes
    assert svc.dia_habil(date(2026, 9, 20)) == date(2026, 9, 21)    # domingo → lunes
    assert svc.dia_habil(date(2026, 10, 20)) == date(2026, 10, 20)  # martes


def test_monotributo_dia_20_o_habil_siguiente(db):
    assert svc.fecha_vencimiento(db, "monotributo", "2026-10", "30700000008") == date(2026, 10, 20)
    assert svc.fecha_vencimiento(db, "monotributo", "2026-06", "30700000008") == date(2026, 6, 22)


def test_monotributo_respeta_el_calendario_cargado(db):
    db.add(CalendarioVencimiento(impuesto="monotributo", periodo="2026-10", terminacion_desde=0,
                                 terminacion_hasta=9, fecha=date(2026, 10, 23), fuente="prórroga"))
    db.commit()
    assert svc.fecha_vencimiento(db, "monotributo", "2026-10", "30700000008") == date(2026, 10, 23)


def test_fecha_por_terminacion_de_cuit(db):
    _cargar_octubre(db)
    assert svc.fecha_vencimiento(db, "iva", "2026-09", "30700000008") == date(2026, 10, 23)  # 8
    assert svc.fecha_vencimiento(db, "iva", "2026-09", "20111111112") == date(2026, 10, 20)  # 2
    assert svc.fecha_vencimiento(db, "f931", "2026-09", "20111111112") == date(2026, 10, 9)
    assert svc.fecha_vencimiento(db, "iibb_cm", "2026-09", "30700000008") == date(2026, 10, 20)
    assert svc.fecha_vencimiento(db, "iva", "2026-10", "30700000008") is None   # sin cargar


def test_periodo_que_vence_en_el_mes():
    assert svc.periodo_fiscal("iva", "2026-10") == "2026-09"
    assert svc.periodo_fiscal("f931", "2026-01") == "2025-12"
    assert svc.periodo_fiscal("monotributo", "2026-10") == "2026-10"


# ── Qué le toca a cada organización ──────────────────────────────────────────

def test_obligaciones_segun_modulos_activos(db):
    assert svc.obligaciones_org(db, 1) == []
    _usa_iva(db, 1)
    db.add_all([
        IIBBConfig(organizacion_id=1, activo=True, modo="convenio_multilateral"),
        ConfigSueldos(organizacion_id=1, activo=True),
    ])
    db.commit()
    assert svc.obligaciones_org(db, 1) == ["iva", "iibb_cm", "f931"]


def test_monotributista_no_tiene_iva_y_iibb_local_no_entra(db):
    _usa_iva(db, 2)
    db.add_all([
        MonotributoConfig(organizacion_id=2, activo=True),
        IIBBConfig(organizacion_id=2, activo=True, modo="simple"),
    ])
    db.commit()
    assert svc.obligaciones_org(db, 2) == ["monotributo"]


def test_configuracion_explicita_manda(db):
    org = db.get(Organizacion, 3)
    org.configuracion = {"obligaciones": ["monotributo", "f931", "inventado"]}
    db.commit()
    assert svc.obligaciones_org(db, 3) == ["monotributo", "f931"]


# ── Grilla ───────────────────────────────────────────────────────────────────

def _celda(fila, impuesto):
    return next(c for c in fila["obligaciones"] if c["impuesto"] == impuesto)


def test_grilla_estados(db):
    _cargar_octubre(db)
    _usa_iva(db, 1)
    _usa_iva(db, 2)
    db.add(ConfigSueldos(organizacion_id=2, activo=True))
    db.commit()
    filas = {f["organizacion_id"]: f for f in svc.grilla(db, [1, 2], "2026-10", hoy=HOY)}

    iva1 = _celda(filas[1], "iva")          # vence 23/10, hoy 21/10
    assert iva1["periodo"] == "2026-09"
    assert iva1["fecha"] == date(2026, 10, 23)
    assert iva1["estado"] == "proximo"
    assert _celda(filas[2], "iva")["estado"] == "vencido"      # venció 20/10
    assert _celda(filas[2], "f931")["estado"] == "vencido"     # venció 09/10


def test_grilla_presentado_por_modulo_y_manual(db):
    _cargar_octubre(db)
    _usa_iva(db, 1)
    db.add_all([
        IIBBConfig(organizacion_id=1, activo=True, modo="convenio_multilateral"),
        ConfigSueldos(organizacion_id=1, activo=True),
        LiquidacionIva(organizacion_id=1, periodo="2026-09", estado="presentada"),
        ProyeccionIIBB(organizacion_id=1, periodo="2026-09", estado="presentado"),
        LiquidacionSueldoPeriodo(organizacion_id=1, periodo="2026-09", estado="aprobado"),
    ])
    db.commit()
    fila = svc.grilla(db, [1], "2026-10", hoy=HOY)[0]
    assert _celda(fila, "iva")["estado"] == "presentado"
    assert _celda(fila, "iva")["presentado_por"] == "modulo"
    assert _celda(fila, "iibb_cm")["estado"] == "presentado"
    assert _celda(fila, "f931")["estado"] == "vencido"   # aprobado no es presentado

    db.add(VencimientoMarcado(organizacion_id=1, impuesto="f931", periodo="2026-09", marcado_por=1))
    db.commit()
    f931 = _celda(svc.grilla(db, [1], "2026-10", hoy=HOY)[0], "f931")
    assert f931["estado"] == "presentado" and f931["presentado_por"] == "manual"


def test_grilla_sin_cuit_o_sin_calendario(db):
    _usa_iva(db, 3)   # org 3 no tiene CUIT
    sin_cuit = _celda(svc.grilla(db, [3], "2026-10", hoy=HOY)[0], "iva")
    assert sin_cuit["fecha"] is None and sin_cuit["motivo"] == "sin_cuit"
    _usa_iva(db, 1)
    sin_cal = _celda(svc.grilla(db, [1], "2026-11", hoy=HOY)[0], "iva")
    assert sin_cal["fecha"] is None and sin_cal["motivo"] == "sin_calendario"
    assert sin_cal["estado"] == "pendiente"


def test_pendientes_proximos_para_el_aviso(db):
    _cargar_octubre(db)
    _usa_iva(db, 1)   # vence 23/10 → dentro de 3 días
    _usa_iva(db, 2)   # venció 20/10 → no es "próximo"
    db.add(MonotributoConfig(organizacion_id=3, activo=True))
    db.commit()
    proximos = svc.pendientes_proximos(db, hoy=HOY, dias=3)
    assert [(p["organizacion_id"], p["impuesto"]) for p in proximos] == [(1, "iva")]


def test_sembrar_calendario_inicial_es_idempotente(db):
    svc.sembrar_calendario_inicial(db)
    n = db.query(CalendarioVencimiento).count()
    assert n > 0
    svc.sembrar_calendario_inicial(db)
    assert db.query(CalendarioVencimiento).count() == n
    assert svc.fecha_vencimiento(db, "iva", "2026-09", "30700000008") == date(2026, 10, 23)


# ── Endpoints ────────────────────────────────────────────────────────────────

def test_grilla_endpoint_solo_orgs_accesibles(client, db):
    r = client.get("/vencimientos/grilla?mes=2026-10", headers=_auth(db, "admin@v.test"))
    assert r.status_code == 200, r.text
    assert [f["organizacion_id"] for f in r.json()["filas"]] == [1, 2]
    r = client.get("/vencimientos/grilla?mes=2026-10", headers=_auth(db, "supa@v.test"))
    assert [f["organizacion_id"] for f in r.json()["filas"]] == [1, 2, 3]


def test_grilla_mes_invalido_422(client, db):
    r = client.get("/vencimientos/grilla?mes=2026-13", headers=_auth(db, "admin@v.test"))
    assert r.status_code == 422


def test_calendario_solo_superadmin_lo_carga(client, db):
    body = {"impuesto": "iva", "periodo": "2026-10", "fuente": "argentina.gob.ar/arca/vencimientos",
            "fechas": [{"terminacion_desde": d, "terminacion_hasta": d + 1, "fecha": f"2026-11-{18 + d // 2}"}
                       for d in (0, 2, 4, 6, 8)]}
    assert client.put("/vencimientos/calendario", json=body, headers=_auth(db, "admin@v.test")).status_code == 403
    r = client.put("/vencimientos/calendario", json=body, headers=_auth(db, "supa@v.test"))
    assert r.status_code == 200, r.text
    assert svc.fecha_vencimiento(db, "iva", "2026-10", "30700000008") == date(2026, 11, 22)
    # recargar el mismo período reemplaza (no duplica)
    body["fechas"][4]["fecha"] = "2026-11-25"
    client.put("/vencimientos/calendario", json=body, headers=_auth(db, "supa@v.test"))
    assert db.query(CalendarioVencimiento).filter_by(impuesto="iva", periodo="2026-10").count() == 5
    assert svc.fecha_vencimiento(db, "iva", "2026-10", "30700000008") == date(2026, 11, 25)
    r = client.get("/vencimientos/calendario?periodo=2026-10", headers=_auth(db, "revisor@v.test"))
    assert len(r.json()) == 5


def test_calendario_bloques_deben_cubrir_0_a_9_sin_pisarse(client, db):
    h = _auth(db, "supa@v.test")
    base = {"impuesto": "f931", "periodo": "2026-10", "fuente": "x"}
    faltan = {**base, "fechas": [{"terminacion_desde": 0, "terminacion_hasta": 5, "fecha": "2026-11-09"}]}
    pisan = {**base, "fechas": [{"terminacion_desde": 0, "terminacion_hasta": 5, "fecha": "2026-11-09"},
                                {"terminacion_desde": 5, "terminacion_hasta": 9, "fecha": "2026-11-10"}]}
    imp_mal = {**base, "impuesto": "ganancias",
               "fechas": [{"terminacion_desde": 0, "terminacion_hasta": 9, "fecha": "2026-11-09"}]}
    for body in (faltan, pisan, imp_mal):
        assert client.put("/vencimientos/calendario", json=body, headers=h).status_code == 422


def test_marcar_y_desmarcar_presentado(client, db):
    h = _auth(db, "contador@v.test")
    body = {"organizacion_id": 2, "impuesto": "monotributo", "periodo": "2026-10"}
    r = client.post("/vencimientos/marcar", json=body, headers=h)
    assert r.status_code == 200, r.text
    assert db.query(VencimientoMarcado).filter_by(organizacion_id=2).count() == 1
    # repetir no duplica
    client.post("/vencimientos/marcar", json=body, headers=h)
    assert db.query(VencimientoMarcado).filter_by(organizacion_id=2).count() == 1
    r = client.request("DELETE", "/vencimientos/marcar", json=body, headers=h)
    assert r.status_code == 200
    assert db.query(VencimientoMarcado).count() == 0


def test_marcar_org_ajena_o_sin_permiso(client, db):
    body = {"organizacion_id": 3, "impuesto": "iva", "periodo": "2026-09"}
    assert client.post("/vencimientos/marcar", json=body, headers=_auth(db, "contador@v.test")).status_code == 403
    body["organizacion_id"] = 1
    assert client.post("/vencimientos/marcar", json=body, headers=_auth(db, "revisor@v.test")).status_code == 403


def test_aviso_diario_incluye_vencimientos(db, monkeypatch):
    from datetime import datetime as _dt
    from app.services import backup_scheduler, push_service

    _cargar_octubre(db)
    _usa_iva(db, 1)   # vence 23/10
    enviados = []
    monkeypatch.setattr(backup_scheduler, "SessionLocal", lambda: db)
    monkeypatch.setattr(db, "close", lambda: None)
    monkeypatch.setattr(push_service, "send_push_to_all",
                        lambda _db, titulo, cuerpo, url="/": enviados.append(cuerpo) or 1)

    class _Reloj(_dt):
        @classmethod
        def now(cls, tz=None):
            return _dt(2026, 10, 21, 10, 0, tzinfo=tz)
    monkeypatch.setattr("datetime.datetime", _Reloj)

    backup_scheduler._run_alertas_push()
    assert enviados and "1 vencimiento impositivo en 3 días sin presentar" in enviados[0]
