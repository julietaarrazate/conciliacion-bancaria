"""Tests del módulo Liquidación REAL de IVA (Excel "Mis Comprobantes" de ARCA).

Cubre:
  - parser de Excel sintético (emitidos y recibidos, formato ARCA exacto),
    incluyendo NC tipo 3 y un monto None.
  - import con dedup en re-import y filtro por período.
  - toggle incluido cambia los totales.
  - cadena de liquidación de 2 períodos (herencia automática de saldo técnico).
  - crédito > débito acumula saldo técnico.
  - débito > crédito con retenciones que sobran → libre disponibilidad.
  - presentada → recalcular = 409.
  - aislamiento multi-tenant (org 2 no ve comprobantes de org 3).
"""
import io
from decimal import Decimal

import openpyxl
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.services.auth import get_password_hash, create_access_token
from app.services.mis_comprobantes_parser import parsear_mis_comprobantes
from app.services.iva_liquidacion_service import calcular_liquidacion
from app.models.organizacion import Organizacion
from app.models.user import User
from app.models.iva_liquidacion import ComprobanteIva


# ── Headers exactos del formato ARCA ───────────────────────────────

_H_EMITIDOS = [
    "Fecha", "Tipo", "Punto de Venta", "Número Desde", "Número Hasta",
    "Cód. Autorización", "Tipo Doc. Receptor", "Nro. Doc. Receptor",
    "Denominación Receptor", "Tipo Cambio", "Moneda",
    "Neto Grav. IVA 0%", "IVA 2,5%", "Neto Grav. IVA 2,5%", "IVA 5%",
    "Neto Grav. IVA 5%", "IVA 10,5%", "Neto Grav. IVA 10,5%", "IVA 21%",
    "Neto Grav. IVA 21%", "IVA 27%", "Neto Grav. IVA 27%",
    "Neto Gravado Total", "Neto No Gravado", "Op. Exentas", "Otros Tributos",
    "Total IVA", "Imp. Total",
]

_H_RECIBIDOS = [
    "Fecha", "Tipo", "Punto de Venta", "Número Desde", "Número Hasta",
    "Cód. Autorización", "Tipo Doc. Emisor", "Nro. Doc. Emisor",
    "Denominación Emisor", "Tipo Doc. Receptor", "Nro. Doc. Receptor",
    "Tipo Cambio", "Moneda",
    "Neto Grav. IVA 0%", "IVA 2,5%", "Neto Grav. IVA 2,5%", "IVA 5%",
    "Neto Grav. IVA 5%", "IVA 10,5%", "Neto Grav. IVA 10,5%", "IVA 21%",
    "Neto Grav. IVA 21%", "IVA 27%", "Neto Grav. IVA 27%",
    "Neto Gravado Total", "Neto No Gravado", "Op. Exentas", "Otros Tributos",
    "Total IVA", "Imp. Total",
]


