"""Tests del reset de datos operativos por organización.

Cubre:
  - Borra lo transaccional de la(s) org(s) indicada(s)
  - CONSERVA maestros/config (clientes, users, plan_cuentas, reglas)
  - Aislamiento multi-tenant: NO toca otras organizaciones
  - Saldo de cuenta corriente vuelve a cero (asientos vaciados)
  - dry_run no borra nada y reporta los conteos
  - incluir_auditoria=False conserva el log de auditoría
"""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.auditoria import AuditoriaLog
from app.models.cheque import Cheque
from app.models.cliente import Cliente
from app.models.contabilidad import Asiento, AsientoDetalle, PlanCuenta, ReglaContable
from app.models.extracto import ExtractoBancario, MovimientoBanco
from app.models.organizacion import Organizacion
from app.models.planilla import Planilla, PlanillaRow
from app.models.user import User
from app.services.reset_operativo import reset_datos_operativos

ORG_A = 101  # se limpia
ORG_B = 202  # debe quedar intacta


def _seed_org(session, org_id: int, nombre: str):
    """Crea maestros + un set completo de datos transaccionales para una org."""
    session.add(Organizacion(id=org_id, nombre=nombre, plan="pro", activo=True, configuracion={}))
    session.flush()

    user = User(id=org_id + 1, email=f"u{org_id}@t.com", full_name="U", hashed_password="x",
                organizacion_id=org_id)
    banco = PlanCuenta(id=org_id + 10, codigo="1-1-1-3-1", nombre="Banco", tipo="activo",
                       nivel=4, activo=True, organizacion_id=org_id)
    cta_cli = PlanCuenta(id=org_id + 11, codigo="2-1-2-1", nombre="Cliente CC", tipo="pasivo",
                         nivel=4, activo=True, organizacion_id=org_id)
    session.add_all([user, banco, cta_cli])
    session.flush()

    cli = Cliente(id=org_id + 20, nombre="Cliente Test", organizacion_id=org_id,
                  cuenta_contable_id=cta_cli.id)
    regla = ReglaContable(id=org_id + 30, evento="um_credito", cuenta_debe_id=banco.id,
                          cuenta_haber_id=cta_cli.id, organizacion_id=org_id)
    session.add_all([cli, regla])
    session.flush()

    ext = ExtractoBancario(id=org_id + 40, nombre_archivo="e.xlsx", creado_por=user.id,
                           organizacion_id=org_id)
    session.add(ext)
    session.flush()
    session.add(MovimientoBanco(id=org_id + 50, extracto_id=ext.id, monto=Decimal("1000.00"),
                                organizacion_id=org_id))

    pl = Planilla(id=org_id + 60, cliente_id=cli.id, usuario_id=user.id,
                  nombre_archivo="p.xlsx", organizacion_id=org_id)
    session.add(pl)
    session.flush()
    session.add(PlanillaRow(id=org_id + 70, planilla_id=pl.id, monto=Decimal("1000.00"),
                            status="pendiente", organizacion_id=org_id))

    asi = Asiento(id=org_id + 80, numero_asiento=1, fecha=date(2026, 6, 1),
                  descripcion="test", modulo="um_lote", organizacion_id=org_id)
    session.add(asi)
    session.flush()
    # Debe en banco / Haber en cuenta corriente del cliente ⇒ saldo acreedor 1000
    session.add_all([
        AsientoDetalle(asiento_id=asi.id, cuenta_id=banco.id, debe=Decimal("1000.00"), haber=Decimal("0")),
        AsientoDetalle(asiento_id=asi.id, cuenta_id=cta_cli.id, debe=Decimal("0"), haber=Decimal("1000.00")),
    ])

    session.add(Cheque(id=org_id + 90, monto=Decimal("500.00"), comision=Decimal("0"),
                       estado="registrado", organizacion_id=org_id))
    session.add(AuditoriaLog(usuario_id=user.id, tabla="planillas", registro_id=pl.id,
                             accion="INSERT"))
    session.flush()


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()
    _seed_org(session, ORG_A, "Org A")
    _seed_org(session, ORG_B, "Org B")
    session.commit()
    yield session
    session.close()


