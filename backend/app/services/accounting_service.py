"""Generación automática de asientos contables (Debe/Haber).

Plan de cuentas jerárquico (4 niveles, código X-X-X-X). Solo las cuentas IMPUTABLES
(hojas, nivel 4 mayormente) reciben asientos.

Códigos relevantes:
  1-1-1-1  Caja chica
  1-1-1-2  Efectivo
  1-1-1-3  Banco
  1-1-2-0  Creditos               (imputable)
  2-1-1-1  No identificado        (cliente sin asignar)
  2-1-2-X  Cliente <X>            (Green, Tucu, Alojando, +clientes creados)
  3-1-1-0  Comisiones
  3-2-1-0  Impuesto deb y cred
  3-2-2-0  Gastos bancarios

Mapeo (mapa del contador):
  Carga extracto bancario:   Debe Banco            / Haber Pasivo (cliente o no identificado)
  Carga archivos clientes:   Debe Pasivo (s/i)     / Haber Pasivo Cliente + Comisiones
  Carga efectivo:            Debe Efectivo + Com.  / Haber Banco
  Cheque (carga):            Debe Crédito          / Haber Pasivo Cliente + Comisiones
  Cheque (acreditación):     Debe Banco            / Haber Crédito
  Cheque (rechazo):          Debe Pasivo Cliente   / Haber Crédito
  Pago cliente (banco):      Debe Pasivo Cliente   / Haber Banco
  Pago cliente (efectivo):   Debe Pasivo Cliente   / Haber Efectivo
  Gasto bancario:            Debe Gastos bancarios / Haber Banco
  Gasto en efectivo:         Debe Gastos bancarios / Haber Efectivo
"""
from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.models.asiento_contable import AsientoContable, LineaAsiento
from app.models.cuenta_contable import CuentaContable


# Códigos canónicos del plan de cuentas
COD_BANCO = "1-1-1-3"
COD_EFECTIVO = "1-1-1-2"
COD_CAJA = "1-1-1-1"
COD_CREDITO = "1-1-2-0"
COD_NO_IDENTIFICADO = "2-1-1-1"
COD_CLIENTE_PARENT = "2-1-2-0"
COD_COMISIONES = "3-1-1-0"
COD_IMPUESTO_DEBCRED = "3-2-1-0"
COD_GASTOS_BANCARIOS = "3-2-2-0"


async def _cuenta_por_codigo(db: AsyncSession, codigo: str) -> CuentaContable:
    result = await db.execute(select(CuentaContable).where(CuentaContable.codigo == codigo))
    cuenta = result.scalar_one_or_none()
    if not cuenta:
        raise ValueError(f"Cuenta contable {codigo} no existe")
    if not cuenta.imputable:
        raise ValueError(f"Cuenta {codigo} no es imputable (es un rubro resumen)")
    return cuenta


async def cuenta_pasivo_cliente(db: AsyncSession, cliente_id: int | None) -> CuentaContable:
    """Devuelve la sub-cuenta bajo '2-1-2 Cliente' que corresponde al cliente.
    Si no hay cliente_id o no existe sub-cuenta → 'No identificado' (2-1-1-1)."""
    if cliente_id:
        result = await db.execute(
            select(CuentaContable).where(CuentaContable.cliente_id == cliente_id)
        )
        cuenta = result.scalar_one_or_none()
        if cuenta:
            return cuenta
    return await _cuenta_por_codigo(db, COD_NO_IDENTIFICADO)


async def crear_cuenta_para_cliente(
    db: AsyncSession, cliente_id: int, nombre: str
) -> CuentaContable:
    """Auto-crea la sub-cuenta bajo 2-1-2 cuando se da de alta un cliente."""
    parent_result = await db.execute(
        select(CuentaContable).where(CuentaContable.codigo == COD_CLIENTE_PARENT)
    )
    parent = parent_result.scalar_one()

    # Buscar el siguiente número libre bajo 2-1-2-X
    used = await db.execute(
        select(CuentaContable.codigo).where(CuentaContable.parent_id == parent.id)
    )
    used_codes = {row[0] for row in used.all()}
    next_n = 1
    while f"{COD_CLIENTE_PARENT[:-2]}-{next_n}" in used_codes:
        next_n += 1
    codigo = f"{COD_CLIENTE_PARENT[:-2]}-{next_n}"

    cuenta = CuentaContable(
        codigo=codigo, nombre=nombre, tipo="pasivo", naturaleza="acreedora",
        nivel=4, parent_id=parent.id, imputable=True, cliente_id=cliente_id,
    )
    db.add(cuenta)
    await db.flush()
    return cuenta


async def _siguiente_numero(db: AsyncSession) -> int:
    """Número correlativo de asiento (atómico)."""
    result = await db.execute(
        text("UPDATE secuencias SET valor = valor + 1 WHERE clave='asiento' RETURNING valor")
    )
    return result.scalar_one()


