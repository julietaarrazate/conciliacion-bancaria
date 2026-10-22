"""Aislamiento entre organizaciones en endpoints que recibían IDs sin validar la org.

Revisión de seguridad oct/2026. Escenario: un operador de la org 1 manda IDs de
datos de la org 2. Antes cada caso funcionaba (leía o modificaba datos ajenos);
ahora tiene que fallar sin tocar nada de la org 2.
  - POST /clientes/planillas/{id}/guardar      → descargaba la planilla de otra org
  - POST /clientes/movimientos/{id}/acreditar → escribía en el movimiento de otra org
  - POST /pagos con cliente_id de otra org      → usaba el cliente ajeno
  - PATCH /cheques/{id} con cliente/portador de otra org
  - POST /cheques/{id}/acreditar con cuenta de banco de otra org
"""
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.cheque import Cheque
from app.models.cliente import Cliente
from app.models.contabilidad import PlanCuenta
from app.models.extracto import ExtractoBancario, MovimientoBanco
from app.models.organizacion import Organizacion
from app.models.planilla import Planilla, PlanillaRow
from app.models.portador import Portador
from app.models.user import User
from app.routers.clientes_dir import _nombre_carpeta_seguro
from app.services.auth import create_access_token, get_password_hash
from app.services.seed_contable import seed_contabilidad_org


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    s = sessionmaker(bind=engine)()
    s.add_all([Organizacion(id=1, nombre="Org1"), Organizacion(id=2, nombre="Org2")])
    s.commit()
    seed_contabilidad_org(s, 1)
    seed_contabilidad_org(s, 2)
    for email, org in (("op1@t.test", 1), ("op2@t.test", 2)):
        s.add(User(
            email=email, full_name=email, hashed_password=get_password_hash("pw123"),
            organizacion_id=org, is_active=True, role="operador", is_superadmin=False,
        ))
    s.commit()
    yield s
    s.close()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app, raise_server_exceptions=True)
    app.dependency_overrides.pop(get_db, None)


def _auth(db, email):
    u = db.query(User).filter(User.email == email).first()
    tok = create_access_token({"sub": u.email, "user_id": u.id, "role": u.role})
    return {"Authorization": f"Bearer {tok}"}


def _user_id(db, email):
    return db.query(User).filter(User.email == email).first().id


def _cliente(db, org, nombre):
    c = Cliente(nombre=nombre, organizacion_id=org)
    db.add(c)
    db.commit()
    return c


def _movimiento(db, org):
    ext = ExtractoBancario(
        nombre_archivo=f"ext{org}.xlsx", creado_por=_user_id(db, f"op{org}@t.test"),
        organizacion_id=org,
    )
    db.add(ext)
    db.flush()
    mov = MovimientoBanco(
        extracto_id=ext.id, orden=1, titular="Titular org2", monto=Decimal("1000"),
        organizacion_id=org,
    )
    db.add(mov)
    db.commit()
    return mov


def _cuenta_banco(db, org):
    return db.query(PlanCuenta).filter(
        PlanCuenta.codigo == "1-1-1-3-1", PlanCuenta.organizacion_id == org,
    ).first()


# ── Planillas ────────────────────────────────────────────────────────────────

def test_guardar_planilla_de_otra_org_da_404(client, db):
    cli2 = _cliente(db, 2, "Cliente Org2")
    p = Planilla(
        cliente_id=cli2.id, usuario_id=_user_id(db, "op2@t.test"),
        nombre_archivo="privada.xlsx", organizacion_id=2,
    )
    db.add(p)
    db.flush()
    db.add(PlanillaRow(planilla_id=p.id, monto=Decimal("10"), status="ok", titular="Secreto"))
    db.commit()

    r = client.post(f"/clientes/planillas/{p.id}/guardar", headers=_auth(db, "op1@t.test"))
    assert r.status_code == 404

    r_propia = client.post(f"/clientes/planillas/{p.id}/guardar", headers=_auth(db, "op2@t.test"))
    assert r_propia.status_code == 200


@pytest.mark.parametrize("nombre", ["../../etc", "..", "a/../../b", "C:\\Windows", ""])
def test_nombre_de_carpeta_no_sale_de_la_base(nombre):
    limpio = _nombre_carpeta_seguro(nombre)
    assert limpio
    assert "/" not in limpio and "\\" not in limpio and ".." not in limpio


# ── Movimientos ──────────────────────────────────────────────────────────────

def test_acreditar_movimiento_de_otra_org_da_404_y_no_lo_toca(client, db):
    mov = _movimiento(db, 2)
    cli1 = _cliente(db, 1, "Cliente Org1")

    r = client.post(
        f"/clientes/movimientos/{mov.id}/acreditar",
        json={"cliente_id": cli1.id, "fecha_acred": "2026-01-01"},
        headers=_auth(db, "op1@t.test"),
    )
    assert r.status_code == 404
    db.refresh(mov)
    assert mov.cliente_acreditado is None
    assert db.query(Planilla).filter(Planilla.organizacion_id == 2).count() == 0


# ── Pagos ────────────────────────────────────────────────────────────────────

def test_pago_con_cliente_de_otra_org_no_usa_el_cliente_ajeno(client, db):
    cli2 = _cliente(db, 2, "Cliente Org2 Privado")

    r = client.post(
        "/pagos",
        json={"tipo": "pago_cliente", "monto": 1, "cliente_id": cli2.id},
        headers=_auth(db, "op1@t.test"),
    )
    assert r.status_code >= 400
    assert "Cliente Org2 Privado" not in r.text
    db.refresh(cli2)
    assert cli2.cuenta_contable_id is None


# ── Cheques ──────────────────────────────────────────────────────────────────

def _cheque_org1(db):
    c = Cheque(organizacion_id=1, monto=Decimal("500"), comision=Decimal("0"), estado="registrado")
    db.add(c)
    db.commit()
    return c


def test_patch_cheque_con_cliente_de_otra_org_da_404(client, db):
    cheque = _cheque_org1(db)
    cli2 = _cliente(db, 2, "Cliente Org2")

    r = client.patch(
        f"/cheques/{cheque.id}", json={"monto": 500, "cliente_id": cli2.id}, headers=_auth(db, "op1@t.test"),
    )
    assert r.status_code == 404
    db.refresh(cheque)
    assert cheque.cliente_id is None


def test_patch_cheque_con_portador_de_otra_org_da_404(client, db):
    cheque = _cheque_org1(db)
    port2 = Portador(nombre="Portador Org2", organizacion_id=2)
    db.add(port2)
    db.commit()

    r = client.patch(
        f"/cheques/{cheque.id}", json={"monto": 500, "portador_id": port2.id}, headers=_auth(db, "op1@t.test"),
    )
    assert r.status_code == 404
    db.refresh(cheque)
    assert cheque.portador_id is None


def test_acreditar_cheque_con_cuenta_de_banco_de_otra_org_da_404(client, db):
    cheque = _cheque_org1(db)
    banco_org2 = _cuenta_banco(db, 2)
    assert banco_org2 is not None

    r = client.post(
        f"/cheques/{cheque.id}/acreditar",
        json={"banco_cuenta_id": banco_org2.id},
        headers=_auth(db, "op1@t.test"),
    )
    assert r.status_code == 404
    db.refresh(cheque)
    assert cheque.estado == "registrado"
