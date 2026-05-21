"""Sincronización bidireccional Extracto ↔ Planilla de cliente.

Reglas:
  - Si un movimiento de planilla pasa a estado 'ok' → buscar/crear el reconciliation_item
    correspondiente en el extracto activo y marcar la bank_transaction como acreditada.
  - Si una bank_transaction se acredita (manual o auto) y tiene planilla_movimiento_id →
    actualizar ese movimiento a estado 'ok' con fecha_acreditacion = fecha del extracto.
  - Al borrar un reconciliation_item: liberar el movimiento (estado vuelve a 'pendiente') y
    liberar la transacción (is_reconciled=False, estado=pendiente).
"""
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.bank_statement import BankStatement
from app.models.bank_transaction import BankTransaction
from app.models.planilla import MovimientoPlanilla
from app.models.reconciliation import Reconciliation, ReconciliationItem


async def acreditar_movimiento(
    db: AsyncSession, movimiento: MovimientoPlanilla, fecha_acred: date
) -> ReconciliationItem | None:
    """Cuando una planilla marca un movimiento como 'ok', sincroniza con el extracto activo."""
    movimiento.estado = "ok"
    movimiento.fecha_acreditacion = fecha_acred

    # Buscar bank_transaction asociada (si existe)
    result = await db.execute(
        select(BankTransaction).where(BankTransaction.planilla_movimiento_id == movimiento.id)
    )
    txn = result.scalar_one_or_none()
    if not txn:
        return None

    txn.is_reconciled = True
    txn.estado = "acreditado"

    # Reconciliation del extracto donde está esa txn
    recon_result = await db.execute(
        select(Reconciliation).where(Reconciliation.statement_id == txn.statement_id)
    )
    recon = recon_result.scalar_one_or_none()
    if not recon:
        return None

    # ¿Existe ya item para esta txn?
    item_result = await db.execute(
        select(ReconciliationItem).where(
            ReconciliationItem.reconciliation_id == recon.id,
            ReconciliationItem.bank_transaction_id == txn.id,
        )
    )
    item = item_result.scalar_one_or_none()
    if item:
        item.estado = "acreditado"
        item.planilla_movimiento_id = movimiento.id
    else:
        item = ReconciliationItem(
            reconciliation_id=recon.id,
            bank_transaction_id=txn.id,
            planilla_movimiento_id=movimiento.id,
            match_type="sync_planilla",
            estado="acreditado",
        )
        db.add(item)
    return item


async def desacreditar_item(db: AsyncSession, item: ReconciliationItem) -> None:
    """Al borrar/cambiar un item, libera la transacción y el movimiento de planilla."""
    if item.bank_transaction_id:
        txn = await db.get(BankTransaction, item.bank_transaction_id)
        if txn:
            txn.is_reconciled = False
            txn.estado = "pendiente"
    if item.planilla_movimiento_id:
        mov = await db.get(MovimientoPlanilla, item.planilla_movimiento_id)
        if mov:
            mov.estado = "pendiente"
            mov.fecha_acreditacion = None


async def acreditar_transaccion_con_planilla(
    db: AsyncSession, txn: BankTransaction, mov: MovimientoPlanilla, recon_id: int
) -> ReconciliationItem:
    """Acreditación manual en extracto, eligiendo la planilla destino del cliente."""
    txn.is_reconciled = True
    txn.estado = "acreditado"
    txn.planilla_movimiento_id = mov.id
    txn.cliente_id = mov.planilla.cliente_id if mov.planilla else txn.cliente_id

    mov.estado = "ok"
    mov.fecha_acreditacion = txn.transaction_date

    item = ReconciliationItem(
        reconciliation_id=recon_id,
        bank_transaction_id=txn.id,
        planilla_movimiento_id=mov.id,
        match_type="manual",
        estado="acreditado",
    )
    db.add(item)
    return item
