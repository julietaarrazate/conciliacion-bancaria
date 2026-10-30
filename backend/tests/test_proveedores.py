"""Ficha de proveedores propios de la organización (base de retenciones).

Proveedor = a quien la ORGANIZACIÓN le compra (sus facturas recibidas). Las OP
por cuenta de un cliente (`pago_cliente`) pagan a proveedores DEL CLIENTE: no
entran a la ficha ni se vinculan a ella.
"""
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.cliente import Cliente
from app.models.comprobante_compra import BorradorComprobante
from app.models.egreso import Egreso
from app.models.iva_liquidacion import ComprobanteIva
from app.models.organizacion import Organizacion
from app.models.proveedor import Proveedor
from app.models.user import User
from app.services import proveedores as svc
from app.services.auth import create_access_token, get_password_hash

CUIT_A = "30712345671"
CUIT_B = "20111111112"


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    s = sessionmaker(bind=engine)()
    s.add_all([Organizacion(id=1, nombre="Empresa Demo"), Organizacion(id=2, nombre="Otra")])
    s.commit()
    for email, oid, rol in [("admin@p.test", 1, "admin"), ("revisor@p.test", 1, "revisor"),
                            ("otra@p.test", 2, "admin")]:
        s.add(User(email=email, full_name=email, hashed_password=get_password_hash("pw"),
                   organizacion_id=oid, is_active=True, role=rol, is_superadmin=False))
    s.add(Cliente(id=10, nombre="Distribuidora del Sur", organizacion_id=1))
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


def _recibido(db, org_id, cuit, nombre, total, tipo=1, numero=1):
    db.add(ComprobanteIva(organizacion_id=org_id, direccion="recibido", periodo="2026-09",
                          fecha=date(2026, 9, 10), tipo_codigo=tipo, punto_venta=1, numero=numero,
                          cuit_contraparte=cuit, denominacion=nombre,
                          neto_gravado_total=0, total_iva=0, imp_total=Decimal(total)))
    db.commit()


# ── Servicio ─────────────────────────────────────────────────────────────────

def test_sincronizar_trae_los_proveedores_de_las_facturas_recibidas(db):
    _recibido(db, 1, CUIT_A, "Papelera SA", "1000", numero=1)
    _recibido(db, 1, CUIT_A, "Papelera SA", "500", numero=2)
    _recibido(db, 1, CUIT_B, "Juan Perez", "200")
    _recibido(db, 2, "30999999993", "De otra org", "100")
    db.add(ComprobanteIva(organizacion_id=1, direccion="emitido", periodo="2026-09",
                          fecha=date(2026, 9, 1), tipo_codigo=6, punto_venta=1, numero=9,
                          cuit_contraparte="27222222223", denominacion="Un cliente",
                          neto_gravado_total=0, total_iva=0, imp_total=10))
    db.commit()

    creados = svc.sincronizar_desde_comprobantes(db, 1)

    assert creados == 2
    provs = db.query(Proveedor).filter_by(organizacion_id=1).order_by(Proveedor.razon_social).all()
    assert [(p.razon_social, p.cuit, p.origen) for p in provs] == [
        ("Juan Perez", CUIT_B, "comprobantes"), ("Papelera SA", CUIT_A, "comprobantes")]
    # Idempotente: una segunda pasada no duplica
    assert svc.sincronizar_desde_comprobantes(db, 1) == 0


def test_sincronizar_no_pisa_lo_editado_a_mano(db):
    db.add(Proveedor(organizacion_id=1, cuit=CUIT_A, razon_social="Papelera (nombre corto)",
                     origen="manual"))
    db.commit()
    _recibido(db, 1, CUIT_A, "PAPELERA SOCIEDAD ANONIMA", "1000")
    assert svc.sincronizar_desde_comprobantes(db, 1) == 0
    assert db.query(Proveedor).filter_by(cuit=CUIT_A).one().razon_social == "Papelera (nombre corto)"


