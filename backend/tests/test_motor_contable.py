"""Tests del motor contable.

Cada test usa una DB SQLite en memoria con plan de cuentas y reglas mínimas.
Cubre los casos críticos: happy path, idempotencia, regla faltante, monto inválido,
y comportamiento de upsert (re-conciliación, reposición efectivo).
"""

import pytest
from datetime import date
from decimal import Decimal
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
    "1-1-1-2", "1-1-1-3", "1-1-1-3-1", "1-1-2-0", "2-1-0-0",
    "2-1-2-0", "3-1-1-0", "3-2-0-0",
    # Cuentas cheques v2 (regla contador junio 2026)
    "1-1-2-1", "2-1-3-1", "3-1-3-0", "3-2-2-1",
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

def _cuenta_id(db, codigo):
    return db.query(PlanCuenta).filter(
        PlanCuenta.codigo == codigo, PlanCuenta.organizacion_id == ORG_ID).first().id


def test_cheque_registro_genera_asiento_3_lineas(db):
    """Registro cheque: Cartera(D) / Depositados(H neto) / Comisiones(H)."""
    fecha = date(2026, 5, 23)
    mc.registrar_cheque(db, cheque_id=1, org_id=ORG_ID, usuario_id=1,
                        titular="Cliente X", monto=5000, comision=100, fecha=fecha)
    asientos = _asientos_de(db, "cheque_registro", 1)
    assert len(asientos) == 1
    lineas = asientos[0].lineas
    assert len(lineas) == 3  # cartera + depositados + comisiones
    # Debe total = monto, Haber = neto + comisión
    assert abs(sum(l.debe for l in lineas) - 5000) < 0.01
    assert abs(sum(l.haber for l in lineas) - 5000) < 0.01
    cartera = _cuenta_id(db, "1-1-2-1")
    assert any(l.cuenta_id == cartera and l.debe == 5000 for l in lineas)


def test_cheque_registro_sin_comision_dos_lineas(db):
    mc.registrar_cheque(db, 1, ORG_ID, 1, "X", monto=5000, comision=0, fecha=date(2026, 5, 23))
    asientos = _asientos_de(db, "cheque_registro", 1)
    assert len(asientos) == 1
    assert len(asientos[0].lineas) == 2  # cartera(D) / depositados(H), sin comisión


def test_cheque_registro_idempotente(db):
    fecha = date(2026, 5, 23)
    mc.registrar_cheque(db, 1, ORG_ID, 1, "X", monto=5000, comision=100, fecha=fecha)
    mc.registrar_cheque(db, 1, ORG_ID, 1, "X", monto=5000, comision=100, fecha=fecha)
    assert len(_asientos_de(db, "cheque_registro", 1)) == 1


def test_cheque_acreditacion_dos_asientos(db):
    """Acreditación: A1 Banco(D)/Cartera(H) + A2 Depositados(D)/Cliente(H)."""
    fecha = date(2026, 5, 23)
    banco_id   = _cuenta_id(db, "1-1-1-3-1")
    cliente_id = _cuenta_id(db, "2-1-2-0")
    mc.registrar_cheque(db, 1, ORG_ID, 1, "X", monto=5000, comision=100, fecha=fecha)
    mc.acreditar_cheque(db, cheque_id=1, org_id=ORG_ID, usuario_id=1,
                        titular="X", monto=5000, neto=4900,
                        banco_cuenta_id=banco_id, cliente_cuenta_id=cliente_id, fecha=fecha)
    assert len(_asientos_de(db, "cheque_acred_banco", 1)) == 1
    assert len(_asientos_de(db, "cheque_acred_cliente", 1)) == 1
    # A1 banco por monto total, A2 cliente por neto
    a1 = _asientos_de(db, "cheque_acred_banco", 1)[0]
    assert abs(sum(l.debe for l in a1.lineas) - 5000) < 0.01
    a2 = _asientos_de(db, "cheque_acred_cliente", 1)[0]
    assert abs(sum(l.debe for l in a2.lineas) - 4900) < 0.01


def test_cheque_rechazo_tres_asientos(db):
    """Rechazo con gastos: A1 reversión + A2 traslado gastos + A3 débito banco."""
    fecha = date(2026, 5, 23)
    banco_id   = _cuenta_id(db, "1-1-1-3-1")
    cliente_id = _cuenta_id(db, "2-1-2-0")
    mc.rechazar_cheque(db, cheque_id=1, org_id=ORG_ID, usuario_id=1, titular="X",
                       monto=100000, gastos=5000,
                       banco_cuenta_id=banco_id, cliente_cuenta_id=cliente_id, fecha=fecha)
    assert len(_asientos_de(db, "cheque_rechazo_banco", 1)) == 1
    assert len(_asientos_de(db, "cheque_rechazo_cliente", 1)) == 1
    assert len(_asientos_de(db, "cheque_rechazo_gasto", 1)) == 1


def test_cheque_rechazo_sin_gastos_solo_reversion(db):
    fecha = date(2026, 5, 23)
    banco_id   = _cuenta_id(db, "1-1-1-3-1")
    cliente_id = _cuenta_id(db, "2-1-2-0")
    mc.rechazar_cheque(db, cheque_id=1, org_id=ORG_ID, usuario_id=1, titular="X",
                       monto=100000, gastos=0,
                       banco_cuenta_id=banco_id, cliente_cuenta_id=cliente_id, fecha=fecha)
    assert len(_asientos_de(db, "cheque_rechazo_banco", 1)) == 1
    assert len(_asientos_de(db, "cheque_rechazo_cliente", 1)) == 0
    assert len(_asientos_de(db, "cheque_rechazo_gasto", 1)) == 0


