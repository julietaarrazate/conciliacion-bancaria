from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.gasto import Gasto
from app.models.user import User
from app.schemas.operaciones import GastoCreate, GastoResponse
from app.services.accounting_service import asiento_gasto

router = APIRouter()


@router.get("/", response_model=list[GastoResponse])
async def list_gastos(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Gasto).order_by(Gasto.fecha.desc()))
    return result.scalars().all()


@router.post("/", response_model=GastoResponse, status_code=201)
async def create_gasto(
    body: GastoCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if body.medio not in ("banco", "efectivo"):
        raise HTTPException(status_code=422, detail="medio debe ser 'banco' o 'efectivo'")
    gasto = Gasto(**body.model_dump())
    db.add(gasto)
    await db.flush()
    await asiento_gasto(db, gasto.fecha, gasto.monto, gasto.medio, gasto.concepto, gasto.id)
    await db.commit()
    await db.refresh(gasto)
    return gasto
