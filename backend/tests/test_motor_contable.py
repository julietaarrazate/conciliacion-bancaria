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
    "2-1-1-1", "2-1-2-0", "3-1-1-0", "3-2-0-0",
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


# ─── Reclasificación agrupada por planilla (v3.13) ────────────────────────────

def _cliente_con_cuenta(db, nombre="Green"):
    """Crea un Cliente con su cuenta contable (2-1-2-X) ya vinculada."""
    from app.models.cliente import Cliente
    padre = db.query(PlanCuenta).filter(PlanCuenta.codigo == "2-1-2-0", PlanCuenta.organizacion_id == ORG_ID).first()
    cuenta = PlanCuenta(codigo="2-1-2-1", nombre=nombre, tipo="pasivo", nivel=5,
                        activo=True, organizacion_id=ORG_ID, parent_id=padre.id)
    db.add(cuenta)
    db.flush()
    cli = Cliente(nombre=nombre, organizacion_id=ORG_ID, cuenta_contable_id=cuenta.id)
    db.add(cli)
    db.flush()
    return cli, cuenta


def test_reclasificacion_planilla_un_asiento_agrupado(db):
    """Un solo asiento por planilla: No identificado (2-1-1-1) D / Cliente H."""
    cli, cuenta_cli = _cliente_con_cuenta(db)
    mc.registrar_reclasificacion_planilla(
        db, planilla_id=10, org_id=ORG_ID, usuario_id=1,
        cliente_id=cli.id, cliente_nombre=cli.nombre,
        total_monto=Decimal("3000"), fecha=date(2026, 5, 23),
        nombre_archivo="green.xlsx",
    )
    asientos = _asientos_de(db, "um_reclass_planilla", 10)
    assert len(asientos) == 1
    a = asientos[0]
    assert len(a.lineas) == 2
    no_id = next(l for l in a.lineas if l.debe > 0)
    cli_l = next(l for l in a.lineas if l.haber > 0)
    assert no_id.debe == Decimal("3000")
    assert cli_l.haber == Decimal("3000")
    assert cli_l.cuenta_id == cuenta_cli.id


def test_reclasificacion_planilla_con_comision_separa_neto_y_comision(db):
    """comision_pct > 0 -> 2 asientos: principal por el NETO (origen D / Cliente H)
    y uno separado por la comision (origen D / Comisiones ganadas H). Tratamiento
    acordado con el contador (ago 2026): el cliente queda acreditado por el neto,
    la comision se reconoce como ingreso aparte."""
    cli, cuenta_cli = _cliente_con_cuenta(db)
    mc.registrar_reclasificacion_planilla(
        db, planilla_id=20, org_id=ORG_ID, usuario_id=1,
        cliente_id=cli.id, cliente_nombre=cli.nombre,
        total_monto=Decimal("100000"), fecha=date(2026, 8, 20),
        nombre_archivo="alojando.xlsx", comision_pct=Decimal("2"),
    )
    principales = _asientos_de(db, "um_reclass_planilla", 20)
    comisiones = _asientos_de(db, "um_reclass_planilla_comision", 20)
    assert len(principales) == 1
    assert len(comisiones) == 1

    p = principales[0]
    origen_p = next(l for l in p.lineas if l.debe > 0)
    cli_l = next(l for l in p.lineas if l.haber > 0)
    assert origen_p.debe == Decimal("98000.00")
    assert cli_l.haber == Decimal("98000.00")
    assert cli_l.cuenta_id == cuenta_cli.id

    c = comisiones[0]
    origen_c = next(l for l in c.lineas if l.debe > 0)
    com_l = next(l for l in c.lineas if l.haber > 0)
    assert origen_c.debe == Decimal("2000.00")
    assert com_l.haber == Decimal("2000.00")


def test_reclasificacion_planilla_sin_comision_no_crea_asiento_comision(db):
    """comision_pct == 0 (default) -> un solo asiento por el total, sin separar
    nada (compatibilidad con el comportamiento previo a ago 2026)."""
    cli, _ = _cliente_con_cuenta(db)
    mc.registrar_reclasificacion_planilla(
        db, planilla_id=21, org_id=ORG_ID, usuario_id=1,
        cliente_id=cli.id, cliente_nombre=cli.nombre,
        total_monto=Decimal("5000"), fecha=date(2026, 8, 20),
    )
    assert len(_asientos_de(db, "um_reclass_planilla", 21)) == 1
    assert len(_asientos_de(db, "um_reclass_planilla_comision", 21)) == 0


