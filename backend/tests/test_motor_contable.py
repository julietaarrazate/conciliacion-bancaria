"""Tests del motor contable.

Cada test usa una DB SQLite en memoria con plan de cuentas y reglas mínimas.
Cubre los casos críticos: happy path, idempotencia, regla faltante, monto inválido,
y comportamiento de upsert (re-conciliación, reposición efectivo).
"""

import pytest
from datetime import date
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.contabilidad import (
    PlanCuenta, ReglaContable, Asiento, AsientoDetalle
)
from app.models.organizacion import Organizacion
from app.services import motor_contable as mc


ORG_ID = 1

# Mapeo regla → (cuenta_debe, cuenta_haber)
REGLAS_TEST = [
    ("carga_extracto",          "1-1-1-3", "2-1-0-0"),
    ("carga_planilla",          "2-1-0-0", "2-1-2-0"),
    ("carga_planilla_comision", "2-1-0-0", "3-1-1-0"),
    ("carga_efectivo",          "1-1-1-2", "1-1-1-3"),
    ("carga_cheque",            "1-1-2-0", "2-1-2-0"),
    ("carga_cheque_comision",   "1-1-2-0", "3-1-1-0"),
    ("acred_rechazo_banco",     "1-1-1-3", "1-1-2-0"),
    ("acred_rechazo_pasivo",    "2-1-2-0", "1-1-2-0"),
    ("pago_cliente_banco",      "2-1-2-0", "1-1-1-3"),
    ("pago_cliente_efectivo",   "2-1-2-0", "1-1-1-2"),
    ("asig_gasto_banco",        "3-2-0-0", "1-1-1-3"),
    ("asig_gasto_efectivo",     "3-2-0-0", "1-1-1-2"),
]

CUENTAS_TEST = [
    "1-1-1-2", "1-1-1-3", "1-1-2-0", "2-1-0-0",
    "2-1-2-0", "3-1-1-0", "3-2-0-0",
]


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()

    session.add(Organizacion(id=ORG_ID, nombre="Test SA", plan="pro", activo=True))
    session.commit()

    cuentas = {}
    for codigo in CUENTAS_TEST:
        c = PlanCuenta(codigo=codigo, nombre=codigo, tipo="activo", nivel=4, activo=True, organizacion_id=ORG_ID)
        session.add(c)
        session.flush()
        cuentas[codigo] = c.id

    for evento, debe_cod, haber_cod in REGLAS_TEST:
        session.add(ReglaContable(
            evento=evento,
            cuenta_debe_id=cuentas[debe_cod],
            cuenta_haber_id=cuentas[haber_cod],
            activo=True,
            organizacion_id=ORG_ID,
        ))
    session.commit()

    yield session
    session.close()


def _mov(monto):
    return SimpleNamespace(monto=monto)


def _row(monto, status="ok"):
    return SimpleNamespace(monto=monto, status=status)


def _asientos_de(db, modulo, ref_id):
    return db.query(Asiento).filter(
        Asiento.modulo == modulo,
        Asiento.referencia_id == ref_id,
        Asiento.organizacion_id == ORG_ID,
    ).all()


# ─── Extracto ────────────────────────────────────────────────────────────────

def test_extracto_crea_asiento_con_total_correcto(db):
    movs = [_mov(1000), _mov(2500), _mov(500)]
    mc.registrar_extracto(db, extracto_id=1, org_id=ORG_ID, usuario_id=1,
                          nombre_archivo="test.xlsx", movimientos=movs)

    asientos = _asientos_de(db, "extracto", 1)
    assert len(asientos) == 1
    assert len(asientos[0].lineas) == 2
    total_debe  = sum(l.debe  for l in asientos[0].lineas)
    total_haber = sum(l.haber for l in asientos[0].lineas)
    assert total_debe  == 4000.0
    assert total_haber == 4000.0


