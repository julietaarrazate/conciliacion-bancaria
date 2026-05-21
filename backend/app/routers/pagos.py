from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.pago import Pago
from app.models.user import User
from app.schemas.operaciones import PagoCreate, PagoResponse
from app.services.accounting_service import asiento_pago_cliente

router = APIRouter()


@router.get("/", response_model=list[PagoResponse])
async def list_pagos(
    cliente_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Pago)
    if cliente_id:
        query = query.where(Pago.cliente_id == cliente_id)
    result = await db.execute(query.order_by(Pago.fecha.desc()))
    return result.scalars().all()


@router.post("/", response_model=PagoResponse, status_code=201)
async def create_pago(
    body: PagoCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if body.medio not in ("banco", "efectivo"):
        raise HTTPException(status_code=422, detail="medio debe ser 'banco' o 'efectivo'")
    pago = Pago(**body.model_dump())
    db.add(pago)
    await db.flush()
    await asiento_pago_cliente(db, pago.fecha, pago.monto, pago.medio, pago.id)
    await db.commit()
    await db.refresh(pago)
    return pago
