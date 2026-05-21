from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.bank_account import BankAccount
from app.models.bank_statement import BankStatement
from app.models.bank_transaction import BankTransaction
from app.models.accounting_entry import AccountingEntry
from app.models.reconciliation import Reconciliation, ReconciliationItem
from app.models.user import User
from app.schemas.reconciliation import (
    AutoMatchResult,
    ManualMatchRequest,
    ReconciliationCreate,
    ReconciliationItemResponse,
    ReconciliationResponse,
)
from app.services.matching_service import auto_match

router = APIRouter()


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
    # Verificar que el extracto pertenece al usuario
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


@router.post("/{reconciliation_id}/auto-match", response_model=AutoMatchResult)
async def run_auto_match(
    reconciliation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    recon_result = await db.execute(
        select(Reconciliation).join(BankStatement).join(BankAccount).where(
            Reconciliation.id == reconciliation_id,
            BankAccount.user_id == current_user.id,
        )
    )
    reconciliation = recon_result.scalar_one_or_none()
    if not reconciliation:
        raise HTTPException(status_code=404, detail="Conciliación no encontrada")

    statement = await db.get(BankStatement, reconciliation.statement_id)
    matches = await auto_match(db, statement.id, statement.account_id)

    for txn_id, entry_id in matches:
        item = ReconciliationItem(
            reconciliation_id=reconciliation_id,
            bank_transaction_id=txn_id,
            accounting_entry_id=entry_id,
            match_type="auto",
            matched_by=current_user.id,
        )
        db.add(item)
        # Marcar como conciliados
        txn = await db.get(BankTransaction, txn_id)
        entry = await db.get(AccountingEntry, entry_id)
        if txn:
            txn.is_reconciled = True
        if entry:
            entry.is_reconciled = True

    reconciliation.status = "in_progress"
    await db.commit()

    # Calcular diferencia
    unmatched_count = await _count_unmatched(db, statement.id, statement.account_id)
    difference = await _calculate_difference(db, statement.id, statement.account_id)
    reconciliation.difference = difference
    await db.commit()

    return AutoMatchResult(
        matched=len(matches),
        unmatched=unmatched_count,
        difference=difference,
    )


@router.post("/{reconciliation_id}/items", response_model=ReconciliationItemResponse, status_code=201)
async def manual_match(
    reconciliation_id: int,
    body: ManualMatchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = ReconciliationItem(
        reconciliation_id=reconciliation_id,
        bank_transaction_id=body.bank_transaction_id,
        accounting_entry_id=body.accounting_entry_id,
        match_type="manual",
        matched_by=current_user.id,
    )
    db.add(item)

    txn = await db.get(BankTransaction, body.bank_transaction_id)
    entry = await db.get(AccountingEntry, body.accounting_entry_id)
    if txn:
        txn.is_reconciled = True
    if entry:
        entry.is_reconciled = True

    await db.commit()
    await db.refresh(item)
    return item


@router.post("/{reconciliation_id}/close", response_model=ReconciliationResponse)
async def close_reconciliation(
    reconciliation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    recon_result = await db.execute(
        select(Reconciliation).join(BankStatement).join(BankAccount).where(
            Reconciliation.id == reconciliation_id,
            BankAccount.user_id == current_user.id,
        )
    )
    reconciliation = recon_result.scalar_one_or_none()
    if not reconciliation:
        raise HTTPException(status_code=404, detail="Conciliación no encontrada")

    reconciliation.status = "closed"
    reconciliation.closed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(reconciliation)
    return reconciliation


async def _count_unmatched(db: AsyncSession, statement_id: int, account_id: int) -> int:
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
        select(func.sum(AccountingEntry.amount)).where(
            AccountingEntry.account_id == account_id,
        )
    )
    accounting_total = entry_result.scalar_one() or Decimal("0")
    return (statement.closing_balance - accounting_total).quantize(Decimal("0.01"))