def _saldo_cc(session, org_id):
    """Saldo de cuenta corriente = suma(debe-haber) sobre asiento_detalle de la org."""
    cta = session.query(Cliente).filter_by(organizacion_id=org_id).one().cuenta_contable_id
    rows = (session.query(AsientoDetalle).join(Asiento)
            .filter(AsientoDetalle.cuenta_id == cta, Asiento.organizacion_id == org_id).all())
    return sum((d.debe or 0) - (d.haber or 0) for d in rows)


def test_borra_transaccional_de_la_org(db):
    reset_datos_operativos(db, ORG_A)
    db.commit()
    assert db.query(MovimientoBanco).filter_by(organizacion_id=ORG_A).count() == 0
    assert db.query(ExtractoBancario).filter_by(organizacion_id=ORG_A).count() == 0
    assert db.query(Planilla).filter_by(organizacion_id=ORG_A).count() == 0
    assert db.query(PlanillaRow).filter_by(organizacion_id=ORG_A).count() == 0
    assert db.query(Asiento).filter_by(organizacion_id=ORG_A).count() == 0
    assert db.query(AsientoDetalle).count() == 2  # sólo quedan los de ORG_B
    assert db.query(Cheque).filter_by(organizacion_id=ORG_A).count() == 0


def test_conserva_maestros_y_config(db):
    reset_datos_operativos(db, ORG_A)
    db.commit()
    assert db.query(Cliente).filter_by(organizacion_id=ORG_A).count() == 1
    assert db.query(User).filter_by(organizacion_id=ORG_A).count() == 1
    assert db.query(PlanCuenta).filter_by(organizacion_id=ORG_A).count() == 2
    assert db.query(ReglaContable).filter_by(organizacion_id=ORG_A).count() == 1
    # El vínculo cliente → cuenta contable se mantiene
    assert db.query(Cliente).filter_by(organizacion_id=ORG_A).one().cuenta_contable_id is not None


def test_saldo_cuenta_corriente_vuelve_a_cero(db):
    assert _saldo_cc(db, ORG_A) == Decimal("-1000.00")  # acreedor antes
    reset_datos_operativos(db, ORG_A)
    db.commit()
    assert _saldo_cc(db, ORG_A) == 0


def test_no_toca_otra_organizacion(db):
    reset_datos_operativos(db, ORG_A)
    db.commit()
    assert db.query(MovimientoBanco).filter_by(organizacion_id=ORG_B).count() == 1
    assert db.query(Planilla).filter_by(organizacion_id=ORG_B).count() == 1
    assert db.query(Asiento).filter_by(organizacion_id=ORG_B).count() == 1
    assert db.query(Cheque).filter_by(organizacion_id=ORG_B).count() == 1
    assert _saldo_cc(db, ORG_B) == Decimal("-1000.00")


def test_dry_run_no_borra_y_reporta(db):
    resultado = reset_datos_operativos(db, ORG_A, dry_run=True)
    db.commit()
    # No borró nada
    assert db.query(MovimientoBanco).filter_by(organizacion_id=ORG_A).count() == 1
    # Reportó conteos
    assert resultado["movimientos_banco"] == 1
    assert resultado["asiento_detalle"] == 2
    assert resultado["planillas"] == 1
    assert resultado["auditoria"] == 1


def test_incluir_auditoria_false_conserva_log(db):
    reset_datos_operativos(db, ORG_A, incluir_auditoria=False)
    db.commit()
    # La auditoría de ORG_A se conserva; lo transaccional igual se borró
    assert db.query(AuditoriaLog).count() == 2
    assert db.query(Planilla).filter_by(organizacion_id=ORG_A).count() == 0


def test_multiples_orgs_a_la_vez(db):
    reset_datos_operativos(db, [ORG_A, ORG_B])
    db.commit()
    assert db.query(MovimientoBanco).count() == 0
    assert db.query(Planilla).count() == 0
    assert db.query(AsientoDetalle).count() == 0
    # Maestros de ambas intactos
    assert db.query(Cliente).count() == 2
    assert db.query(PlanCuenta).count() == 4


def test_lista_vacia_es_error(db):
    with pytest.raises(ValueError):
        reset_datos_operativos(db, [])
