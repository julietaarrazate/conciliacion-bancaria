"""Generación automática de asientos contables (Debe/Haber) según el mapa del contador.

Mapa:
  - Acreditación (carga extracto):   Debe Banco            / Haber Pasivo Corriente
  - Acreditación (archivo cliente):  Debe Pasivo Corriente / Haber Pasivo Cliente + Comisiones
  - Acreditación (efectivo):         Debe Efectivo + Comisiones / Haber Banco
  - Cheque (carga):                  Debe Crédito          / Haber Pasivo Cliente + Comisiones
  - Cheque (acreditación):           Debe Banco            / Haber Crédito
  - Cheque (rechazo):                Debe Pasivo Cliente   / Haber Crédito
  - Pago cliente (banco):            Debe Pasivo Cliente   / Haber Banco
  - Pago cliente (efectivo):         Debe Pasivo Cliente   / Haber Efectivo
  - Gasto:                           Debe Gasto            / Haber Banco|Efectivo
"""
from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.asiento_contable import AsientoContable, LineaAsiento
from app.models.cuenta_contable import CuentaContable


async def _cuenta(db: AsyncSession, nombre: str) -> CuentaContable:
    """Busca una cuenta por nombre. Falla si no existe (debe estar en el seed)."""
    result = await db.execute(select(CuentaContable).where(CuentaContable.nombre == nombre))
    cuenta = result.scalar_one_or_none()
    if not cuenta:
        raise ValueError(f"Cuenta contable '{nombre}' no existe en el plan de cuentas")
    return cuenta


async def crear_asiento(
    db: AsyncSession,
    fecha: date,
    descripcion: str,
    origen: str,
    origen_id: int | None,
    lineas: list[tuple[str, Decimal, Decimal]],
) -> AsientoContable:
    """Crea un asiento con sus líneas. lineas = [(cuenta_nombre, debe, haber), ...].
    Valida que debe == haber (asiento balanceado)."""
    total_debe = sum(l[1] for l in lineas)
    total_haber = sum(l[2] for l in lineas)
    if total_debe != total_haber:
        raise ValueError(f"Asiento desbalanceado: debe={total_debe} haber={total_haber}")

    asiento = AsientoContable(
        fecha=fecha, descripcion=descripcion, origen=origen, origen_id=origen_id
    )
    db.add(asiento)
    await db.flush()

    for cuenta_nombre, debe, haber in lineas:
        cuenta = await _cuenta(db, cuenta_nombre)
        db.add(LineaAsiento(
            asiento_id=asiento.id, cuenta_id=cuenta.id, debe=debe, haber=haber
        ))
    await db.flush()
    return asiento


# === Generadores por operación ===

async def asiento_acreditacion_extracto(
    db: AsyncSession, fecha: date, monto: Decimal, referencia: str, txn_id: int
) -> AsientoContable:
    return await crear_asiento(
        db, fecha, f"Acreditación extracto: {referencia}", "acreditacion_extracto", txn_id,
        [("Banco", monto, Decimal("0")), ("Pasivo Corriente", Decimal("0"), monto)],
    )


async def asiento_acreditacion_cliente(
    db: AsyncSession, fecha: date, monto: Decimal, comision: Decimal,
    descripcion: str, mov_id: int
) -> AsientoContable:
    neto = monto - comision
    return await crear_asiento(
        db, fecha, f"Acreditación cliente: {descripcion}", "acreditacion_cliente", mov_id,
        [
            ("Pasivo Corriente", monto, Decimal("0")),
            ("Pasivo Cliente", Decimal("0"), neto),
            ("Comisiones", Decimal("0"), comision),
        ],
    )


async def asiento_acreditacion_efectivo(
    db: AsyncSession, fecha: date, monto: Decimal, comision: Decimal, ref_id: int
) -> AsientoContable:
    neto_efectivo = monto - comision
    return await crear_asiento(
        db, fecha, "Acreditación efectivo", "acreditacion_efectivo", ref_id,
        [
            ("Efectivo", neto_efectivo, Decimal("0")),
            ("Comisiones", comision, Decimal("0")),
            ("Banco", Decimal("0"), monto),
        ],
    )


async def asiento_cheque_carga(
    db: AsyncSession, fecha: date, monto: Decimal, comision: Decimal,
    numero: str, cheque_id: int
) -> AsientoContable:
    neto = monto - comision
    return await crear_asiento(
        db, fecha, f"Cheque cargado #{numero}", "cheque_carga", cheque_id,
        [
            ("Credito", monto, Decimal("0")),
            ("Pasivo Cliente", Decimal("0"), neto),
            ("Comisiones", Decimal("0"), comision),
        ],
    )


async def asiento_cheque_acreditacion(
    db: AsyncSession, fecha: date, monto: Decimal, numero: str, cheque_id: int
) -> AsientoContable:
    return await crear_asiento(
        db, fecha, f"Cheque acreditado #{numero}", "cheque_acreditacion", cheque_id,
        [("Banco", monto, Decimal("0")), ("Credito", Decimal("0"), monto)],
    )


async def asiento_cheque_rechazo(
    db: AsyncSession, fecha: date, monto: Decimal, numero: str, cheque_id: int
) -> AsientoContable:
    return await crear_asiento(
        db, fecha, f"Cheque rechazado #{numero}", "cheque_rechazo", cheque_id,
        [("Pasivo Cliente", monto, Decimal("0")), ("Credito", Decimal("0"), monto)],
    )


async def asiento_pago_cliente(
    db: AsyncSession, fecha: date, monto: Decimal, medio: str, pago_id: int
) -> AsientoContable:
    """medio: 'banco' o 'efectivo'."""
    cuenta_credito = "Banco" if medio == "banco" else "Efectivo"
    return await crear_asiento(
        db, fecha, f"Pago a cliente ({medio})", "pago_cliente", pago_id,
        [("Pasivo Cliente", monto, Decimal("0")), (cuenta_credito, Decimal("0"), monto)],
    )


async def asiento_gasto(
    db: AsyncSession, fecha: date, monto: Decimal, medio: str,
    concepto: str, gasto_id: int
) -> AsientoContable:
    cuenta_credito = "Banco" if medio == "banco" else "Efectivo"
    return await crear_asiento(
        db, fecha, f"Gasto: {concepto}", "gasto", gasto_id,
        [("Gasto", monto, Decimal("0")), (cuenta_credito, Decimal("0"), monto)],
    )
