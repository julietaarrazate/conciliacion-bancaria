"""Resumen de gastos bancarios, "% explicado" y motivo de cada match.

Todo es read-only y aditivo: estos tests verifican además que nada de esto
cambia el resultado del motor (`buscar_match`) ni muta movimientos.
"""
from decimal import Decimal

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
from app.models.planilla import PlanillaRow
from app.services.conciliacion import explicar_match
from app.services.gastos_bancarios import clasificar_gasto, resumen_extracto


def _mov(monto, titular="", cliente_acreditado=None, id=1):
    return MovimientoBanco(id=id, extracto_id=1, monto=monto, titular=titular,
                           cliente_acreditado=cliente_acreditado)


# ── clasificar_gasto ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("titular,esperado", [
    ("IMP. LEY 25.413 S/DEBIT", "Impuesto Ley 25.413 (débitos y créditos)"),
    ("IMP LEY 25413 S/CRED", "Impuesto Ley 25.413 (débitos y créditos)"),
    ("IMPUESTO A LOS DEBITOS", "Impuesto Ley 25.413 (débitos y créditos)"),
    ("IMP. DEB. LEY 25413", "Impuesto Ley 25.413 (débitos y créditos)"),
    ("SIRCREB REG. RECAUDA", "SIRCREB / Ingresos Brutos"),
    ("ING. BRUTOS S/ CRED REG.RECAU.SIRCREB", "SIRCREB / Ingresos Brutos"),
    ("RETENCION IIBB", "SIRCREB / Ingresos Brutos"),
    ("PERCEPCION IVA RG 2408", "Percepción IVA"),
    ("IVA TASA GENERAL", "IVA"),
    ("I.V.A. 21%", None),  # no se fuerza: sin la palabra IVA suelta no se adivina
    ("COMISION MANTENIMIENTO", "Comisiones y mantenimiento"),
    ("Comisión transferencia", "Comisiones y mantenimiento"),
    ("COM. MANT. CUENTA", "Comisiones y mantenimiento"),
    ("INTERESES SALDO DEUDOR", "Intereses y sellos"),
    ("TRANSF. ENVIADA PROVEEDOR SA", None),
    ("PAGO VEP F.931", None),
])
def test_clasificar_gasto_debitos(titular, esperado):
    assert clasificar_gasto(titular, Decimal("-100")) == esperado


def test_creditos_nunca_son_gasto():
    # Un cliente que se llama "IVA SRL" o un crédito por comisión no es gasto bancario.
    assert clasificar_gasto("TRANSF. RECIBIDA IVA SRL", Decimal("500")) is None
    assert clasificar_gasto("COMISION COBRADA", 100) is None
    assert clasificar_gasto("IMP LEY 25413", None) is None


def test_iva_no_matchea_dentro_de_otra_palabra():
    assert clasificar_gasto("TRANSF A IVANA LOPEZ", Decimal("-10")) is None


# ── resumen_extracto ─────────────────────────────────────────────────────────

def test_resumen_agrupa_al_centavo_y_calcula_explicado():
    movs = [
        _mov(Decimal("-196.80"), "IMP. LEY 25.413 S/DEBIT"),
        _mov(Decimal("-12687.36"), "IMP. LEY 25.413 S/DEBIT"),
        _mov(Decimal("-2470.00"), "SIRCREB REG. RECAUDA"),
        _mov(Decimal("-32800.00"), "COMISION MANTENIMIENTO"),
        _mov(Decimal("-6888.00"), "IVA TASA GENERAL"),
        _mov(Decimal("-734900.00"), "TRANSF. ENVIADA TALLER"),  # no es gasto
        _mov(Decimal("400000.00"), "DEP. EFECTIVO CAJA 03", cliente_acreditado="Green"),
        _mov(Decimal("250000.00"), "DEP. EFECTIVO CAJA 03", cliente_acreditado="No identificado"),
        _mov(Decimal("180500.00"), "DEP. EFECTIVO CAJA 01"),
        _mov(Decimal("612000.00"), "TRANSF. RECIBIDA", cliente_acreditado="Tucu"),
    ]
    r = resumen_extracto(movs)

    g = r["gastos_bancarios"]
    por = {c["concepto"]: c for c in g["conceptos"]}
    assert por["Impuesto Ley 25.413 (débitos y créditos)"]["cantidad"] == 2
    assert por["Impuesto Ley 25.413 (débitos y créditos)"]["total"] == Decimal("12884.16")
    assert por["SIRCREB / Ingresos Brutos"]["total"] == Decimal("2470.00")
    assert g["cantidad"] == 5
    assert g["total"] == Decimal("55042.16")
    # Orden fijo por concepto (el de las reglas), no por monto.
    assert [c["concepto"] for c in g["conceptos"]][0].startswith("Impuesto Ley 25.413")

    e = r["explicado"]
    assert e == {"creditos": 4, "acreditados": 2, "sin_acreditar": 2, "porcentaje": 50.0}


