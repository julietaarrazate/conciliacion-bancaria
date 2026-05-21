from datetime import date as date_type

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.planilla import PlanillaCliente, MovimientoPlanilla
from app.models.user import User
from app.schemas.planilla import (
    PlanillaCreate, PlanillaResponse,
    MovimientoPlanillaCreate, MovimientoPlanillaResponse, MovimientoPlanillaUpdate,
)
from app.services.sync_service import acreditar_movimiento

router = APIRouter()


@router.get("/", response_model=list[PlanillaResponse])
async def list_planillas(
    cliente_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(PlanillaCliente)
    if cliente_id:
        query = query.where(PlanillaCliente.cliente_id == cliente_id)
    result = await db.execute(query.order_by(PlanillaCliente.created_at.desc()))
    return result.scalars().all()


@router.post("/", response_model=PlanillaResponse, status_code=201)
async def create_planilla(
    body: PlanillaCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    p = PlanillaCliente(**body.model_dump())
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p


@router.get("/{planilla_id}/movimientos", response_model=list[MovimientoPlanillaResponse])
async def list_movimientos(
    planilla_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(MovimientoPlanilla)
        .where(MovimientoPlanilla.planilla_id == planilla_id)
        .order_by(MovimientoPlanilla.fecha)
    )
    return result.scalars().all()


@router.post("/movimientos", response_model=MovimientoPlanillaResponse, status_code=201)
async def create_movimiento(
    body: MovimientoPlanillaCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    mov = MovimientoPlanilla(**body.model_dump())
    db.add(mov)
    await db.commit()
    await db.refresh(mov)
    return mov


@router.patch("/movimientos/{movimiento_id}", response_model=MovimientoPlanillaResponse)
async def update_movimiento(
    movimiento_id: int,
    body: MovimientoPlanillaUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Modificar un movimiento. Si el estado pasa a 'ok', sincroniza con extracto (acredita)."""
    mov = await db.get(MovimientoPlanilla, movimiento_id)
    if not mov:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")

    data = body.model_dump(exclude_unset=True)
    nuevo_estado = data.pop("estado", None)
    fecha_acred = data.pop("fecha_acreditacion", None)

    for k, v in data.items():
        setattr(mov, k, v)

    if nuevo_estado == "ok":
        await acreditar_movimiento(db, mov, fecha_acred or date_type.today())
    elif nuevo_estado:
        mov.estado = nuevo_estado
        if fecha_acred:
            mov.fecha_acreditacion = fecha_acred

    await db.commit()
    await db.refresh(mov)
    return mov


@router.delete("/movimientos/{movimiento_id}", status_code=204)
async def delete_movimiento(
    movimiento_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Borra un movimiento de la planilla. NO afecta otros extractos."""
    mov = await db.get(MovimientoPlanilla, movimiento_id)
    if not mov:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    await db.delete(mov)
    await db.commit()
    return None
