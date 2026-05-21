from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.cliente import Cliente
from app.models.planilla import PlanillaCliente
from app.models.user import User
from app.schemas.cliente import ClienteCreate, ClienteResponse, ClienteUpdate
from app.schemas.planilla import PlanillaResponse

router = APIRouter()


@router.get("/", response_model=list[ClienteResponse])
async def list_clientes(
    activo: bool | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Cliente)
    if activo is not None:
        query = query.where(Cliente.activo == activo)
    result = await db.execute(query.order_by(Cliente.nombre))
    return result.scalars().all()


@router.post("/", response_model=ClienteResponse, status_code=201)
async def create_cliente(
    body: ClienteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Crear cliente nuevo, sin requerir conciliación previa."""
    cliente = Cliente(**body.model_dump())
    db.add(cliente)
    await db.commit()
    await db.refresh(cliente)
    return cliente


@router.get("/{cliente_id}", response_model=ClienteResponse)
async def get_cliente(
    cliente_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cliente = await db.get(Cliente, cliente_id)
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return cliente


@router.patch("/{cliente_id}", response_model=ClienteResponse)
async def update_cliente(
    cliente_id: int,
    body: ClienteUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cliente = await db.get(Cliente, cliente_id)
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(cliente, k, v)
    await db.commit()
    await db.refresh(cliente)
    return cliente


@router.get("/{cliente_id}/planillas", response_model=list[PlanillaResponse])
async def list_planillas_cliente(
    cliente_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Listar planillas del cliente para poblar el selector en acreditación manual."""
    result = await db.execute(
        select(PlanillaCliente).where(PlanillaCliente.cliente_id == cliente_id).order_by(
            PlanillaCliente.created_at.desc()
        )
    )
    return result.scalars().all()
