from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.bank_account import BankAccount
from app.models.bank_statement import BankStatement
from app.models.bank_transaction import BankTransaction
from app.models.user import User
from app.schemas.reconciliation import BankStatementResponse, BankTransactionResponse
from app.services.import_service import detect_and_parse, ImportError as ParseImportError

router = APIRouter()


@router.get("/", response_model=list[BankStatementResponse])
async def list_statements(
    account_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(BankStatement).join(BankAccount).where(BankAccount.user_id == current_user.id)
    if account_id:
        query = query.where(BankStatement.account_id == account_id)
    result = await db.execute(query.order_by(BankStatement.period_end.desc()))
    return result.scalars().all()


@router.post("/upload", response_model=BankStatementResponse, status_code=201)
async def upload_statement(
    account_id: int = Form(...),
    period_start: str = Form(...),       # YYYY-MM-DD
    period_end: str = Form(...),         # YYYY-MM-DD
    opening_balance: str = Form(...),    # "1500.00"
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verificar que la cuenta pertenece al usuario
    acc_result = await db.execute(
        select(BankAccount).where(
            BankAccount.id == account_id,
            BankAccount.user_id == current_user.id,
        )
    )
    if not acc_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")

    # Parsear el archivo
    content = await file.read()
    try:
        parsed_txns = detect_and_parse(file.filename or "upload.csv", content)
    except ParseImportError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Calcular saldo de cierre
    opening = Decimal(opening_balance)
    total_movement = sum(t.amount for t in parsed_txns)
    closing = opening + total_movement

    # Crear extracto
    from datetime import date
    statement = BankStatement(
        account_id=account_id,
        period_start=date.fromisoformat(period_start),
        period_end=date.fromisoformat(period_end),
        opening_balance=opening,
        closing_balance=closing,
        status="draft",
    )
    db.add(statement)
    await db.flush()  # para obtener statement.id

    # Crear transacciones
    for t in parsed_txns:
        txn = BankTransaction(
            statement_id=statement.id,
            transaction_date=t.transaction_date,
            description=t.description,
            amount=t.amount,
            reference=t.reference,
        )
        db.add(txn)

    await db.commit()
    await db.refresh(statement)
    return statement


@router.get("/{statement_id}/transactions", response_model=list[BankTransactionResponse])
async def list_transactions(
    statement_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verificar ownership
    stmt_result = await db.execute(
        select(BankStatement).join(BankAccount).where(
            BankStatement.id == statement_id,
            BankAccount.user_id == current_user.id,
        )
    )
    if not stmt_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Extracto no encontrado")

    result = await db.execute(
        select(BankTransaction)
        .where(BankTransaction.statement_id == statement_id)
        .order_by(BankTransaction.transaction_date)
    )
    return result.scalars().all()
