from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select, func

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.asiento_contable import AsientoContable, LineaAsiento
from app.models.cuenta_contable import CuentaContable
from app.models.user import User
from app.schemas.contabilidad import (
    AsientoResponse, LineaAsientoResponse, CuentaContableResponse,
    MayorRow, SumasSaldosRow, BalanceRow,
)

router = APIRouter()


@router.get("/cuentas", response_model=list[CuentaContableResponse])
async def list_cuentas(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(CuentaContable).order_by(CuentaContable.codigo))
    return result.scalars().all()


@router.get("/libro-diario", response_model=list[AsientoResponse])
async def libro_diario(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Todos los asientos cronológicos con sus líneas."""
    result = await db.execute(
        select(AsientoContable)
        .options(selectinload(AsientoContable.lineas).selectinload(LineaAsiento.cuenta))
        .order_by(AsientoContable.fecha, AsientoContable.id)
    )
    asientos = result.scalars().all()
    return [
        AsientoResponse(
            id=a.id, fecha=a.fecha, descripcion=a.descripcion,
            origen=a.origen, origen_id=a.origen_id, created_at=a.created_at,
            lineas=[
                LineaAsientoResponse(
                    id=l.id, cuenta_id=l.cuenta_id,
                    cuenta_nombre=l.cuenta.nombre if l.cuenta else None,
                    debe=l.debe, haber=l.haber,
                ) for l in a.lineas
            ],
        ) for a in asientos
    ]


@router.get("/libro-mayor/{cuenta_id}", response_model=list[MayorRow])
async def libro_mayor(
    cuenta_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Movimientos cronológicos de una cuenta con saldo acumulado."""
    result = await db.execute(
        select(LineaAsiento, AsientoContable)
        .join(AsientoContable, AsientoContable.id == LineaAsiento.asiento_id)
        .where(LineaAsiento.cuenta_id == cuenta_id)
        .order_by(AsientoContable.fecha, AsientoContable.id)
    )
    rows = []
    saldo = Decimal("0")
    for linea, asiento in result.all():
        saldo += linea.debe - linea.haber
        rows.append(MayorRow(
            fecha=asiento.fecha, descripcion=asiento.descripcion,
            debe=linea.debe, haber=linea.haber, saldo=saldo,
        ))
    return rows


@router.get("/sumas-y-saldos", response_model=list[SumasSaldosRow])
async def sumas_y_saldos(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(
            CuentaContable.id, CuentaContable.codigo, CuentaContable.nombre,
            func.coalesce(func.sum(LineaAsiento.debe), 0).label("suma_debe"),
            func.coalesce(func.sum(LineaAsiento.haber), 0).label("suma_haber"),
        )
        .outerjoin(LineaAsiento, LineaAsiento.cuenta_id == CuentaContable.id)
        .group_by(CuentaContable.id, CuentaContable.codigo, CuentaContable.nombre)
        .order_by(CuentaContable.codigo)
    )
    rows = []
    for cid, codigo, nombre, sd, sh in result.all():
        sd, sh = Decimal(sd), Decimal(sh)
        diff = sd - sh
        rows.append(SumasSaldosRow(
            cuenta_id=cid, codigo=codigo, nombre=nombre,
            suma_debe=sd, suma_haber=sh,
            saldo_deudor=diff if diff > 0 else Decimal("0"),
            saldo_acreedor=-diff if diff < 0 else Decimal("0"),
        ))
    return rows


@router.get("/balance", response_model=list[BalanceRow])
async def balance(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Saldo final por cuenta (signo según naturaleza)."""
    result = await db.execute(
        select(
            CuentaContable.id, CuentaContable.codigo, CuentaContable.nombre,
            CuentaContable.tipo, CuentaContable.naturaleza,
            func.coalesce(func.sum(LineaAsiento.debe - LineaAsiento.haber), 0).label("saldo_dh"),
        )
        .outerjoin(LineaAsiento, LineaAsiento.cuenta_id == CuentaContable.id)
        .group_by(CuentaContable.id)
        .order_by(CuentaContable.codigo)
    )
    rows = []
    for cid, codigo, nombre, tipo, nat, saldo_dh in result.all():
        saldo = Decimal(saldo_dh)
        # Para cuentas acreedoras invertimos el signo para mostrar positivo
        if nat == "acreedora":
            saldo = -saldo
        rows.append(BalanceRow(
            cuenta_id=cid, codigo=codigo, nombre=nombre, tipo=tipo, saldo=saldo,
        ))
    return rows