def test_reclasificacion_planilla_bajar_comision_a_cero_borra_asiento_comision(db):
    """Re-conciliar con comision_pct=0 tras haber tenido comision borra el
    asiento de comision viejo (no lo deja huerfano con un monto que ya no
    corresponde)."""
    cli, _ = _cliente_con_cuenta(db)
    mc.registrar_reclasificacion_planilla(
        db, planilla_id=22, org_id=ORG_ID, usuario_id=1,
        cliente_id=cli.id, cliente_nombre=cli.nombre,
        total_monto=Decimal("10000"), fecha=date(2026, 8, 20),
        comision_pct=Decimal("2"),
    )
    assert len(_asientos_de(db, "um_reclass_planilla_comision", 22)) == 1

    mc.registrar_reclasificacion_planilla(
        db, planilla_id=22, org_id=ORG_ID, usuario_id=1,
        cliente_id=cli.id, cliente_nombre=cli.nombre,
        total_monto=Decimal("10000"), fecha=date(2026, 8, 20),
        comision_pct=Decimal("0"),
    )
    assert len(_asientos_de(db, "um_reclass_planilla_comision", 22)) == 0
    principal = _asientos_de(db, "um_reclass_planilla", 22)[0]
    assert sum(l.debe for l in principal.lineas) == Decimal("10000.00")


def test_reclasificacion_planilla_origen_extracto_usa_pasivo_corriente_y_modulo_propio(db):
    """cuenta_origen_codigo='2-1-0-0' (extracto principal) postea contra Pasivo
    Corriente, no contra No identificado, y usa un modulo DISTINTO al de UM —
    para que ambos buckets convivan sin pisarse en la MISMA planilla (un cliente
    puede tener filas conciliadas contra el extracto y contra UM a la vez)."""
    cli, cuenta_cli = _cliente_con_cuenta(db)
    pasivo = db.query(PlanCuenta).filter(PlanCuenta.codigo == "2-1-0-0", PlanCuenta.organizacion_id == ORG_ID).first()

    mc.registrar_reclasificacion_planilla(
        db, planilla_id=30, org_id=ORG_ID, usuario_id=1,
        cliente_id=cli.id, cliente_nombre=cli.nombre,
        total_monto=Decimal("7000"), fecha=date(2026, 8, 20),
        cuenta_origen_codigo="2-1-0-0",
    )
    asientos_extracto = _asientos_de(db, "reclass_planilla_extracto", 30)
    assert len(asientos_extracto) == 1
    origen_l = next(l for l in asientos_extracto[0].lineas if l.debe > 0)
    assert origen_l.cuenta_id == pasivo.id

    # El mismo planilla_id, bucket UM (default) -> asiento aparte, no choca.
    mc.registrar_reclasificacion_planilla(
        db, planilla_id=30, org_id=ORG_ID, usuario_id=1,
        cliente_id=cli.id, cliente_nombre=cli.nombre,
        total_monto=Decimal("1000"), fecha=date(2026, 8, 20),
    )
    assert len(_asientos_de(db, "reclass_planilla_extracto", 30)) == 1
    assert len(_asientos_de(db, "um_reclass_planilla", 30)) == 1


