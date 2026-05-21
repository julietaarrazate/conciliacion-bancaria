import csv
import io
from datetime import date as date_type
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.bank_account import BankAccount
from app.models.bank_statement import BankStatement
from app.models.bank_transaction import BankTransaction
from app.models.cliente import Cliente
from app.models.planilla import MovimientoPlanilla
from app.models.user import User
from app.schemas.reconciliation import (
    BankStatementResponse, BankTransactionResponse,
    BankTransactionCreateManual, BankTransactionUpdate,
)
from app.services.import_service import detect_and_parse, ImportError as ParseImportError

router = APIRouter()


async def _owned_statement(db: AsyncSession, statement_id: int, user_id: int) -> BankStatement:
    result = await db.execute(
        select(BankStatement).join(BankAccount).where(
            BankStatement.id == statement_id, BankAccount.user_id == user_id,
        )
    )
    stmt = result.scalar_one_or_none()
    if not stmt:
        raise HTTPException(status_code=404, detail="Extracto no encontrado")
    return stmt


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
    period_start: str = Form(...),
    period_end: str = Form(...),
    opening_balance: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    acc_result = await db.execute(
        select(BankAccount).where(
            BankAccount.id == account_id, BankAccount.user_id == current_user.id,
        )
    )
    if not acc_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")

    content = await file.read()
    try:
        parsed_txns = detect_and_parse(file.filename or "upload.csv", content)
    except ParseImportError as e:
        raise HTTPException(status_code=422, detail=str(e))

    opening = Decimal(opening_balance)
    total_movement = sum((t.amount for t in parsed_txns), Decimal("0"))
    closing = opening + total_movement

    try:
        statement = BankStatement(
            account_id=account_id,
            period_start=date_type.fromisoformat(period_start),
            period_end=date_type.fromisoformat(period_end),
            opening_balance=opening,
            closing_balance=closing,
            status="draft",
        )
        db.add(statement)
        await db.flush()

        for t in parsed_txns:
            db.add(BankTransaction(
                statement_id=statement.id,
                transaction_date=t.transaction_date,
                description=t.description,
                amount=t.amount,
                reference=t.reference,
            ))
        await db.commit()
        await db.refresh(statement)
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al importar: {e}")
    return statement


@router.get("/{statement_id}/transactions", response_model=list[BankTransactionResponse])
async def list_transactions(
    statement_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _owned_statement(db, statement_id, current_user.id)
    result = await db.execute(
        select(BankTransaction)
        .where(BankTransaction.statement_id == statement_id)
        .order_by(BankTransaction.transaction_date)
    )
    return result.scalars().all()


@router.post("/{statement_id}/transactions", response_model=BankTransactionResponse, status_code=201)
async def add_manual_transaction(
    statement_id: int,
    body: BankTransactionCreateManual,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Agregar una UM manual al extracto."""
    await _owned_statement(db, statement_id, current_user.id)
    txn = BankTransaction(
        statement_id=statement_id, es_manual=True, **body.model_dump()
    )
    db.add(txn)
    await db.commit()
    await db.refresh(txn)
    return txn


@router.patch("/transactions/{txn_id}", response_model=BankTransactionResponse)
async def update_transaction(
    txn_id: int,
    body: BankTransactionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Editar manualmente cualquier dato de una fila del extracto (incluyendo acreditadas)."""
    txn = await db.get(BankTransaction, txn_id)
    if not txn:
        raise HTTPException(status_code=404, detail="Transacción no encontrada")
    await _owned_statement(db, txn.statement_id, current_user.id)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(txn, k, v)
    await db.commit()
    await db.refresh(txn)
    return txn


@router.delete("/transactions/{txn_id}", status_code=204)
async def delete_transaction(
    txn_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Borrar una UM (incluido si está acreditada)."""
    txn = await db.get(BankTransaction, txn_id)
    if not txn:
        raise HTTPException(status_code=404, detail="Transacción no encontrada")
    await _owned_statement(db, txn.statement_id, current_user.id)
    await db.delete(txn)
    await db.commit()


@router.delete("/{statement_id}", status_code=204)
async def delete_statement(
    statement_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Borrar extracto: SOLO borra las transacciones del extracto. Las planillas y movimientos
    de clientes permanecen intactas (las FK son SET NULL)."""
    stmt = await _owned_statement(db, statement_id, current_user.id)
    await db.delete(stmt)
    await db.commit()


@router.get("/{statement_id}/export")
async def export_statement(
    statement_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Exportar extracto a CSV con estado + cliente + planilla destino + fecha acreditación."""
    await _owned_statement(db, statement_id, current_user.id)
    result = await db.execute(
        select(BankTransaction, Cliente, MovimientoPlanilla)
        .outerjoin(Cliente, Cliente.id == BankTransaction.cliente_id)
        .outerjoin(MovimientoPlanilla, MovimientoPlanilla.id == BankTransaction.planilla_movimiento_id)
        .where(BankTransaction.statement_id == statement_id)
        .order_by(BankTransaction.transaction_date)
    )

    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow([
        "Fecha", "Descripcion", "Monto", "Referencia", "Estado",
        "Cliente", "CUIT", "Planilla mov.", "Fecha acreditacion original", "Manual",
    ])
    for txn, cliente, mov in result.all():
        w.writerow([
            txn.transaction_date.isoformat(),
            txn.description, str(txn.amount), txn.reference or "",
            txn.estado,
            cliente.nombre if cliente else "",
            cliente.cuit if cliente else "",
            mov.id if mov else "",
            txn.fecha_acreditacion_original.isoformat() if txn.fecha_acreditacion_original else "",
            "S" if txn.es_manual else "N",
        ])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=extracto_{statement_id}.csv"},
    )