def test_resumen_suma_facturado_con_notas_de_credito_y_pagado(db):
    p = svc.crear(db, 1, {"cuit": CUIT_A, "razon_social": "Papelera SA"})
    _recibido(db, 1, CUIT_A, "Papelera SA", "1000", numero=1)
    _recibido(db, 1, CUIT_A, "Papelera SA", "100", tipo=3, numero=2)   # NC A
    db.add(Egreso(organizacion_id=1, tipo="proveedor", monto=Decimal("600"), fecha=date(2026, 9, 20),
                  proveedor_id=p.id))
    db.commit()
    r = svc.listar(db, 1)[0]
    assert r["total_facturado"] == Decimal("900")
    assert r["total_pagado"] == Decimal("600")
    assert r["saldo"] == Decimal("300")


def test_crear_valida_cuit_y_no_duplica(db):
    with pytest.raises(svc.ProveedorInvalido):
        svc.crear(db, 1, {"cuit": "123", "razon_social": "X"})
    with pytest.raises(svc.ProveedorInvalido):
        svc.crear(db, 1, {"cuit": CUIT_A, "razon_social": "  "})
    svc.crear(db, 1, {"cuit": "30-71234567-1", "razon_social": "Papelera"})
    with pytest.raises(svc.ProveedorInvalido):
        svc.crear(db, 1, {"cuit": CUIT_A, "razon_social": "Otra vez"})
    # El mismo CUIT en otra organización es otro proveedor
    assert svc.crear(db, 2, {"cuit": CUIT_A, "razon_social": "Papelera"}).organizacion_id == 2
    # Sin CUIT se puede (proveedor informal)
    assert svc.crear(db, 1, {"razon_social": "Fletero"}).cuit is None


def test_confirmar_factura_de_compra_crea_el_proveedor_y_vincula_el_pago(db):
    from app.services.comprobantes_compra_service import confirmar_borrador
    b = BorradorComprobante(organizacion_id=1, estado="pendiente", origen="subida",
                            datos={"tipo_codigo": 1, "punto_venta": 3, "numero": 77,
                                   "fecha": "2026-09-15", "cuit_emisor": CUIT_A,
                                   "razon_social": "Papelera SA", "total": "1210",
                                   "alicuotas": {"21": {"neto": "1000", "iva": "210"}}})
    db.add(b)
    db.commit()
    res = confirmar_borrador(db, b, None, usuario_id=1, registrar_pago=True)
    prov = db.query(Proveedor).filter_by(organizacion_id=1, cuit=CUIT_A).one()
    assert prov.origen == "comprobantes"
    assert db.get(Egreso, res["egreso_id"]).proveedor_id == prov.id


# ── API ──────────────────────────────────────────────────────────────────────

def test_crud_por_api(client, db):
    h = _auth(db, "admin@p.test")
    r = client.post("/proveedores", json={"cuit": CUIT_A, "razon_social": "Papelera SA",
                                          "condicion_iva": "responsable_inscripto"}, headers=h)
    assert r.status_code == 200, r.text
    pid = r.json()["id"]
    r = client.patch(f"/proveedores/{pid}", json={"email": "pagos@papelera.test"}, headers=h)
    assert r.status_code == 200 and r.json()["email"] == "pagos@papelera.test"
    r = client.patch(f"/proveedores/{pid}", json={"condicion_iva": "cualquiera"}, headers=h)
    assert r.status_code == 422
    assert [p["razon_social"] for p in client.get("/proveedores", headers=h).json()] == ["Papelera SA"]
    assert client.get("/proveedores?q=pape", headers=h).json()[0]["id"] == pid
    assert client.get("/proveedores?q=zzz", headers=h).json() == []
    # Dar de baja: no se borra (puede tener pagos), deja de listarse
    assert client.delete(f"/proveedores/{pid}", headers=h).status_code == 200
    assert client.get("/proveedores", headers=h).json() == []
    assert len(client.get("/proveedores?incluir_inactivos=true", headers=h).json()) == 1