def test_resumen_extracto_vacio():
    r = resumen_extracto([])
    assert r["gastos_bancarios"] == {"conceptos": [], "cantidad": 0, "total": Decimal("0.00")}
    assert r["explicado"]["porcentaje"] is None


def test_resumen_no_muta_movimientos():
    m = _mov(Decimal("-100"), "COMISION", cliente_acreditado=None)
    resumen_extracto([m])
    assert m.cliente_acreditado is None and m.monto == Decimal("-100")


# ── explicar_match ───────────────────────────────────────────────────────────

def _row(cuit=None, titular=None, referencia=None):
    return PlanillaRow(planilla_id=1, monto=5000, cuit=cuit, titular=titular,
                       referencia=referencia, status="ok")


@pytest.mark.parametrize("row,titular_mov,esperado", [
    (_row(cuit="20-11223344-0"), "TRANSF 20112233440 GARCIA MARIA", "cuit"),
    (_row(cuit="11223344"), "TRANSF 20112233440 GARCIA MARIA", "dni"),
    (_row(titular="CBU 2850590940090418135201"), "CBU 2850590940090418135201 EMPRESA", "cbu"),
    (_row(referencia="0004512"), "TRANSF. RECIBIDA OP 0004512 LOS ALAMOS", "numero"),
    (_row(titular="Garcia Maria"), "TRANSF GARCIA MARIA", "titular"),
    (_row(referencia="FAC-A"), "COBRO FAC-A LOS ALAMOS", "referencia"),
    (_row(titular="Perez Juan"), "DEP. EFECTIVO CAJA 03", "monto"),
    (_row(referencia="  "), "DEP. EFECTIVO CAJA 03", "monto"),
])
def test_explicar_match(row, titular_mov, esperado):
    assert explicar_match(row, _mov(5000, titular_mov)) == esperado


def test_explicar_match_sin_movimiento():
    assert explicar_match(_row(cuit="20112233440"), None) is None


# ── Endpoints ────────────────────────────────────────────────────────────────

@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    session.add_all([Organizacion(id=1, nombre="A"), Organizacion(id=2, nombre="B")])
    session.commit()
    session.add_all([
        User(email="a@org.test", full_name="A", hashed_password=get_password_hash("pw"),
             organizacion_id=1, is_active=True, role="admin", is_superadmin=False),
        User(email="b@org.test", full_name="B", hashed_password=get_password_hash("pw"),
             organizacion_id=2, is_active=True, role="admin", is_superadmin=False),
    ])
    session.commit()
    yield session
    session.close()


@pytest.fixture
def client(db):
    def _override():
        yield db
    app.dependency_overrides[get_db] = _override
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)


def _auth(db, email):
    u = db.query(User).filter(User.email == email).first()
    tok = create_access_token({"sub": u.email, "user_id": u.id, "role": u.role})
    return {"Authorization": f"Bearer {tok}"}


def _extracto_org1(db):
    u = db.query(User).filter(User.email == "a@org.test").first()
    e = ExtractoBancario(nombre_archivo="macro.xlsx", creado_por=u.id, organizacion_id=1)
    db.add(e)
    db.commit()
    db.add_all([
        MovimientoBanco(extracto_id=e.id, organizacion_id=1, monto=Decimal("-32800.00"), titular="COMISION MANTENIMIENTO"),
        MovimientoBanco(extracto_id=e.id, organizacion_id=1, monto=Decimal("-196.80"), titular="IMP. LEY 25.413 S/DEBIT"),
        MovimientoBanco(extracto_id=e.id, organizacion_id=1, monto=Decimal("1000.00"), titular="TRANSF", cliente_acreditado="Green"),
    ])
    db.commit()
    return e


def test_endpoint_resumen(client, db):
    e = _extracto_org1(db)
    r = client.get(f"/extractos/{e.id}/resumen", headers=_auth(db, "a@org.test"))
    assert r.status_code == 200
    body = r.json()
    assert Decimal(str(body["gastos_bancarios"]["total"])) == Decimal("32996.80")
    assert body["explicado"]["porcentaje"] == 100.0


def test_endpoint_resumen_aislado_por_org(client, db):
    e = _extracto_org1(db)
    r = client.get(f"/extractos/{e.id}/resumen", headers=_auth(db, "b@org.test"))
    assert r.status_code == 404
