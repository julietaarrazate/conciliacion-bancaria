"""Tests de `services/extracto_import.py` (persistencia compartida Excel / PDF).

El comportamiento del upload de Excel lo cubren `test_extractos_org.py` y el resto;
acá se prueban los contratos que usa el importador de PDF.
"""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.main  # noqa: F401  (registra todos los modelos)
from app.database import Base
from app.models.extracto import ExtractoBancario, MovimientoBanco
from app.models.organizacion import Organizacion
from app.models.user import User
from app.services import extracto_import as ei


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    s = sessionmaker(bind=engine)()
    s.add(Organizacion(id=1, nombre="Org1"))
    s.add(Organizacion(id=2, nombre="Org2"))
    s.commit()
    s.add(User(email="u@x.test", full_name="u", hashed_password="x", organizacion_id=2, role="admin"))
    s.commit()
    yield s
    s.close()


def _movs():
    # del más reciente al más antiguo (como el parser de Excel de Macro)
    return [
        {"orden": None, "fecha": date(2026, 9, 3), "mes": "9", "titular": "B", "monto": Decimal("-5.00"),
         "saldo": Decimal("95.00"), "cliente_acreditado": None, "fecha_acred": None},
        {"orden": None, "fecha": date(2026, 9, 1), "mes": "9", "titular": "A", "monto": Decimal("100.00"),
         "saldo": Decimal("100.00"), "cliente_acreditado": None, "fecha_acred": None},
    ]


def test_resolver_banco_y_nombre():
    assert ei.resolver_banco("Banco Macro", "galicia") == "Galicia"
    assert ei.resolver_banco("Mi banco", "galicia") == "Mi banco"
    assert ei.resolver_banco("Banco Macro", "generico") == "Banco Macro"
    assert ei.resolver_banco("Banco Macro", "mercadopago") == "Mercadopago"
    assert ei.nombre_banco("provincia") == "Bapro"
    assert ei.nombre_banco("generico") is None and ei.nombre_banco(None) is None


def test_fingerprint_igual_que_antes():
    assert ei.fingerprint([]) == "empty"
    a = ei.fingerprint([{"orden": 7, "monto": 10.5}, {"orden": 3, "monto": -0.5}])
    assert a == ei.fingerprint([{"orden": 7, "monto": 10.5}, {"orden": 3, "monto": -0.5}])
    assert a != ei.fingerprint([{"orden": None, "monto": 10.5}, {"orden": None, "monto": -0.5}])


def test_crear_extracto_numera_y_respeta_la_org(db):
    ext = ei.crear_extracto_con_movimientos(db, movs=_movs(), nombre_archivo="x", banco="Galicia",
                                            huella="h1", org_id=2, usuario_id=1)
    movs = db.query(MovimientoBanco).filter(MovimientoBanco.extracto_id == ext.id) \
        .order_by(MovimientoBanco.orden).all()
    assert [(m.orden, m.titular) for m in movs] == [(1, "A"), (2, "B")]
    assert ext.organizacion_id == 2 and all(m.organizacion_id == 2 for m in movs)
    assert all(m.source == "extracto" for m in movs) and ext.fingerprint == "h1"


def test_crear_extracto_sin_commit_se_puede_deshacer(db):
    ei.crear_extracto_con_movimientos(db, movs=_movs(), nombre_archivo="x", banco="Galicia",
                                      huella="h2", org_id=2, usuario_id=1, commit=False)
    db.rollback()
    assert db.query(ExtractoBancario).count() == 0 and db.query(MovimientoBanco).count() == 0


def test_asiento_um_que_falla_devuelve_false(db, monkeypatch):
    ext = ei.crear_extracto_con_movimientos(db, movs=_movs(), nombre_archivo="x", banco="Galicia",
                                            huella="h3", org_id=2, usuario_id=1)

    def _explota(**kwargs):
        raise RuntimeError("motor caído")
    monkeypatch.setattr("app.services.motor_contable.registrar_um_import", _explota)
    assert ei.registrar_asiento_um(db, extracto=ext, nuevo_lote=1, usuario_id=1) is False

    llamadas = []
    monkeypatch.setattr("app.services.motor_contable.registrar_um_import", lambda **kw: llamadas.append(kw))
    assert ei.registrar_asiento_um(db, extracto=ext, nuevo_lote=1, usuario_id=1, modo_asiento="individual") is True
    assert llamadas[0]["org_id"] == 2 and llamadas[0]["modo"] == "individual"
    assert llamadas[0]["extracto_id"] == ext.id