def test_permisos_y_aislamiento(client, db):
    h = _auth(db, "admin@p.test")
    pid = client.post("/proveedores", json={"razon_social": "Fletero"}, headers=h).json()["id"]
    # El revisor ve pero no edita
    hr = _auth(db, "revisor@p.test")
    assert client.get("/proveedores", headers=hr).status_code == 200
    assert client.post("/proveedores", json={"razon_social": "X"}, headers=hr).status_code == 403
    # Otra organización no lo ve ni lo toca
    ho = _auth(db, "otra@p.test")
    assert client.get("/proveedores", headers=ho).json() == []
    assert client.patch(f"/proveedores/{pid}", json={"razon_social": "Hack"}, headers=ho).status_code == 404
    assert client.delete(f"/proveedores/{pid}", headers=ho).status_code == 404


def test_sincronizar_por_api(client, db):
    _recibido(db, 1, CUIT_A, "Papelera SA", "1000")
    r = client.post("/proveedores/sincronizar", headers=_auth(db, "admin@p.test"))
    assert r.status_code == 200 and r.json() == {"creados": 1}


def test_pago_a_proveedor_se_vincula_a_la_ficha(client, db):
    h = _auth(db, "admin@p.test")
    pid = client.post("/proveedores", json={"cuit": CUIT_A, "razon_social": "Papelera SA"},
                      headers=h).json()["id"]
    r = client.post("/pagos", json={"tipo": "proveedor", "monto": 500, "fecha": "2026-09-20",
                                    "proveedor_id": pid}, headers=h)
    assert r.status_code == 200, r.text
    eg = r.json()["egreso"]
    assert eg["proveedor_id"] == pid
    assert eg["proveedor_nombre"] == "Papelera SA"
    assert eg["beneficiario"] == "Papelera SA"     # se completa con la razón social
    assert client.get("/proveedores", headers=h).json()[0]["total_pagado"] == 500


def test_op_por_cuenta_de_cliente_no_usa_la_ficha_de_proveedores(client, db):
    h = _auth(db, "admin@p.test")
    pid = client.post("/proveedores", json={"razon_social": "Papelera SA"}, headers=h).json()["id"]
    r = client.post("/pagos", json={"tipo": "pago_cliente", "cliente_id": 10, "monto": 500,
                                    "beneficiario": "Proveedor de Distribuidora del Sur", "proveedor_id": pid},
                    headers=h)
    assert r.status_code == 400
    assert "cliente" in r.json()["detail"].lower()
    # Y una OP por cuenta de cliente sin proveedor_id no crea nada en la ficha
    r = client.post("/pagos", json={"tipo": "pago_cliente", "cliente_id": 10, "monto": 500,
                                    "beneficiario": "Proveedor de Distribuidora del Sur"}, headers=h)
    assert r.status_code == 200
    assert db.query(Proveedor).count() == 1


def test_pago_con_proveedor_de_otra_org_400(client, db):
    pid = client.post("/proveedores", json={"razon_social": "De otra"},
                      headers=_auth(db, "otra@p.test")).json()["id"]
    r = client.post("/pagos", json={"tipo": "proveedor", "monto": 1, "proveedor_id": pid},
                    headers=_auth(db, "admin@p.test"))
    assert r.status_code == 400


def test_editar_pago_cambia_o_quita_el_proveedor(client, db):
    h = _auth(db, "admin@p.test")
    p1 = client.post("/proveedores", json={"razon_social": "Uno"}, headers=h).json()["id"]
    p2 = client.post("/proveedores", json={"razon_social": "Dos"}, headers=h).json()["id"]
    eid = client.post("/pagos", json={"tipo": "proveedor", "monto": 5, "proveedor_id": p1},
                      headers=h).json()["egreso"]["id"]
    r = client.patch(f"/pagos/{eid}", json={"proveedor_id": p2}, headers=h)
    assert r.status_code == 200 and r.json()["egreso"]["proveedor_id"] == p2
    r = client.patch(f"/pagos/{eid}", json={"proveedor_id": None}, headers=h)
    assert r.json()["egreso"]["proveedor_id"] is None