def test_extracto_idempotente(db):
    movs = [_mov(1000)]
    mc.registrar_extracto(db, 1, ORG_ID, 1, "x.xlsx", movs)
    mc.registrar_extracto(db, 1, ORG_ID, 1, "x.xlsx", movs)
    assert len(_asientos_de(db, "extracto", 1)) == 1


def test_extracto_monto_cero_no_crea_asiento(db):
    mc.registrar_extracto(db, 1, ORG_ID, 1, "x.xlsx", [])
    assert len(_asientos_de(db, "extracto", 1)) == 0


def test_extracto_suma_montos_negativos_en_abs(db):
    """Los retiros bancarios vienen negativos — el asiento debe sumar el absoluto."""
    movs = [_mov(1000), _mov(-300)]
    mc.registrar_extracto(db, 1, ORG_ID, 1, "x.xlsx", movs)
    total = sum(l.debe for l in _asientos_de(db, "extracto", 1)[0].lineas)
    assert total == 1300.0


# ─── Planilla ────────────────────────────────────────────────────────────────

def test_planilla_solo_suma_filas_ok(db):
    rows = [_row(1000, "ok"), _row(500, "pendiente"), _row(2000, "ok"), _row(300, "no está")]
    mc.registrar_planilla(db, planilla_id=1, org_id=ORG_ID, usuario_id=1,
                          cliente_nombre="Green", nombre_archivo="x.xlsx",
                          rows=rows, fecha_acred=date(2026, 5, 23))

    asiento = _asientos_de(db, "planilla", 1)[0]
    total = sum(l.debe for l in asiento.lineas)
    assert total == 3000.0


def test_planilla_re_conciliacion_actualiza_monto(db):
    """solo_pendientes=True debe ACTUALIZAR el asiento, no crear uno nuevo."""
    rows1 = [_row(1000)]
    mc.registrar_planilla(db, 1, ORG_ID, 1, "Green", "x.xlsx", rows1, date(2026, 5, 23))

    rows2 = [_row(1000), _row(500)]
    mc.registrar_planilla(db, 1, ORG_ID, 1, "Green", "x.xlsx", rows2,
                          date(2026, 5, 23), solo_pendientes=True)

    asientos = _asientos_de(db, "planilla", 1)
    assert len(asientos) == 1
    assert sum(l.debe for l in asientos[0].lineas) == 1500.0


def test_planilla_comision_genera_segundo_asiento(db):
    rows = [_row(10000)]
    mc.registrar_planilla(db, 1, ORG_ID, 1, "Green", "x.xlsx", rows,
                          date(2026, 5, 23), comision_pct=1.5)

    principales = _asientos_de(db, "planilla", 1)
    comisiones  = _asientos_de(db, "planilla_comision", 1)
    assert len(principales) == 1
    assert len(comisiones) == 1
    assert sum(l.debe for l in comisiones[0].lineas) == 150.0  # 10000 * 1.5%


def test_planilla_sin_filas_ok_no_crea_asiento(db):
    rows = [_row(1000, "pendiente"), _row(500, "no está")]
    mc.registrar_planilla(db, 1, ORG_ID, 1, "Green", "x.xlsx", rows, date(2026, 5, 23))
    assert len(_asientos_de(db, "planilla", 1)) == 0


# ─── Cheque ──────────────────────────────────────────────────────────────────

def test_cheque_carga_y_acreditacion(db):
    fecha = date(2026, 5, 23)
    mc.registrar_cheque(db, cheque_id=1, org_id=ORG_ID, usuario_id=1,
                        titular="Cliente X", monto=5000, comision=0, fecha=fecha)
    mc.acreditar_cheque(db, cheque_id=1, org_id=ORG_ID, usuario_id=1,
                        titular="Cliente X", monto=5000, fecha=fecha)

    assert len(_asientos_de(db, "cheque_carga", 1)) == 1
    assert len(_asientos_de(db, "cheque_acred", 1)) == 1


def test_cheque_con_comision_crea_dos_asientos(db):
    mc.registrar_cheque(db, 1, ORG_ID, 1, "X", monto=5000, comision=100, fecha=date(2026, 5, 23))
    assert len(_asientos_de(db, "cheque_carga", 1)) == 1
    assert len(_asientos_de(db, "cheque_comision", 1)) == 1


