"""Regresión: en buscar_por_patrones (IA Nivel 2) la rama "match por números del
plan" usaba una variable indefinida (`nums_plan` en vez de `numeros_plan`), lo
que tiraba NameError en runtime cuando un patrón aprendido no matcheaba por sus
propios números pero sí por los del plan. Ver services/aprendizaje.py."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.organizacion import Organizacion
from app.models.patron_aprendido import PatronAprendido
from app.services.aprendizaje import buscar_por_patrones


class _Mov:
    """Stand-in liviano de MovimientoBanco (la función solo usa .id y .titular)."""
    def __init__(self, id, titular):
        self.id = id
        self.titular = titular


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    session.add(Organizacion(id=1, nombre="Org"))
    session.commit()
    yield session
    session.close()


def test_match_por_numeros_del_plan_no_rompe(db):
    # Patrón confirmado (veces_correcto>=2) con números propios que NO están en el
    # movimiento, y sin fragmento de titular → fuerza la rama "numeros_plan & nums_mov".
    db.add(PatronAprendido(
        organizacion_id=1, cliente_nombre="Dani",
        numeros_clave="111111", titular_extracto_fragmento=None,
        veces_correcto=2, activo=True,
    ))
    db.commit()

    mov = _Mov(id=10, titular="CREDITO POR CREDIN 999999")
    # referencia del plan aporta 999999, que sí está en el titular del movimiento
    resultado = buscar_por_patrones(
        db, org_id=1, cliente_nombre="Dani", monto=1000.0,
        cuit=None, titular=None, referencia="999999",
        movimientos_libres=[mov], procesados=set(),
    )
    assert resultado is mov  # antes: NameError en la rama de numeros_plan