def test_conciliar_planilla_genera_asiento_por_origen_con_comision(db):
    """Integración conciliacion.conciliar_planilla -> motor_contable: una planilla
    con filas conciliadas contra el extracto principal Y contra UM genera DOS
    asientos separados (uno por origen), cada uno neteando su propia comisión —
    sin que se pisen entre sí en la misma planilla."""
    from app.services.conciliacion import conciliar_planilla, CONFIG_DEFAULT_ORG

    cli, cuenta_cli = _cliente_con_cuenta(db, nombre="Alojando")

    mov_extracto = SimpleNamespace(
        id=101, source="extracto", monto=Decimal("98000"), titular="JUAN PEREZ",
        fecha=date(2026, 8, 19), cliente_acreditado=None, fecha_acred=None,
    )
    mov_um = SimpleNamespace(
        id=202, source="um", monto=Decimal("49000"), titular="JUAN PEREZ",
        fecha=date(2026, 8, 19), cliente_acreditado=None, fecha_acred=None,
    )
    row_extracto = SimpleNamespace(
        planilla_id=99, monto=Decimal("98000"), cuit=None, titular="Juan Perez",
        referencia=None, fecha=date(2026, 8, 19), fecha_acred=None,
        status="pendiente", orden_movimiento_acreditado=None,
    )
    row_um = SimpleNamespace(
        planilla_id=99, monto=Decimal("49000"), cuit=None, titular="Juan Perez",
        referencia=None, fecha=date(2026, 8, 19), fecha_acred=None,
        status="pendiente", orden_movimiento_acreditado=None,
    )

    resultado = conciliar_planilla(
        db=db,
        planilla_rows=[row_extracto, row_um],
        movimientos=[mov_extracto, mov_um],
        cliente_nombre="Alojando",
        fecha_acred_str="2026-08-20",
        org_config=CONFIG_DEFAULT_ORG,
        org_id=ORG_ID,
        cliente_id=cli.id,
        comision_pct=Decimal("2"),
    )
    assert resultado["acreditadas"] == 2

    principal_extracto = _asientos_de(db, "reclass_planilla_extracto", 99)
    comision_extracto = _asientos_de(db, "reclass_planilla_extracto_comision", 99)
    principal_um = _asientos_de(db, "um_reclass_planilla", 99)
    comision_um = _asientos_de(db, "um_reclass_planilla_comision", 99)
    assert len(principal_extracto) == 1 and len(comision_extracto) == 1
    assert len(principal_um) == 1 and len(comision_um) == 1

    pasivo = db.query(PlanCuenta).filter(PlanCuenta.codigo == "2-1-0-0", PlanCuenta.organizacion_id == ORG_ID).first()
    no_id = db.query(PlanCuenta).filter(PlanCuenta.codigo == "2-1-1-1", PlanCuenta.organizacion_id == ORG_ID).first()

    origen_pe = next(l for l in principal_extracto[0].lineas if l.debe > 0)
    assert origen_pe.cuenta_id == pasivo.id
    assert origen_pe.debe == Decimal("96040.00")  # 98000 - 2%

    origen_pu = next(l for l in principal_um[0].lineas if l.debe > 0)
    assert origen_pu.cuenta_id == no_id.id
    assert origen_pu.debe == Decimal("48020.00")  # 49000 - 2%


def test_reclasificacion_planilla_upsert_actualiza_monto(db):
    """Re-conciliar la misma planilla actualiza el monto, no crea otro asiento."""
    cli, _ = _cliente_con_cuenta(db)
    mc.registrar_reclasificacion_planilla(
        db, 10, ORG_ID, 1, cli.id, cli.nombre, Decimal("1000"), date(2026, 5, 23))
    mc.registrar_reclasificacion_planilla(
        db, 10, ORG_ID, 1, cli.id, cli.nombre, Decimal("1500"), date(2026, 5, 24))
    asientos = _asientos_de(db, "um_reclass_planilla", 10)
    assert len(asientos) == 1
    assert sum(l.debe for l in asientos[0].lineas) == Decimal("1500")


def test_reclasificacion_planilla_monto_cero_no_crea(db):
    cli, _ = _cliente_con_cuenta(db)
    mc.registrar_reclasificacion_planilla(
        db, 10, ORG_ID, 1, cli.id, cli.nombre, Decimal("0"), date(2026, 5, 23))
    assert len(_asientos_de(db, "um_reclass_planilla", 10)) == 0


# ─── Asiento al aprobar liquidación (v3.13) ───────────────────────────────────

