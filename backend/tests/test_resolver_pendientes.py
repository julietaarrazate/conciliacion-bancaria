"""Resolver un débito pendiente del extracto con un pago vinculado.

Cubre `services/movimiento_egreso.py`, el `movimiento_banco_id` de POST/PATCH
/pagos, el listado de movimientos (egreso_id + gasto_bancario) y el bloque
`debitos` del resumen del extracto. Llamadas directas al router con SQLite en
memoria, igual que test_pagos_v312.py.
"""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.egreso import Egreso
from app.models.extracto import ExtractoBancario, MovimientoBanco
from app.models.organizacion import Organizacion
from app.models.user import User
from app.services.gastos_bancarios import resumen_extracto
from app.services.movimiento_egreso import (
    VinculoInvalido,
    egresos_por_movimiento,
    validar_vinculo,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    session.add_all([Organizacion(id=1, nombre="Org1"), Organizacion(id=2, nombre="Org2")])
    from app.services.auth import get_password_hash
    session.add(User(id=1, email="a@test.com", full_name="A", hashed_password=get_password_hash("pw"),
                     organizacion_id=1, is_superadmin=False))
    session.commit()
    yield session
    session.close()


def _user(org_id=1):
    u = MagicMock(spec=User)
    u.id = 1
    u.organizacion_id = org_id
    u.is_superadmin = False
    return u


def _request():
    from starlette.requests import Request
    from app.main import app as fastapi_app
    return Request(scope={"type": "http", "headers": [], "client": ("test", 0),
                          "path": "/pagos", "method": "POST", "app": fastapi_app})


def _extracto(db, org_id=1, movimientos=((-1500, "TRANSF A PROVEEDOR SA"),)):
    ext = ExtractoBancario(nombre_archivo="ext.xlsx", creado_por=1, organizacion_id=org_id)
    db.add(ext)
    db.flush()
    movs = []
    for i, (monto, titular) in enumerate(movimientos, start=1):
        m = MovimientoBanco(extracto_id=ext.id, orden=i, fecha=date(2026, 10, 1), titular=titular,
                            monto=Decimal(str(monto)), organizacion_id=org_id)
        db.add(m)
        movs.append(m)
    db.commit()
    return ext, movs


def _crear(db, mov_id, monto="1500", forma_pago="banco", tipo="proveedor"):
    from app.routers.pagos import crear_egreso
    return crear_egreso(
        request=_request(),
        payload={"tipo": tipo, "forma_pago": forma_pago, "monto": monto, "fecha": "2026-10-01",
                 "beneficiario": "Proveedor SA", "movimiento_banco_id": mov_id},
        db=db, current_user=_user(),
    )


# ── validar_vinculo ──────────────────────────────────────────────────────────

class TestValidarVinculo:

    def test_debito_mismo_importe_ok(self, db):
        _, (mov,) = _extracto(db)
        assert validar_vinculo(db, mov.id, 1, Decimal("1500.00"), "banco").id == mov.id

    def test_importe_distinto_rechaza(self, db):
        _, (mov,) = _extracto(db)
        with pytest.raises(VinculoInvalido, match="mismo importe"):
            validar_vinculo(db, mov.id, 1, Decimal("1499.99"), "banco")

    def test_credito_rechaza(self, db):
        _, (mov,) = _extracto(db, movimientos=((2000, "TRANSF DE CLIENTE"),))
        with pytest.raises(VinculoInvalido, match="débito"):
            validar_vinculo(db, mov.id, 1, Decimal("2000"), "banco")

    def test_efectivo_rechaza(self, db):
        _, (mov,) = _extracto(db)
        with pytest.raises(VinculoInvalido, match="por banco"):
            validar_vinculo(db, mov.id, 1, Decimal("1500"), "efectivo")

    def test_otra_org_no_encuentra(self, db):
        _, (mov,) = _extracto(db, org_id=2)
        with pytest.raises(VinculoInvalido, match="no encontrado"):
            validar_vinculo(db, mov.id, 1, Decimal("1500"), "banco")

    def test_extracto_borrado_no_encuentra(self, db):
        ext, (mov,) = _extracto(db)
        from datetime import datetime
        ext.deleted_at = datetime(2026, 10, 2)
        db.commit()
        with pytest.raises(VinculoInvalido, match="no encontrado"):
            validar_vinculo(db, mov.id, 1, Decimal("1500"), "banco")

    def test_id_invalido(self, db):
        with pytest.raises(VinculoInvalido):
            validar_vinculo(db, "abc", 1, Decimal("1"), "banco")


# ── POST /pagos con movimiento_banco_id ──────────────────────────────────────

class TestCrearEgresoVinculado:

    def test_crea_y_vincula(self, db):
        _, (mov,) = _extracto(db)
        res = _crear(db, mov.id)
        assert res["ok"] is True
        assert res["egreso"]["movimiento_banco_id"] == mov.id
        assert egresos_por_movimiento(db, [mov.id]) == {mov.id: res["egreso"]["id"]}

    def test_sin_movimiento_sigue_igual(self, db):
        res = _crear(db, None)
        assert res["egreso"]["movimiento_banco_id"] is None

    def test_segundo_pago_al_mismo_movimiento_rechaza(self, db):
        _, (mov,) = _extracto(db)
        primero = _crear(db, mov.id)
        with pytest.raises(HTTPException) as ex:
            _crear(db, mov.id)
        assert ex.value.status_code == 400
        assert f"#{primero['egreso']['id']}" in ex.value.detail
        assert db.query(Egreso).count() == 1

    def test_importe_distinto_no_crea_nada(self, db):
        _, (mov,) = _extracto(db)
        with pytest.raises(HTTPException) as ex:
            _crear(db, mov.id, monto="100")
        assert ex.value.status_code == 400
        assert db.query(Egreso).count() == 0


# ── PATCH /pagos/{id} ────────────────────────────────────────────────────────

class TestEditarEgresoVinculado:

    def test_editar_monto_de_pago_vinculado_rechaza(self, db):
        from app.routers.pagos import editar_egreso
        _, (mov,) = _extracto(db)
        eid = _crear(db, mov.id)["egreso"]["id"]
        with pytest.raises(HTTPException) as ex:
            editar_egreso(egreso_id=eid, payload={"monto": 1000}, db=db, current_user=_user())
        assert ex.value.status_code == 400
        e = db.get(Egreso, eid)
        assert e.monto == Decimal("1500.00")
        assert e.movimiento_banco_id == mov.id

    def test_desvincular_y_editar_monto(self, db):
        from app.routers.pagos import editar_egreso
        _, (mov,) = _extracto(db)
        eid = _crear(db, mov.id)["egreso"]["id"]
        res = editar_egreso(egreso_id=eid, payload={"monto": 1000, "movimiento_banco_id": None},
                            db=db, current_user=_user())
        assert res["egreso"]["movimiento_banco_id"] is None
        assert db.get(Egreso, eid).monto == Decimal("1000.00")

    def test_vincular_pago_existente(self, db):
        from app.routers.pagos import editar_egreso
        _, (mov,) = _extracto(db)
        eid = _crear(db, None)["egreso"]["id"]
        res = editar_egreso(egreso_id=eid, payload={"movimiento_banco_id": mov.id},
                            db=db, current_user=_user())
        assert res["egreso"]["movimiento_banco_id"] == mov.id


# ── Listado de movimientos, borrado y resumen ────────────────────────────────

class TestExtractosConPagos:

    def test_listado_marca_pago_y_gasto_bancario(self, db):
        from app.routers.extractos import listar_movimientos
        _, (pago, comision, credito) = _extracto(db, movimientos=(
            (-1500, "TRANSF A PROVEEDOR SA"), (-120, "COMISION MANTENIMIENTO"), (900, "TRANSF DE CLIENTE")))
        eid = _crear(db, pago.id)["egreso"]["id"]
        res = listar_movimientos(extracto_id=pago.extracto_id, cliente=None, cuit=None, titular=None,
                                 desde=None, hasta=None, fecha_desde=None, fecha_hasta=None,
                                 sin_acreditar=None, skip=0, limit=0, db=db, current_user=_user())
        por_id = {m.id: m for m in res["items"]}
        assert por_id[pago.id].egreso_id == eid
        assert por_id[pago.id].gasto_bancario is None
        assert por_id[comision.id].egreso_id is None
        assert por_id[comision.id].gasto_bancario == "Comisiones y mantenimiento"
        assert por_id[credito.id].gasto_bancario is None

    def test_resumen_cuenta_debitos_explicados(self, db):
        from app.routers.extractos import resumen_extracto as resumen_endpoint
        ext, (pago, _comision, _suelto, _credito) = _extracto(db, movimientos=(
            (-1500, "TRANSF A PROVEEDOR SA"), (-120, "COMISION MANTENIMIENTO"),
            (-300.50, "DEBITO AUTOMATICO"), (900, "TRANSF DE CLIENTE")))
        _crear(db, pago.id)
        r = resumen_endpoint(extracto_id=ext.id, db=db, current_user=_user())
        assert r["debitos"] == {"debitos": 3, "explicados": 2, "sin_explicar": 1,
                                "total_sin_explicar": Decimal("300.50"), "porcentaje": 66.7}
        assert r["explicado"]["creditos"] == 1

    def test_borrar_movimiento_deja_el_pago_sin_vinculo(self, db):
        from app.routers.extractos import delete_movimiento
        _, (mov,) = _extracto(db)
        eid = _crear(db, mov.id)["egreso"]["id"]
        delete_movimiento(extracto_id=mov.extracto_id, mov_id=mov.id, db=db, current_user=_user())
        e = db.get(Egreso, eid)
        assert e is not None
        assert e.movimiento_banco_id is None


def test_resumen_sin_ids_mantiene_compatibilidad():
    movs = [SimpleNamespace(titular="COMISION", monto=Decimal("-10"), cliente_acreditado=None),
            SimpleNamespace(titular="X", monto=Decimal("-5"), cliente_acreditado=None)]
    r = resumen_extracto(movs)
    assert r["debitos"]["explicados"] == 1
    assert r["debitos"]["porcentaje"] == 50.0
    assert r["gastos_bancarios"]["total"] == Decimal("10.00")


def test_indice_unico_frena_dos_pagos_al_mismo_movimiento(db):
    """Si dos pedidos pasan la validación a la vez, la base rechaza el segundo."""
    from sqlalchemy.exc import IntegrityError
    _, (mov,) = _extracto(db)
    for i in (1, 2):
        db.add(Egreso(id=100 + i, organizacion_id=1, tipo="gasto", forma_pago="banco",
                      monto=Decimal("1500"), fecha=date(2026, 10, 1), movimiento_banco_id=mov.id))
        if i == 1:
            db.commit()
    with pytest.raises(IntegrityError):
        db.commit()


# ── Vincular un pago ya cargado ──────────────────────────────────────────────

def _egreso_cargado(db, egreso_id, monto="1500", fecha=date(2026, 10, 3), forma_pago="banco",
                    org_id=1, movimiento_banco_id=None):
    e = Egreso(id=egreso_id, organizacion_id=org_id, tipo="proveedor", forma_pago=forma_pago,
               monto=Decimal(monto), fecha=fecha, beneficiario="Proveedor SA",
               movimiento_banco_id=movimiento_banco_id)
    db.add(e)
    db.commit()
    return e


class TestPagosCandidatos:

    def test_solo_mismo_importe_banco_sin_vincular_y_fecha_cercana(self, db):
        from app.services.movimiento_egreso import candidatos_para_movimiento
        _, (mov, otro) = _extracto(db, movimientos=((-1500, "TRANSF"), (-1500, "TRANSF 2")))
        _egreso_cargado(db, 1, fecha=date(2026, 10, 3))                      # sí (2 días)
        _egreso_cargado(db, 2, fecha=date(2026, 9, 28))                      # sí (3 días)
        _egreso_cargado(db, 3, monto="1499")                                 # otro importe
        _egreso_cargado(db, 4, forma_pago="efectivo")                        # efectivo
        _egreso_cargado(db, 5, fecha=date(2026, 11, 30))                     # muy lejos
        _egreso_cargado(db, 6, org_id=2)                                     # otra org
        _egreso_cargado(db, 7, movimiento_banco_id=otro.id)                  # ya vinculado
        ids = [e.id for e in candidatos_para_movimiento(db, mov, 1)]
        assert ids == [1, 2]  # el más cercano en fecha primero

    def test_endpoint_candidatos(self, db):
        from app.routers.pagos import candidatos_movimiento
        _, (mov,) = _extracto(db)
        _egreso_cargado(db, 1)
        res = candidatos_movimiento(movimiento_id=mov.id, org_id=None, db=db, current_user=_user())
        assert [c["id"] for c in res] == [1]
        assert res[0]["dias_diferencia"] == 2

    def test_endpoint_candidatos_otra_org_404(self, db):
        from app.routers.pagos import candidatos_movimiento
        _, (mov,) = _extracto(db, org_id=2)
        with pytest.raises(HTTPException) as ex:
            candidatos_movimiento(movimiento_id=mov.id, org_id=None, db=db, current_user=_user())
        assert ex.value.status_code == 404


class TestVincularMovimiento:

    def test_vincula_sin_tocar_asientos(self, db):
        from app.models.contabilidad import Asiento
        from app.routers.pagos import vincular_movimiento
        _, (mov,) = _extracto(db)
        _egreso_cargado(db, 1)
        antes = db.query(Asiento).count()
        res = vincular_movimiento(egreso_id=1, payload={"movimiento_banco_id": mov.id},
                                  db=db, current_user=_user())
        assert res["egreso"]["movimiento_banco_id"] == mov.id
        assert db.query(Asiento).count() == antes

    def test_importe_distinto_rechaza(self, db):
        from app.routers.pagos import vincular_movimiento
        _, (mov,) = _extracto(db)
        _egreso_cargado(db, 1, monto="900")
        with pytest.raises(HTTPException) as ex:
            vincular_movimiento(egreso_id=1, payload={"movimiento_banco_id": mov.id},
                                db=db, current_user=_user())
        assert ex.value.status_code == 400
        assert db.get(Egreso, 1).movimiento_banco_id is None

    def test_pago_de_otra_org_404(self, db):
        from app.routers.pagos import vincular_movimiento
        _, (mov,) = _extracto(db)
        _egreso_cargado(db, 1, org_id=2)
        with pytest.raises(HTTPException) as ex:
            vincular_movimiento(egreso_id=1, payload={"movimiento_banco_id": mov.id},
                                db=db, current_user=_user())
        assert ex.value.status_code == 404

    def test_sin_movimiento_400(self, db):
        from app.routers.pagos import vincular_movimiento
        _egreso_cargado(db, 1)
        with pytest.raises(HTTPException) as ex:
            vincular_movimiento(egreso_id=1, payload={}, db=db, current_user=_user())
        assert ex.value.status_code == 400


# ── OP por cuenta de un cliente (no es gasto de la organización) ─────────────

def test_resolver_con_op_por_cuenta_de_cliente_va_a_su_cuenta_corriente(db):
    """Un débito que es una OP pagada por cuenta de un cliente (ej. Green) se
    resuelve como pago_cliente: el asiento debita la cuenta corriente del
    cliente, no Gastos de la organización."""
    from app.models.cliente import Cliente
    from app.models.contabilidad import Asiento, AsientoDetalle, PlanCuenta
    from app.routers.pagos import crear_egreso
    from app.services.seed_contable import seed_contabilidad_org

    seed_contabilidad_org(db, 1)
    db.add(Cliente(id=50, nombre="Green", organizacion_id=1))
    db.commit()
    _, (mov,) = _extracto(db)
    res = crear_egreso(
        request=_request(),
        payload={"tipo": "pago_cliente", "forma_pago": "banco", "monto": "1500", "fecha": "2026-10-01",
                 "cliente_nombre": "Green", "beneficiario": "Proveedor de Green SA",
                 "movimiento_banco_id": mov.id},
        db=db, current_user=_user(),
    )
    e = db.get(Egreso, res["egreso"]["id"])
    assert e.tipo == "pago_cliente" and e.cliente_id == 50 and e.movimiento_banco_id == mov.id
    asiento = db.query(Asiento).filter_by(modulo="egreso", referencia_id=e.id).one()
    debe = db.query(AsientoDetalle).filter(AsientoDetalle.asiento_id == asiento.id,
                                           AsientoDetalle.debe > 0).one()
    cuenta = db.get(PlanCuenta, debe.cuenta_id)
    assert cuenta.codigo.startswith("2-1-2-")          # cuenta corriente del cliente
    assert cuenta.codigo != "3-2-0-0"                 # no es Gastos de la organización
    assert cuenta.nombre == "Green"
