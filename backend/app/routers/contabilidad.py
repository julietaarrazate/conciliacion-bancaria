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
    CuentaTreeNode, MayorRow, SumasSaldosRow, BalanceRow,
)

router = APIRouter()


@router.get("/cuentas", response_model=list[CuentaContableResponse])
async def list_cuentas(
    imputable: bool | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(CuentaContable).order_by(CuentaContable.codigo)
    if imputable is not None:
        query = query.where(CuentaContable.imputable == imputable)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/cuentas/tree", response_model=list[CuentaTreeNode])
async def cuentas_tree(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Plan de cuentas en árbol con saldo agregado por nodo (suma de descendientes imputables)."""
    cuentas_result = await db.execute(select(CuentaContable).order_by(CuentaContable.codigo))
    cuentas = list(cuentas_result.scalars().all())

    # Saldo por cuenta imputable (debe - haber, ajustado por naturaleza)
    saldos_result = await db.execute(
        select(
            LineaAsiento.cuenta_id,
            func.coalesce(func.sum(LineaAsiento.debe - LineaAsiento.haber), 0),
        ).group_by(LineaAsiento.cuenta_id)
    )
    saldos: dict[int, Decimal] = {cid: Decimal(s) for cid, s in saldos_result.all()}

    # Construir nodos
    nodos: dict[int, CuentaTreeNode] = {}
    for c in cuentas:
        saldo_dh = saldos.get(c.id, Decimal("0"))
        saldo = -saldo_dh if c.naturaleza == "acreedora" else saldo_dh
        nodos[c.id] = CuentaTreeNode(
            id=c.id, codigo=c.codigo, nombre=c.nombre, tipo=c.tipo,
            naturaleza=c.naturaleza, nivel=c.nivel, imputable=c.imputable,
            cliente_id=c.cliente_id, saldo=saldo, hijas=[],
        )

    # Linkear hijas
    roots: list[CuentaTreeNode] = []
    for c in cuentas:
        nodo = nodos[c.id]
        if c.parent_id and c.parent_id in nodos:
            nodos[c.parent_id].hijas.append(nodo)
        else:
            roots.append(nodo)

    # Propagar saldos hacia arriba (cuentas resumen = suma de hijas)
    def agregar(n: CuentaTreeNode) -> Decimal:
        if not n.hijas:
            return n.saldo
        total = Decimal("0")
        for h in n.hijas:
            total += agregar(h)
        if not n.imputable:
            n.saldo = total
        return n.saldo

    for r in roots:
        agregar(r)
    return roots


@router.get("/libro-diario", response_model=list[AsientoResponse])
async def libro_diario(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Asientos cronológicos con sus líneas (incluye número correlativo)."""
    result = await db.execute(
        select(AsientoContable)
        .options(selectinload(AsientoContable.lineas).selectinload(LineaAsiento.cuenta))
        .order_by(AsientoContable.numero)
    )
    asientos = result.scalars().all()
    return [
        AsientoResponse(
            id=a.id, numero=a.numero, fecha=a.fecha, descripcion=a.descripcion,
            origen=a.origen, origen_id=a.origen_id, created_at=a.created_at,
            lineas=[
                LineaAsientoResponse(
                    id=l.id, cuenta_id=l.cuenta_id,
                    cuenta_codigo=l.cuenta.codigo if l.cuenta else None,
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
        .order_by(AsientoContable.numero)
    )
    rows = []
    saldo = Decimal("0")
    for linea, asiento in result.all():
        saldo += linea.debe - linea.haber
        rows.append(MayorRow(
            fecha=asiento.fecha, asiento_numero=asiento.numero,
            descripcion=asiento.descripcion,
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
            CuentaContable.id, CuentaContable.codigo, CuentaContable.nombre, CuentaContable.nivel,
            func.coalesce(func.sum(LineaAsiento.debe), 0).label("sd"),
            func.coalesce(func.sum(LineaAsiento.haber), 0).label("sh"),
        )
        .outerjoin(LineaAsiento, LineaAsiento.cuenta_id == CuentaContable.id)
        .where(CuentaContable.imputable == True)  # noqa: E712
        .group_by(CuentaContable.id, CuentaContable.codigo, CuentaContable.nombre, CuentaContable.nivel)
        .order_by(CuentaContable.codigo)
    )
    rows = []
    for cid, codigo, nombre, nivel, sd, sh in result.all():
        sd, sh = Decimal(sd), Decimal(sh)
        diff = sd - sh
        rows.append(SumasSaldosRow(
            cuenta_id=cid, codigo=codigo, nombre=nombre, nivel=nivel,
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
    """Saldo final por cuenta jerárquico (cuentas resumen = suma de hijas)."""
    cuentas_result = await db.execute(
        select(CuentaContable).order_by(CuentaContable.codigo)
    )
    cuentas = list(cuentas_result.scalars().all())

    saldos_imp_result = await db.execute(
        select(
            LineaAsiento.cuenta_id,
            func.coalesce(func.sum(LineaAsiento.debe - LineaAsiento.haber), 0),
        ).group_by(LineaAsiento.cuenta_id)
    )
    saldos: dict[int, Decimal] = {cid: Decimal(s) for cid, s in saldos_imp_result.all()}

    # Propagar saldos a padres: ordenar de hojas a raíz (mayor nivel primero)
    by_id = {c.id: c for c in cuentas}
    cuentas_orden = sorted(cuentas, key=lambda c: -c.nivel)
    saldo_final: dict[int, Decimal] = {}
    for c in cuentas_orden:
        if c.imputable:
            saldo_final[c.id] = saldos.get(c.id, Decimal("0"))
        else:
            total = sum(
                (saldo_final.get(h.id, Decimal("0")) for h in cuentas if h.parent_id == c.id),
                Decimal("0"),
            )
            saldo_final[c.id] = total

    rows = []
    for c in cuentas:
        s = saldo_final.get(c.id, Decimal("0"))
        if c.naturaleza == "acreedora":
            s = -s
        rows.append(BalanceRow(
            cuenta_id=c.id, codigo=c.codigo, nombre=c.nombre,
            tipo=c.tipo, nivel=c.nivel, parent_id=c.parent_id, saldo=s,
        ))
    return rows