def test_cheque_rechazo_crea_asiento_distinto_al_acred(db):
    fecha = date(2026, 5, 23)
    mc.rechazar_cheque(db, 1, ORG_ID, 1, "X", monto=5000, fecha=fecha)
    assert len(_asientos_de(db, "cheque_rechazo", 1)) == 1
    assert len(_asientos_de(db, "cheque_acred", 1)) == 0


# ─── Pagos y gastos ──────────────────────────────────────────────────────────

def test_op_pago_idempotente(db):
    fecha = date(2026, 5, 23)
    mc.registrar_op_pago(db, op_id=1, org_id=ORG_ID, usuario_id=1,
                         beneficiario="Proveedor", cliente_nombre="Green",
                         monto=500, fecha=fecha)
    mc.registrar_op_pago(db, op_id=1, org_id=ORG_ID, usuario_id=1,
                         beneficiario="Proveedor", cliente_nombre="Green",
                         monto=500, fecha=fecha)
    assert len(_asientos_de(db, "caja_op", 1)) == 1


def test_ingreso_efectivo_upsert(db):
    """Repones efectivo dos veces para el mismo arqueo → un solo asiento actualizado."""
    fecha = date(2026, 5, 23)
    mc.registrar_ingreso_efectivo(db, arqueo_id=1, org_id=ORG_ID, usuario_id=1,
                                  monto=1000, fecha=fecha)
    mc.registrar_ingreso_efectivo(db, arqueo_id=1, org_id=ORG_ID, usuario_id=1,
                                  monto=2500, fecha=fecha)

    asientos = _asientos_de(db, "caja_efectivo", 1)
    assert len(asientos) == 1
    assert sum(l.debe for l in asientos[0].lineas) == 2500.0


# ─── Robustez ────────────────────────────────────────────────────────────────

def test_org_sin_regla_no_crashea(db):
    """Si la regla no existe para esa org, debe retornar sin error ni asiento."""
    db.query(ReglaContable).filter(ReglaContable.evento == "carga_extracto").delete()
    db.commit()
    mc.registrar_extracto(db, 1, ORG_ID, 1, "x.xlsx", [_mov(1000)])
    assert len(_asientos_de(db, "extracto", 1)) == 0


def test_monto_negativo_no_crea_asiento_planilla(db):
    """Una planilla con suma negativa NO debe generar asiento — protege la contabilidad."""
    rows = [_row(-500, "ok")]
    mc.registrar_planilla(db, 1, ORG_ID, 1, "Green", "x.xlsx", rows, date(2026, 5, 23))
    assert len(_asientos_de(db, "planilla", 1)) == 0


def test_partida_doble_siempre_balanceada(db):
    """Invariante crítica: debe == haber en TODO asiento generado."""
    fecha = date(2026, 5, 23)
    mc.registrar_extracto(db, 1, ORG_ID, 1, "x.xlsx", [_mov(1234.56)])
    mc.registrar_planilla(db, 1, ORG_ID, 1, "X", "x.xlsx", [_row(789.12)], fecha)
    mc.registrar_cheque(db, 1, ORG_ID, 1, "X", monto=999, comision=50, fecha=fecha)
    mc.registrar_op_pago(db, 1, ORG_ID, 1, "Prov", "Green", 100, fecha)

    for a in db.query(Asiento).filter(Asiento.organizacion_id == ORG_ID).all():
        debe  = sum(l.debe  for l in a.lineas)
        haber = sum(l.haber for l in a.lineas)
        assert abs(debe - haber) < 0.01, f"Asiento {a.id} ({a.modulo}) desbalanceado: D={debe} H={haber}"


# ─── Reversion contable ──────────────────────────────────────────────────────

