from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select, func

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.bank_account import BankAccount
from app.models.bank_statement import BankStatement
from app.models.bank_transaction import BankTransaction
from app.models.accounting_entry import AccountingEntry
from app.models.planilla import MovimientoPlanilla, PlanillaCliente
from app.models.reconciliation import Reconciliation, ReconciliationItem
from app.models.user import User
from app.schemas.reconciliation import (
    AutoMatchResult,
    ManualMatchRequest,
    ReconciliationCreate,
    ReconciliationItemResponse,
    ReconciliationItemUpdate,
    ReconciliationResponse,
)
from app.services.matching_service import auto_match_full
from app.services.sync_service import (
    acreditar_transaccion_con_planilla,
    desacreditar_item,
)

router = APIRouter()


async def _get_owned_reconciliation(db: AsyncSession, recon_id: int, user_id: int) -> Reconciliation:
    result = await db.execute(
        select(Reconciliation).join(BankStatement).join(BankAccount).where(
            Reconciliation.id == recon_id, BankAccount.user_id == user_id,
        )
    )
    recon = result.scalar_one_or_none()
    if not recon:
        raise HTTPException(status_code=404, detail="Conciliación no encontrada")
    return recon


@router.get("/", response_model=list[ReconciliationResponse])
async def list_reconciliations(
    account_id: int | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Reconciliation).join(BankStatement).join(BankAccount).where(
        BankAccount.user_id == current_user.id
    )
    if account_id:
        query = query.where(BankStatement.account_id == account_id)
    if status:
        query = query.where(Reconciliation.status == status)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/", response_model=ReconciliationResponse, status_code=201)
