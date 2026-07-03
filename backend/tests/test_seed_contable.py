"""Tests del sembrado de plan de cuentas por organización (v3.13)."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.organizacion import Organizacion
from app.models.contabilidad import PlanCuenta
from app.services.seed_contable import seed_contabilidad_org, PLAN, PLAN_PATCH, REGLAS


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=eng)
    s = sessionmaker(bind=eng, autoflush=False, autocommit=False)()
    s.add(Organizacion(id=7, nombre="Org Prueba", plan="pro", activo=True))
    s.commit()
    yield s
    s.close()


def test_seed_crea_plan_completo_para_org_nueva(db):
    res = seed_contabilidad_org(db, 7)
    # Todas las cuentas únicas de PLAN + PLAN_PATCH
    codigos = {c[0] for c in PLAN} | {c[0] for c in PLAN_PATCH}
    assert res["total_cuentas"] == len(codigos)
    assert res["total_reglas"] == len(REGLAS)
    # Cuentas clave que usa el motor
    for cod in ["1-1-1-3-1", "2-1-1-1", "2-1-2-0", "3-1-1-0", "1-1-2-1", "3-1-3-0", "3-2-2-1"]:
        assert db.query(PlanCuenta).filter(
            PlanCuenta.codigo == cod, PlanCuenta.organizacion_id == 7).first() is not None


def test_seed_respeta_jerarquia_padre_hijo(db):
    seed_contabilidad_org(db, 7)
    banco_macro = db.query(PlanCuenta).filter(
        PlanCuenta.codigo == "1-1-1-3-1", PlanCuenta.organizacion_id == 7).first()
    banco = db.query(PlanCuenta).filter(
        PlanCuenta.codigo == "1-1-1-3", PlanCuenta.organizacion_id == 7).first()
    assert banco_macro.parent_id == banco.id


def test_seed_es_idempotente(db):
    r1 = seed_contabilidad_org(db, 7)
    r2 = seed_contabilidad_org(db, 7)
    assert r2["cuentas_creadas"] == 0
    assert r2["reglas_creadas"] == 0
    assert r2["total_cuentas"] == r1["total_cuentas"]
    assert r2["total_reglas"] == r1["total_reglas"]


def test_seed_completa_plan_parcial(db):
    # Simula un seed parcial previo: solo la raíz Activo
    db.add(PlanCuenta(codigo="1-0-0-0", nombre="Activo", tipo="activo", nivel=1,
                      activo=True, organizacion_id=7))
    db.commit()
    res = seed_contabilidad_org(db, 7)
    codigos = {c[0] for c in PLAN} | {c[0] for c in PLAN_PATCH}
    assert res["total_cuentas"] == len(codigos)  # completó el resto sin duplicar 1-0-0-0
    assert db.query(PlanCuenta).filter(
        PlanCuenta.codigo == "1-0-0-0", PlanCuenta.organizacion_id == 7).count() == 1


def test_seed_no_pisa_otra_org(db):
    db.add(Organizacion(id=8, nombre="Otra", plan="pro", activo=True))
    db.commit()
    seed_contabilidad_org(db, 7)
    assert db.query(PlanCuenta).filter(PlanCuenta.organizacion_id == 8).count() == 0