def _build_xlsx(titulo, headers, filas):
    """Genera un .xlsx en memoria imitando el formato ARCA.

    filas: lista de dicts {header: valor}. Los headers ausentes quedan None.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append([titulo] + [None] * (len(headers) - 1))
    ws.append(headers)
    for fila in filas:
        ws.append([fila.get(h) for h in headers])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _fila_emitido(fecha, tipo, pv, num, cuit, denom, iva21=None, neto21=None,
                  total_iva=None, imp_total=None):
    return {
        "Fecha": fecha, "Tipo": tipo, "Punto de Venta": pv,
        "Número Desde": num, "Número Hasta": num, "Cód. Autorización": 12345,
        "Tipo Doc. Receptor": "CUIT", "Nro. Doc. Receptor": cuit,
        "Denominación Receptor": denom, "Tipo Cambio": 1, "Moneda": "$",
        "IVA 21%": iva21, "Neto Grav. IVA 21%": neto21,
        "Neto Gravado Total": neto21, "Total IVA": total_iva, "Imp. Total": imp_total,
    }


def _fila_recibido(fecha, tipo, pv, num, cuit, denom, iva21=None, neto21=None,
                   total_iva=None, imp_total=None):
    return {
        "Fecha": fecha, "Tipo": tipo, "Punto de Venta": pv,
        "Número Desde": num, "Número Hasta": num, "Cód. Autorización": 12345,
        "Tipo Doc. Emisor": "CUIT", "Nro. Doc. Emisor": cuit,
        "Denominación Emisor": denom,
        "Tipo Doc. Receptor": "CUIT", "Nro. Doc. Receptor": 30716892871,
        "Tipo Cambio": 1, "Moneda": "$",
        "IVA 21%": iva21, "Neto Grav. IVA 21%": neto21,
        "Neto Gravado Total": neto21, "Total IVA": total_iva, "Imp. Total": imp_total,
    }


# ── Fixtures ───────────────────────────────────────────────────────

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

    for oid, nombre in [(1, "Org1"), (2, "Org2"), (3, "Org3")]:
        session.add(Organizacion(id=oid, nombre=nombre))
    session.commit()

    # admin org 1 (superadmin False, rol admin → todos los permisos de contabilidad)
    admin = User(
        email="admin@liq.test", full_name="Admin",
        hashed_password=get_password_hash("pw123"),
        organizacion_id=1, is_active=True, role="admin", is_superadmin=False,
    )
    # superadmin para tests multi-org
    supa = User(
        email="supa@liq.test", full_name="Supa",
        hashed_password=get_password_hash("pw123"),
        organizacion_id=1, is_active=True, role="admin", is_superadmin=True,
    )
    session.add_all([admin, supa])
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
    u = db.query(User).filter(User.email == email).first()
    return create_access_token({"sub": u.email, "user_id": u.id, "role": u.role})


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# ── Parser ─────────────────────────────────────────────────────────

def test_parser_emitidos():
    xlsx = _build_xlsx(
        "Mis Comprobantes Emitidos - CUIT 30716892871", _H_EMITIDOS,
        [
            _fila_emitido("31/05/2026", "1 - Factura A", 2, 182, 30716636166,
                          "VARIETALES SRL", 17151.77, 81675.10, 17151.77, 98826.87),
            # NC tipo 3 (Nota de Crédito A)
            _fila_emitido("20/05/2026", "3 - Nota de Crédito A", 2, 5, 30716636166,
                          "VARIETALES SRL", 2100.00, 10000.00, 2100.00, 12100.00),
            # monto None en Total IVA → debe normalizarse a 0
            _fila_emitido("15/05/2026", "6 - Factura B", 3, 40, 27413298755,
                          "CONSUMIDOR", None, None, None, 5000),
        ],
    )
    filas = parsear_mis_comprobantes(xlsx, "emitido")
    assert len(filas) == 3
    f0 = filas[0]
    assert f0["tipo_codigo"] == 1
    assert f0["tipo_desc"] == "1 - Factura A"
    assert f0["punto_venta"] == 2
    assert f0["numero"] == 182
    assert f0["cuit_contraparte"] == "30716636166"
    assert f0["denominacion"] == "VARIETALES SRL"
    assert f0["total_iva"] == Decimal("17151.77")
    assert f0["detalle_alicuotas"]["21%"]["iva"] == 17151.77
    assert filas[1]["tipo_codigo"] == 3  # NC
    # None → 0
    assert filas[2]["total_iva"] == Decimal("0.00")


def test_parser_recibidos_usa_emisor():
    xlsx = _build_xlsx(
        "Mis Comprobantes Recibidos - CUIT 30716892871", _H_RECIBIDOS,
        [
            _fila_recibido("06/05/2026", "1 - Factura A", 10, 999, 30690783521,
                           "INTERBANKING SA", 4200.00, 20000.00, 4200.00, 24200.00),
        ],
    )
    filas = parsear_mis_comprobantes(xlsx, "recibido")
    assert len(filas) == 1
    assert filas[0]["cuit_contraparte"] == "30690783521"  # del EMISOR
    assert filas[0]["denominacion"] == "INTERBANKING SA"
    assert filas[0]["total_iva"] == Decimal("4200.00")


def test_parser_archivo_equivocado():
    xlsx = _build_xlsx("Otra cosa cualquiera", _H_EMITIDOS, [])
    with pytest.raises(ValueError):
        parsear_mis_comprobantes(xlsx, "emitido")


# ── Import + dedup + período ───────────────────────────────────────

def _importar(client, token, xlsx, direccion, periodo, fname="test.xlsx"):
    return client.post(
        f"/iva/comprobantes/importar?direccion={direccion}&periodo={periodo}",
        headers=_auth(token),
        files={"file": (fname, xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )


def test_import_dedup_y_periodo(db, client):
    token = _token(db, "admin@liq.test")
    xlsx = _build_xlsx(
        "Mis Comprobantes Emitidos - CUIT 30716892871", _H_EMITIDOS,
        [
            _fila_emitido("10/05/2026", "1 - Factura A", 2, 100, 30111111119,
                          "CLIENTE 1", 2100, 10000, 2100, 12100),
            _fila_emitido("15/05/2026", "1 - Factura A", 2, 101, 30222222229,
                          "CLIENTE 2", 4200, 20000, 4200, 24200),
            # fuera de período (junio)
            _fila_emitido("03/06/2026", "1 - Factura A", 2, 102, 30333333339,
                          "CLIENTE 3", 6300, 30000, 6300, 36300),
        ],
    )
    r = _importar(client, token, xlsx, "emitido", "2026-05")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["importados"] == 2
    assert data["fuera_de_periodo"] == 1
    assert data["duplicados"] == 0

    # re-import → los 2 ya existen = duplicados
    r2 = _importar(client, token, xlsx, "emitido", "2026-05")
    assert r2.json()["importados"] == 0
    assert r2.json()["duplicados"] == 2

    assert db.query(ComprobanteIva).filter(ComprobanteIva.organizacion_id == 1).count() == 2


def test_toggle_cambia_totales(db, client):
    token = _token(db, "admin@liq.test")
    xlsx = _build_xlsx(
        "Mis Comprobantes Emitidos - CUIT 30716892871", _H_EMITIDOS,
        [
            _fila_emitido("10/05/2026", "1 - Factura A", 2, 100, 30111111119,
                          "C1", 2100, 10000, 2100, 12100),
            _fila_emitido("11/05/2026", "1 - Factura A", 2, 101, 30222222229,
                          "C2", 4200, 20000, 4200, 24200),
        ],
    )
    _importar(client, token, xlsx, "emitido", "2026-05")

    r = client.get("/iva/comprobantes?periodo=2026-05&direccion=emitido", headers=_auth(token))
    assert r.status_code == 200
    body = r.json()
    assert body["totales"]["debito_incluido"] == 6300.0
    cid = body["items"][0]["id"]

    # excluir el primero (2100)
    rp = client.patch(f"/iva/comprobantes/{cid}", json={"incluido": False}, headers=_auth(token))
    assert rp.status_code == 200
    r2 = client.get("/iva/comprobantes?periodo=2026-05&direccion=emitido", headers=_auth(token))
    assert r2.json()["totales"]["debito_incluido"] == 4200.0


def test_delete_comprobante(db, client):
    token = _token(db, "admin@liq.test")
    xlsx = _build_xlsx(
        "Mis Comprobantes Emitidos - CUIT 30716892871", _H_EMITIDOS,
        [_fila_emitido("10/05/2026", "1 - Factura A", 2, 100, 30111111119,
                       "C1", 2100, 10000, 2100, 12100)],
    )
    _importar(client, token, xlsx, "emitido", "2026-05")
    cid = db.query(ComprobanteIva).first().id
    r = client.delete(f"/iva/comprobantes/{cid}", headers=_auth(token))
    assert r.status_code == 200
    assert db.query(ComprobanteIva).count() == 0


# ── Lógica fiscal (service directo) ────────────────────────────────

def _mk_comp(db, org, direccion, periodo, tipo, iva, num, fecha="2026-05-10"):
    from datetime import date
    y, m, d = [int(x) for x in fecha.split("-")]
    c = ComprobanteIva(
        organizacion_id=org, direccion=direccion, periodo=periodo,
        fecha=date(y, m, d), tipo_codigo=tipo, tipo_desc=f"{tipo} - X",
        punto_venta=1, numero=num, cuit_contraparte=f"30{num:09d}",
        denominacion="X", neto_gravado_total=Decimal("0"),
        total_iva=Decimal(str(iva)), imp_total=Decimal("0"),
    )
    db.add(c)
    db.commit()
    return c


def test_credito_mayor_acumula_tecnico(db):
    # débito 1000, crédito 3000 → técnico -2000 → saldo_tecnico_nuevo 2000
    _mk_comp(db, 1, "emitido", "2026-05", 1, 1000, 1)
    _mk_comp(db, 1, "recibido", "2026-05", 1, 3000, 2)
    liq = calcular_liquidacion(db, 1, "2026-05")
    assert liq.debito_fiscal == Decimal("1000.00")
    assert liq.credito_fiscal == Decimal("3000.00")
    assert liq.tecnico_periodo == Decimal("-2000.00")
    assert liq.saldo_tecnico_nuevo == Decimal("2000.00")
    assert liq.saldo_a_pagar == Decimal("0.00")


def test_cadena_dos_periodos_hereda_tecnico(db):
    # Período 1: crédito > débito → deja 2000 de saldo técnico.
    _mk_comp(db, 1, "emitido", "2026-05", 1, 1000, 1)
    _mk_comp(db, 1, "recibido", "2026-05", 1, 3000, 2)
    calcular_liquidacion(db, 1, "2026-05")

    # Período 2: débito 5000, crédito 1000 → técnico 4000; hereda -2000 anterior
    # posicion = 4000 - 2000 = 2000 → a pagar 2000 (sin ret/perc).
    _mk_comp(db, 1, "emitido", "2026-06", 1, 5000, 3, fecha="2026-06-10")
    _mk_comp(db, 1, "recibido", "2026-06", 1, 1000, 4, fecha="2026-06-12")
    liq2 = calcular_liquidacion(db, 1, "2026-06")
    assert liq2.saldo_tecnico_anterior == Decimal("2000.00")  # heredado automático
    assert liq2.tecnico_periodo == Decimal("4000.00")
    assert liq2.saldo_tecnico_nuevo == Decimal("0.00")
    assert liq2.saldo_a_pagar == Decimal("2000.00")


def test_retenciones_sobran_generan_libre(db):
    # débito 5000, crédito 1000 → a pagar parcial 4000; retenciones 6000
    # → libre disponibilidad nuevo = 2000, a pagar 0.
    _mk_comp(db, 1, "emitido", "2026-05", 1, 5000, 1)
    _mk_comp(db, 1, "recibido", "2026-05", 1, 1000, 2)
    liq = calcular_liquidacion(db, 1, "2026-05", retenciones=Decimal("6000"))
    assert liq.tecnico_periodo == Decimal("4000.00")
    assert liq.saldo_a_pagar == Decimal("0.00")
    assert liq.saldo_libre_nuevo == Decimal("2000.00")


def test_nota_credito_resta_debito(db):
    # emitido: factura 5000 IVA, NC (tipo 3) 1000 IVA → débito 4000.
    _mk_comp(db, 1, "emitido", "2026-05", 1, 5000, 1)
    _mk_comp(db, 1, "emitido", "2026-05", 3, 1000, 2)  # NC A
    liq = calcular_liquidacion(db, 1, "2026-05")
    assert liq.debito_fiscal == Decimal("4000.00")


# ── Presentar / recalcular ─────────────────────────────────────────

def test_presentada_recalcular_409(db, client):
    token = _token(db, "admin@liq.test")
    _mk_comp(db, 1, "emitido", "2026-05", 1, 5000, 1)
    r = client.post("/iva/liquidacion/calcular", json={"periodo": "2026-05"}, headers=_auth(token))
    assert r.status_code == 200
    lid = r.json()["id"]

    rp = client.post(f"/iva/liquidacion/{lid}/presentar", headers=_auth(token))
    assert rp.status_code == 200
    assert rp.json()["estado"] == "presentada"

    # recalcular una presentada → 409
    r2 = client.post("/iva/liquidacion/calcular", json={"periodo": "2026-05"}, headers=_auth(token))
    assert r2.status_code == 409

    # presentar de nuevo → 409
    rp2 = client.post(f"/iva/liquidacion/{lid}/presentar", headers=_auth(token))
    assert rp2.status_code == 409


def test_get_liquidacion_404(db, client):
    token = _token(db, "admin@liq.test")
    r = client.get("/iva/liquidacion?periodo=2026-05", headers=_auth(token))
    assert r.status_code == 404


def test_historial_liquidaciones(db, client):
    token = _token(db, "admin@liq.test")
    _mk_comp(db, 1, "emitido", "2026-05", 1, 5000, 1)
    _mk_comp(db, 1, "emitido", "2026-06", 1, 3000, 2, fecha="2026-06-10")
    client.post("/iva/liquidacion/calcular", json={"periodo": "2026-05"}, headers=_auth(token))
    client.post("/iva/liquidacion/calcular", json={"periodo": "2026-06"}, headers=_auth(token))
    r = client.get("/iva/liquidacion/historial", headers=_auth(token))
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 2
    assert items[0]["periodo"] == "2026-06"  # desc


# ── Multi-tenant ───────────────────────────────────────────────────

def test_aislamiento_multi_tenant(db, client):
    """Superadmin importa comprobantes en org 3; consultando org 2 no los ve."""
    token = _token(db, "supa@liq.test")
    xlsx = _build_xlsx(
        "Mis Comprobantes Emitidos - CUIT 30716892871", _H_EMITIDOS,
        [_fila_emitido("10/05/2026", "1 - Factura A", 2, 100, 30111111119,
                       "C1", 2100, 10000, 2100, 12100)],
    )
    _importar(client, token, xlsx, "emitido", "2026-05")
    # superadmin con org_id=3
    r3 = client.post(
        "/iva/comprobantes/importar?direccion=emitido&periodo=2026-05&org_id=3",
        headers=_auth(token),
        files={"file": ("t.xlsx", xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert r3.status_code == 200
    assert r3.json()["importados"] == 1

    # org 3 ve 1, org 2 ve 0
    lst3 = client.get("/iva/comprobantes?periodo=2026-05&org_id=3", headers=_auth(token))
    assert len(lst3.json()["items"]) == 1
    lst2 = client.get("/iva/comprobantes?periodo=2026-05&org_id=2", headers=_auth(token))
    assert len(lst2.json()["items"]) == 0

    # a nivel DB: los comprobantes de org 3 tienen organizacion_id=3
    assert db.query(ComprobanteIva).filter(ComprobanteIva.organizacion_id == 3).count() == 1
    assert db.query(ComprobanteIva).filter(ComprobanteIva.organizacion_id == 2).count() == 0