async def create_reconciliation(
    body: ReconciliationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt_result = await db.execute(
        select(BankStatement).join(BankAccount).where(
            BankStatement.id == body.statement_id,
            BankAccount.user_id == current_user.id,
        )
    )
    statement = stmt_result.scalar_one_or_none()
    if not statement:
        raise HTTPException(status_code=404, detail="Extracto no encontrado")

    reconciliation = Reconciliation(statement_id=body.statement_id)
    db.add(reconciliation)
    await db.commit()
    await db.refresh(reconciliation)
    return reconciliation


@router.get("/{reconciliation_id}/items", response_model=list[ReconciliationItemResponse])
async def list_items(
    reconciliation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_owned_reconciliation(db, reconciliation_id, current_user.id)
    result = await db.execute(
        select(ReconciliationItem).where(ReconciliationItem.reconciliation_id == reconciliation_id)
    )
    return result.scalars().all()


@router.post("/{reconciliation_id}/auto-match", response_model=AutoMatchResult)
async def run_auto_match(
    reconciliation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    reconciliation = await _get_owned_reconciliation(db, reconciliation_id, current_user.id)
    statement = await db.get(BankStatement, reconciliation.statement_id)
    if not statement:
        raise HTTPException(status_code=404, detail="Extracto no encontrado")

    result = await auto_match_full(db, statement.id, statement.account_id)
    matches = result["matches"]

    for txn_id, entry_id in matches:
        db.add(ReconciliationItem(
            reconciliation_id=reconciliation_id,
            bank_transaction_id=txn_id,
            accounting_entry_id=entry_id,
            match_type="auto",
            estado="acreditado",
            matched_by=current_user.id,
        ))
        txn = await db.get(BankTransaction, txn_id)
        entry = await db.get(AccountingEntry, entry_id)
        if txn:
            txn.is_reconciled = True
            txn.estado = "acreditado"
        if entry:
            entry.is_reconciled = True

    reconciliation.status = "in_progress"
    unmatched = await _count_unmatched(db, statement.id)
    difference = await _calculate_difference(db, statement.id, statement.account_id)
    reconciliation.difference = difference
    await db.commit()

    return AutoMatchResult(
        matched=len(matches),
        unmatched=unmatched,
        difference=difference,
        no_esta=len(result["no_esta"]),
        faltan_datos=len(result["faltan_datos"]),
    )


@router.post("/{reconciliation_id}/items", response_model=ReconciliationItemResponse, status_code=201)
async def manual_match(
    reconciliation_id: int,
    body: ManualMatchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Acreditación manual. Si no se pasa accounting_entry_id, debe pasarse planilla_movimiento_id
    (acreditación a planilla del cliente, sin asiento contable previo)."""
    recon = await _get_owned_reconciliation(db, reconciliation_id, current_user.id)
    statement = await db.get(BankStatement, recon.statement_id)

    txn = await db.get(BankTransaction, body.bank_transaction_id)
    if not txn or txn.statement_id != statement.id:
        raise HTTPException(status_code=404, detail="Transacción no pertenece a este extracto")

    if not body.accounting_entry_id and not body.planilla_movimiento_id:
        raise HTTPException(
            status_code=422,
            detail="Debe especificar accounting_entry_id o planilla_movimiento_id",
        )

    if body.planilla_movimiento_id:
        mov_result = await db.execute(
            select(MovimientoPlanilla)
            .options(selectinload(MovimientoPlanilla.planilla))
            .where(MovimientoPlanilla.id == body.planilla_movimiento_id)
        )
        mov = mov_result.scalar_one_or_none()
        if not mov:
            raise HTTPException(status_code=404, detail="Movimiento de planilla no encontrado")
        item = await acreditar_transaccion_con_planilla(db, txn, mov, recon.id)
        item.observacion = body.observacion
        item.matched_by = current_user.id
    else:
        entry = await db.get(AccountingEntry, body.accounting_entry_id)
        if not entry or entry.account_id != statement.account_id:
            raise HTTPException(
                status_code=422,
                detail="El asiento no pertenece a la misma cuenta del extracto",
            )
        item = ReconciliationItem(
            reconciliation_id=recon.id,
            bank_transaction_id=txn.id,
            accounting_entry_id=entry.id,
            match_type="manual",
            estado=body.estado,
            observacion=body.observacion,
            matched_by=current_user.id,
        )
        db.add(item)
        txn.is_reconciled = True
        txn.estado = "acreditado"
        entry.is_reconciled = True

    await db.commit()
    await db.refresh(item)
    return item


@router.patch("/items/{item_id}", response_model=ReconciliationItemResponse)
async def update_item(
    item_id: int,
    body: ReconciliationItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Edita un reconciliation_item: cambiar estado, cambiar planilla destino, observación."""
    item = await db.get(ReconciliationItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item no encontrado")
    await _get_owned_reconciliation(db, item.reconciliation_id, current_user.id)

    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(item, k, v)
    await db.commit()
    await db.refresh(item)
    return item


@router.delete("/items/{item_id}", status_code=204)
async def delete_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Desacreditar: libera la transacción y el movimiento de planilla."""
    item = await db.get(ReconciliationItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item no encontrado")
    await _get_owned_reconciliation(db, item.reconciliation_id, current_user.id)
    await desacreditar_item(db, item)
    await db.delete(item)
    await db.commit()
    return None


@router.post("/{reconciliation_id}/close", response_model=ReconciliationResponse)
async def close_reconciliation(
    reconciliation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    reconciliation = await _get_owned_reconciliation(db, reconciliation_id, current_user.id)
    reconciliation.status = "closed"
    reconciliation.closed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(reconciliation)
    return reconciliation


async def _count_unmatched(db: AsyncSession, statement_id: int) -> int:
    result = await db.execute(
        select(func.count()).select_from(BankTransaction).where(
            BankTransaction.statement_id == statement_id,
            BankTransaction.is_reconciled == False,  # noqa: E712
        )
    )
    return result.scalar_one()


async def _calculate_difference(db: AsyncSession, statement_id: int, account_id: int) -> Decimal:
    statement = await db.get(BankStatement, statement_id)
    entry_result = await db.execute(
        select(func.sum(AccountingEntry.amount)).where(AccountingEntry.account_id == account_id)
    )
    accounting_total = entry_result.scalar_one() or Decimal("0")
    return (statement.closing_balance - accounting_total).quantize(Decimal("0.01"))