def test_cheque_ciclo_completo_transitorias_netean_cero(db):
    """Ciclo registro→acreditación: Cartera y Depositados deben quedar en 0.
    Saldos finales esperados: Banco +monto (D), Cliente +neto (H), Comisión (H)."""
    fecha = date(2026, 5, 23)
    banco_id   = _cuenta_id(db, "1-1-1-3-1")
    cliente_id = _cuenta_id(db, "2-1-2-0")
    cartera_id = _cuenta_id(db, "1-1-2-1")
    deposit_id = _cuenta_id(db, "2-1-3-1")

    mc.registrar_cheque(db, 1, ORG_ID, 1, "X", monto=100000, comision=2000, fecha=fecha)
    mc.acreditar_cheque(db, cheque_id=1, org_id=ORG_ID, usuario_id=1, titular="X",
                        monto=100000, neto=98000,
                        banco_cuenta_id=banco_id, cliente_cuenta_id=cliente_id, fecha=fecha)

    saldos: dict = {}
    for a in db.query(Asiento).filter(Asiento.organizacion_id == ORG_ID).all():
        for l in a.lineas:
            saldos.setdefault(l.cuenta_id, Decimal("0"))
            saldos[l.cuenta_id] += (l.debe - l.haber)

    # Transitorias en cero
    assert abs(saldos.get(cartera_id, 0)) < 0.01, "Cheques en cartera debería netear 0"
    assert abs(saldos.get(deposit_id, 0)) < 0.01, "Cheques depositados debería netear 0"
    # Banco +100000 (D), Cliente +98000 (H, saldo negativo en debe-haber)
    assert abs(saldos.get(banco_id, 0) - 100000) < 0.01
    assert abs(saldos.get(cliente_id, 0) + 98000) < 0.01


# ─── Egresos (módulo unificado Pagos) ────────────────────────────────────────

def test_egreso_idempotente(db):
    fecha = date(2026, 5, 23)
    mc.registrar_egreso(db, egreso_id=1, org_id=ORG_ID, usuario_id=1,
                        tipo="proveedor", forma_pago="efectivo",
                        monto=500, fecha=fecha, beneficiario="Proveedor")
    mc.registrar_egreso(db, egreso_id=1, org_id=ORG_ID, usuario_id=1,
                        tipo="proveedor", forma_pago="efectivo",
                        monto=500, fecha=fecha, beneficiario="Proveedor")
    assert len(_asientos_de(db, "egreso", 1)) == 1


def test_egreso_banco_usa_cuenta_hoja_banco_macro(db):
    """Un egreso por banco debe acreditar Banco Macro (1-1-1-3-1, hoja), NO la madre 1-1-1-3."""
    fecha = date(2026, 5, 23)
    mc.registrar_egreso(db, egreso_id=2, org_id=ORG_ID, usuario_id=1,
                        tipo="gasto", forma_pago="banco",
                        monto=800, fecha=fecha, concepto="Impuestos")
    asientos = _asientos_de(db, "egreso", 2)
    assert len(asientos) == 1
    banco_macro = db.query(PlanCuenta).filter(
        PlanCuenta.codigo == "1-1-1-3-1", PlanCuenta.organizacion_id == ORG_ID).first()
    haber_lineas = [l for l in asientos[0].lineas if l.haber > 0]
    assert len(haber_lineas) == 1
    assert haber_lineas[0].cuenta_id == banco_macro.id


def test_egreso_efectivo_usa_cuenta_efectivo(db):
    fecha = date(2026, 5, 23)
    mc.registrar_egreso(db, egreso_id=3, org_id=ORG_ID, usuario_id=1,
                        tipo="gasto", forma_pago="efectivo",
                        monto=300, fecha=fecha, concepto="Varios")
    asientos = _asientos_de(db, "egreso", 3)
    efectivo = db.query(PlanCuenta).filter(
        PlanCuenta.codigo == "1-1-1-2", PlanCuenta.organizacion_id == ORG_ID).first()
    haber_lineas = [l for l in asientos[0].lineas if l.haber > 0]
    assert haber_lineas[0].cuenta_id == efectivo.id


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
    mc.registrar_egreso(db, 1, ORG_ID, 1, tipo="proveedor", forma_pago="efectivo",
                        monto=100, fecha=fecha, beneficiario="Prov")

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
            saldos_por_cuenta.setdefault(l.cuenta_id, 0)
            saldos_por_cuenta[l.cuenta_id] += (l.debe - l.haber)

    for cuenta_id, saldo in saldos_por_cuenta.items():
        assert abs(saldo) < Decimal("0.01"), f"Cuenta {cuenta_id} quedó con saldo {saldo} (esperaba 0)"


def test_reverso_mantiene_invariante_partida_doble(db):
    """El asiento de reverso también debe tener debe == haber."""
    fecha = date(2026, 5, 23)
    mc.registrar_cheque(db, 1, ORG_ID, 1, "X", monto=2500, comision=100, fecha=fecha)
    mc.reversar_asientos(db, "cheque_registro", 1, ORG_ID, usuario_id=1)

    reversos = db.query(Asiento).filter(Asiento.modulo.like("%_reverso")).all()
    assert len(reversos) == 1
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