def test_liquidacion_aprobacion_partida_doble(db):
    """Cliente D (bruto) / Banco H (neto) + Comisiones H (comisión), balanceado."""
    cli, cuenta_cli = _cliente_con_cuenta(db)
    mc.registrar_liquidacion_aprobacion(
        db, liquidacion_id=5, detalle_id=50, org_id=ORG_ID, usuario_id=1,
        cliente_id=cli.id, cliente_nombre=cli.nombre,
        monto_conciliado=Decimal("10000"), monto_neto=Decimal("9800"),
        monto_comision=Decimal("200"), fecha=date(2026, 5, 31),
    )
    asientos = _asientos_de(db, "liquidacion_aprobacion", 50)
    assert len(asientos) == 1
    a = asientos[0]
    total_debe  = sum(l.debe for l in a.lineas)
    total_haber = sum(l.haber for l in a.lineas)
    assert total_debe == Decimal("10000")
    assert total_haber == Decimal("10000")
    # Cliente debitado por el bruto
    cli_l = next(l for l in a.lineas if l.cuenta_id == cuenta_cli.id)
    assert cli_l.debe == Decimal("10000")


def test_liquidacion_aprobacion_sin_comision(db):
    """Sin comisión: solo Cliente D / Banco H (2 líneas)."""
    cli, _ = _cliente_con_cuenta(db)
    mc.registrar_liquidacion_aprobacion(
        db, 5, 50, ORG_ID, 1, cli.id, cli.nombre,
        Decimal("10000"), Decimal("10000"), Decimal("0"), date(2026, 5, 31))
    a = _asientos_de(db, "liquidacion_aprobacion", 50)[0]
    assert len(a.lineas) == 2


def test_liquidacion_aprobacion_idempotente(db):
    cli, _ = _cliente_con_cuenta(db)
    for _ in range(2):
        mc.registrar_liquidacion_aprobacion(
            db, 5, 50, ORG_ID, 1, cli.id, cli.nombre,
            Decimal("10000"), Decimal("9800"), Decimal("200"), date(2026, 5, 31))
    assert len(_asientos_de(db, "liquidacion_aprobacion", 50)) == 1


# ─── Invariante: partida doble en todo el libro (v3.13) ───────────────────────

def test_partida_doble_invariante_libro_completo(db):
    """Tras generar asientos de cada tipo, cada asiento balancea y el libro cuadra."""
    cli, _ = _cliente_con_cuenta(db)
    # Reclasificación agrupada (conciliación)
    mc.registrar_reclasificacion_planilla(
        db, 1, ORG_ID, 1, cli.id, cli.nombre, Decimal("10000"), date(2026, 5, 20), "g.xlsx")
    # Liquidación aprobada (Cliente D / Banco H / Comisión H)
    mc.registrar_liquidacion_aprobacion(
        db, 1, 100, ORG_ID, 1, cli.id, cli.nombre,
        Decimal("10000"), Decimal("9800"), Decimal("200"), date(2026, 5, 31))
    # Cheque (3 líneas)
    mc.registrar_cheque(db, 1, ORG_ID, 1, cli.nombre, Decimal("5000"), Decimal("100"), date(2026, 5, 22))

    asientos = db.query(Asiento).filter(Asiento.organizacion_id == ORG_ID).all()
    assert len(asientos) >= 3
    for a in asientos:
        debe  = sum(l.debe  for l in a.lineas)
        haber = sum(l.haber for l in a.lineas)
        assert abs(debe - haber) < Decimal("0.01"), f"Asiento {a.modulo} no balancea: {debe} vs {haber}"

    # Invariante global del libro: Σdebe == Σhaber
    detalles = db.query(AsientoDetalle).join(Asiento).filter(Asiento.organizacion_id == ORG_ID).all()
    total_debe  = sum(l.debe  for l in detalles)
    total_haber = sum(l.haber for l in detalles)
    assert abs(total_debe - total_haber) < Decimal("0.01")


def test_crear_asiento_multilinea_rechaza_desbalanceado(db):
    """Red de seguridad: un asiento que no cuadra NO se postea."""
    c1 = _cuenta_id(db, "1-1-1-3-1")
    c2 = _cuenta_id(db, "2-1-2-0")
    mc._crear_asiento_multilinea(
        db, fecha=date(2026, 5, 20), descripcion="malo", modulo="test_bad",
        referencia_id=999, org_id=ORG_ID, usuario_id=1,
        lineas=[(c1, Decimal("100"), Decimal("0")), (c2, Decimal("0"), Decimal("80"))],  # 100 != 80
    )
    assert len(_asientos_de(db, "test_bad", 999)) == 0
