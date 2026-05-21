from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.cheque import Cheque
from app.models.user import User
from app.schemas.operaciones import (
    ChequeCreate, ChequeResponse, ChequeAcreditar, ChequeRechazar,
)
from app.services.accounting_service import (
    asiento_cheque_carga, asiento_cheque_acreditacion, asiento_cheque_rechazo,
)

router = APIRouter()


@router.get("/", response_model=list[ChequeResponse])
async def list_cheques(
    cliente_id: int | None = None,
    estado: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Cheque)
    if cliente_id:
        query = query.where(Cheque.cliente_id == cliente_id)
    if estado:
        query = query.where(Cheque.estado == estado)
    result = await db.execute(query.order_by(Cheque.fecha_cobro.desc()))
    return result.scalars().all()


@router.post("/", response_model=ChequeResponse, status_code=201)
async def create_cheque(
    body: ChequeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cheque = Cheque(**body.model_dump())
    db.add(cheque)
    await db.flush()
    await asiento_cheque_carga(
        db, cheque.fecha_emision, cheque.monto, cheque.comision,
        cheque.numero, cheque.id, cheque.cliente_id,
    )
    await db.commit()
    await db.refresh(cheque)
    return cheque


@router.post("/{cheque_id}/acreditar", response_model=ChequeResponse)
async def acreditar_cheque(
    cheque_id: int,
    body: ChequeAcreditar,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cheque = await db.get(Cheque, cheque_id)
    if not cheque:
        raise HTTPException(status_code=404, detail="Cheque no encontrado")
    if cheque.estado != "cargado":
        raise HTTPException(status_code=422, detail=f"Cheque está en estado {cheque.estado}")
    cheque.estado = "acreditado"
    cheque.fecha_acreditacion = body.fecha_acreditacion
    await asiento_cheque_acreditacion(
        db, body.fecha_acreditacion, cheque.monto, cheque.numero, cheque.id
    )
    await db.commit()
    await db.refresh(cheque)
    return cheque


@router.post("/{cheque_id}/rechazar", response_model=ChequeResponse)
async def rechazar_cheque(
    cheque_id: int,
    body: ChequeRechazar,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cheque = await db.get(Cheque, cheque_id)
    if not cheque:
        raise HTTPException(status_code=404, detail="Cheque no encontrado")
    if cheque.estado != "cargado":
        raise HTTPException(status_code=422, detail=f"Cheque está en estado {cheque.estado}")
    cheque.estado = "rechazado"
    cheque.motivo_rechazo = body.motivo
    await asiento_cheque_rechazo(
        db, cheque.fecha_cobro, cheque.monto, cheque.numero, cheque.id, cheque.cliente_id,
    )
    await db.commit()
    await db.refresh(cheque)
    return cheque