async def crear_asiento_por_codigos(
    db: AsyncSession,
    fecha: date,
    descripcion: str,
    origen: str,
    origen_id: int | None,
    lineas: list[tuple[str, Decimal, Decimal]],
) -> AsientoContable:
    """Crea un asiento. lineas = [(codigo_cuenta, debe, haber), ...].
    Valida que debe == haber y que todas las cuentas sean imputables."""
    # Filtrar líneas con monto 0
    lineas = [(c, d, h) for c, d, h in lineas if d > 0 or h > 0]

    total_debe = sum(l[1] for l in lineas)
    total_haber = sum(l[2] for l in lineas)
    if total_debe != total_haber:
        raise ValueError(f"Asiento desbalanceado: debe={total_debe} haber={total_haber}")
    if total_debe == 0:
        raise ValueError("Asiento vacío")

    numero = await _siguiente_numero(db)
    asiento = AsientoContable(
        numero=numero, fecha=fecha, descripcion=descripcion,
        origen=origen, origen_id=origen_id,
    )
    db.add(asiento)
    await db.flush()

    for codigo, debe, haber in lineas:
        cuenta = await _cuenta_por_codigo(db, codigo)
        db.add(LineaAsiento(
            asiento_id=asiento.id, cuenta_id=cuenta.id, debe=debe, haber=haber,
        ))
    await db.flush()
    return asiento


# === Generadores por operación (usan códigos) ===

async def asiento_acreditacion_extracto(
    db: AsyncSession, fecha: date, monto: Decimal, referencia: str,
    txn_id: int, cliente_id: int | None = None,
) -> AsientoContable:
    cliente_cta = await cuenta_pasivo_cliente(db, cliente_id)
    return await crear_asiento_por_codigos(
        db, fecha, f"Acreditación: {referencia}", "acreditacion_extracto", txn_id,
        [(COD_BANCO, monto, Decimal("0")), (cliente_cta.codigo, Decimal("0"), monto)],
    )


async def asiento_acreditacion_efectivo(
    db: AsyncSession, fecha: date, monto: Decimal, comision: Decimal, ref_id: int,
) -> AsientoContable:
    return await crear_asiento_por_codigos(
        db, fecha, "Acreditación en efectivo", "acreditacion_efectivo", ref_id,
        [
            (COD_EFECTIVO, monto - comision, Decimal("0")),
            (COD_COMISIONES, Decimal("0"), comision),  # comisión es ingreso
            (COD_BANCO, Decimal("0"), monto - comision),
        ],
    )


async def asiento_cheque_carga(
    db: AsyncSession, fecha: date, monto: Decimal, comision: Decimal,
    numero: str, cheque_id: int, cliente_id: int,
) -> AsientoContable:
    cliente_cta = await cuenta_pasivo_cliente(db, cliente_id)
    neto = monto - comision
    return await crear_asiento_por_codigos(
        db, fecha, f"Cheque cargado #{numero}", "cheque_carga", cheque_id,
        [
            (COD_CREDITO, monto, Decimal("0")),
            (cliente_cta.codigo, Decimal("0"), neto),
            (COD_COMISIONES, Decimal("0"), comision),
        ],
    )


async def asiento_cheque_acreditacion(
    db: AsyncSession, fecha: date, monto: Decimal, numero: str, cheque_id: int,
) -> AsientoContable:
    return await crear_asiento_por_codigos(
        db, fecha, f"Cheque acreditado #{numero}", "cheque_acreditacion", cheque_id,
        [(COD_BANCO, monto, Decimal("0")), (COD_CREDITO, Decimal("0"), monto)],
    )


async def asiento_cheque_rechazo(
    db: AsyncSession, fecha: date, monto: Decimal, numero: str,
    cheque_id: int, cliente_id: int,
) -> AsientoContable:
    cliente_cta = await cuenta_pasivo_cliente(db, cliente_id)
    return await crear_asiento_por_codigos(
        db, fecha, f"Cheque rechazado #{numero}", "cheque_rechazo", cheque_id,
        [(cliente_cta.codigo, monto, Decimal("0")), (COD_CREDITO, Decimal("0"), monto)],
    )


async def asiento_pago_cliente(
    db: AsyncSession, fecha: date, monto: Decimal, medio: str,
    pago_id: int, cliente_id: int,
) -> AsientoContable:
    cliente_cta = await cuenta_pasivo_cliente(db, cliente_id)
    cuenta_haber = COD_BANCO if medio == "banco" else COD_EFECTIVO
    return await crear_asiento_por_codigos(
        db, fecha, f"Pago a cliente ({medio})", "pago_cliente", pago_id,
        [(cliente_cta.codigo, monto, Decimal("0")), (cuenta_haber, Decimal("0"), monto)],
    )


async def asiento_gasto(
    db: AsyncSession, fecha: date, monto: Decimal, medio: str,
    concepto: str, gasto_id: int, cuenta_gasto_codigo: str = COD_GASTOS_BANCARIOS,
) -> AsientoContable:
    cuenta_haber = COD_BANCO if medio == "banco" else COD_EFECTIVO
    return await crear_asiento_por_codigos(
        db, fecha, f"Gasto: {concepto}", "gasto", gasto_id,
        [(cuenta_gasto_codigo, monto, Decimal("0")), (cuenta_haber, Decimal("0"), monto)],
    )