def test_reversar_crea_asiento_con_debe_haber_invertidos(db):
    mc.registrar_extracto(db, 1, ORG_ID, 1, "x.xlsx", [_mov(1000)])
    original = _asientos_de(db, "extracto", 1)[0]
    debe_orig = [l.debe for l in original.lineas]
    haber_orig = [l.haber for l in original.lineas]

    creados = mc.reversar_asientos(db, "extracto", 1, ORG_ID, usuario_id=1)
    assert creados == 1

    reversos = db.query(Asiento).filter(Asiento.modulo == "extracto_reverso").all()
    assert len(reversos) == 1
    debe_rev = [l.debe for l in reversos[0].lineas]
    haber_rev = [l.haber for l in reversos[0].lineas]
    # Lo que era debe ahora es haber y viceversa
    assert sorted(debe_rev) == sorted(haber_orig)
    assert sorted(haber_rev) == sorted(debe_orig)


def test_reversar_es_idempotente(db):
    """Llamar reversar dos veces no debe crear dos reversos."""
    mc.registrar_extracto(db, 1, ORG_ID, 1, "x.xlsx", [_mov(1000)])
    mc.reversar_asientos(db, "extracto", 1, ORG_ID, usuario_id=1)
    creados_2 = mc.reversar_asientos(db, "extracto", 1, ORG_ID, usuario_id=1)
    assert creados_2 == 0
    assert len(db.query(Asiento).filter(Asiento.modulo == "extracto_reverso").all()) == 1


def test_reversar_sin_asientos_originales_no_hace_nada(db):
    """Reversar algo que nunca tuvo asiento debe devolver 0 sin error."""
    creados = mc.reversar_asientos(db, "pago", 9999, ORG_ID, usuario_id=1)
    assert creados == 0


def test_original_mas_reverso_neto_es_cero(db):
    """Suma de original + reverso: el efecto neto sobre cada cuenta es 0."""
    mc.registrar_planilla(db, 1, ORG_ID, 1, "Green", "x.xlsx",
                          [_row(1000)], date(2026, 5, 23))
    mc.reversar_asientos(db, "planilla", 1, ORG_ID, usuario_id=1)

    # Sumar todos los movimientos de cada cuenta
    saldos_por_cuenta: dict = {}
    for a in db.query(Asiento).filter(Asiento.organizacion_id == ORG_ID).all():
        for l in a.lineas:
            saldos_por_cuenta.setdefault(l.cuenta_id, 0.0)
            saldos_por_cuenta[l.cuenta_id] += (l.debe - l.haber)

    for cuenta_id, saldo in saldos_por_cuenta.items():
        assert abs(saldo) < 0.01, f"Cuenta {cuenta_id} quedó con saldo {saldo} (esperaba 0)"


def test_reverso_mantiene_invariante_partida_doble(db):
    """El asiento de reverso también debe tener debe == haber."""
    fecha = date(2026, 5, 23)
    mc.registrar_cheque(db, 1, ORG_ID, 1, "X", monto=2500, comision=100, fecha=fecha)
    mc.reversar_asientos(db, "cheque_carga", 1, ORG_ID, usuario_id=1)
    mc.reversar_asientos(db, "cheque_comision", 1, ORG_ID, usuario_id=1)

    reversos = db.query(Asiento).filter(Asiento.modulo.like("%_reverso")).all()
    assert len(reversos) == 2
    for r in reversos:
        debe = sum(l.debe for l in r.lineas)
        haber = sum(l.haber for l in r.lineas)
        assert abs(debe - haber) < 0.01


def test_reverso_referencia_al_asiento_original(db):
    """Trazabilidad: el reverso debe apuntar al asiento original via referencia_id."""
    mc.registrar_extracto(db, 1, ORG_ID, 1, "x.xlsx", [_mov(500)])
    original = _asientos_de(db, "extracto", 1)[0]

    mc.reversar_asientos(db, "extracto", 1, ORG_ID, usuario_id=1)
    reverso = db.query(Asiento).filter(Asiento.modulo == "extracto_reverso").first()

    assert reverso.referencia_id == original.id
    assert "REVERSO" in (reverso.descripcion or "")
