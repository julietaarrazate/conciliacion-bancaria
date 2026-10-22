from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, selectinload, joinedload
from sqlalchemy import and_, case, desc, func
from typing import Optional
from datetime import datetime
import io

from app.database import get_db
from app.models.user import User
from app.models.planilla import Planilla, PlanillaRow
from app.models.extracto import ExtractoBancario, MovimientoBanco
from app.models.cliente import Cliente
from app.schemas.historial import (
    HistorialPlanillasResponse,
    HistorialExtractosResponse,
    PlanillaHistorialItem,
    ExtractoHistorialItem
)
from app.services.excel_export import export_historial_planillas
from app.middleware.auth import get_current_user, can_switch_org

router = APIRouter(prefix="/historial", tags=["historial"])


@router.get("/planillas", response_model=HistorialPlanillasResponse)
def list_planillas(
    skip: int = 0,
    limit: int = 50,
    cliente: Optional[str] = Query(None),
    desde: Optional[datetime] = Query(None),
    hasta: Optional[datetime] = Query(None),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lista planillas reconciliadas con sus stats. Filtros por cliente y fechas."""
    q = (
        db.query(Planilla)
        .join(Cliente, Planilla.cliente_id == Cliente.id)
        .filter(Planilla.deleted_at.is_(None))
    )

    # Aislamiento por org
    if can_switch_org(current_user, org_id) and org_id:
        q = q.filter(Planilla.organizacion_id == org_id)
    elif not current_user.is_superadmin:
        q = q.filter(Planilla.organizacion_id == (current_user.organizacion_id or 1))

    if cliente:
        q = q.filter(Cliente.nombre.ilike(f"%{cliente}%"))
    if desde:
        q = q.filter(Planilla.fecha_carga >= desde)
    if hasta:
        q = q.filter(Planilla.fecha_carga <= hasta)

    total = q.count()
    planillas = (
        q.options(
            joinedload(Planilla.cliente),
            joinedload(Planilla.usuario),
        )
        .order_by(desc(Planilla.fecha_carga))
        .offset(skip)
        .limit(limit)
        .all()
    )

    # Stats por planilla agregadas en SQL: (planilla, status) → cantidad y suma de
    # montos. Antes se cargaban TODAS las filas de cada planilla (selectinload) para
    # contarlas en Python.
    por_status: dict[int, dict] = {}
    if planillas:
        for pid, status, cant, suma in (
            db.query(PlanillaRow.planilla_id, PlanillaRow.status,
                     func.count(PlanillaRow.id), func.sum(PlanillaRow.monto))
            .filter(PlanillaRow.planilla_id.in_([p.id for p in planillas]))
            .group_by(PlanillaRow.planilla_id, PlanillaRow.status)
            .all()
        ):
            por_status.setdefault(pid, {})[status] = (int(cant or 0), suma)

    items = []
    for p in planillas:
        stats = por_status.get(p.id, {})
        n_status = {st: c for st, (c, _) in stats.items()}
        statuses = list(n_status)
        ok_suma = stats.get("ok", (0, None))[1]
        monto_ok = float(ok_suma) if ok_suma is not None else 0
        items.append(
            PlanillaHistorialItem(
                id=p.id,
                cliente_nombre=p.cliente.nombre,
                nombre_archivo=p.nombre_archivo,
                fecha_carga=p.fecha_carga,
                usuario_nombre=(p.usuario.full_name if p.usuario else "—"),
                total_filas=sum(n_status.values()),
                acreditadas=n_status.get("ok", 0),
                no_encontradas=n_status.get("no está", 0),
                duplicadas=sum(
                    n_status[s] for s in statuses
                    if s == "duplicado" or (isinstance(s, str) and s.startswith("acreditado"))
                ),
                sin_datos=n_status.get("faltan datos", 0),
                monto_conciliado=monto_ok,
                porcentaje_comision=float(p.porcentaje_comision) if p.porcentaje_comision is not None else None,
            )
        )

    return {"total": total, "items": items}


@router.get("/planillas/export")
def export_historial_xlsx(
    cliente: Optional[str] = Query(None),
    desde: Optional[datetime] = Query(None),
    hasta: Optional[datetime] = Query(None),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Descarga xlsx con el historial de planillas reconciliadas"""
    q = (
        db.query(Planilla)
        .join(Cliente, Planilla.cliente_id == Cliente.id)
        .filter(Planilla.deleted_at.is_(None))
    )

    # Aislamiento multi-tenant
    if can_switch_org(current_user, org_id) and org_id:
        q = q.filter(Planilla.organizacion_id == org_id)
    elif not current_user.is_superadmin:
        q = q.filter(Planilla.organizacion_id == (current_user.organizacion_id or 1))

    if cliente:
        q = q.filter(Cliente.nombre.ilike(f"%{cliente}%"))
    if desde:
        q = q.filter(Planilla.fecha_carga >= desde)
    if hasta:
        q = q.filter(Planilla.fecha_carga <= hasta)

    planillas = (
        q.options(
            selectinload(Planilla.rows),
            joinedload(Planilla.cliente),
            joinedload(Planilla.usuario),
        )
        .order_by(desc(Planilla.fecha_carga))
        .all()
    )

    items = []
    for p in planillas:
        statuses = [r.status for r in p.rows]
        items.append({
            "cliente_nombre": p.cliente.nombre,
            "nombre_archivo": p.nombre_archivo,
            "fecha_carga": p.fecha_carga,
            "usuario_nombre": (p.usuario.full_name if p.usuario else "—"),
            "total_filas": len(statuses),
            "acreditadas": sum(1 for s in statuses if s == "ok"),
            "no_encontradas": sum(1 for s in statuses if s == "no está"),
            "duplicadas": sum(
                1 for s in statuses
                if s == "duplicado" or (isinstance(s, str) and s.startswith("acreditado"))
            ),
            "sin_datos": sum(1 for s in statuses if s == "faltan datos")
        })

    xlsx_bytes = export_historial_planillas(items)
    filename = f"historial_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return StreamingResponse(
        io.BytesIO(xlsx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/extractos", response_model=HistorialExtractosResponse)
def list_extractos(
    skip: int = 0,
    limit: int = 50,
    desde: Optional[datetime] = Query(None),
    hasta: Optional[datetime] = Query(None),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lista extractos bancarios cargados"""
    q = db.query(ExtractoBancario).filter(ExtractoBancario.deleted_at.is_(None))

    # Aislamiento multi-tenant
    if can_switch_org(current_user, org_id) and org_id:
        q = q.filter(ExtractoBancario.organizacion_id == org_id)
    elif not current_user.is_superadmin:
        q = q.filter(ExtractoBancario.organizacion_id == (current_user.organizacion_id or 1))

    if desde:
        q = q.filter(ExtractoBancario.fecha_creacion >= desde)
    if hasta:
        q = q.filter(ExtractoBancario.fecha_creacion <= hasta)

    total = q.count()
    extractos = (
        q.options(joinedload(ExtractoBancario.creado_por_user))
        .order_by(desc(ExtractoBancario.fecha_creacion))
        .offset(skip)
        .limit(limit)
        .all()
    )

    # Totales por extracto en SQL (antes: selectinload de TODOS los movimientos para
    # contarlos en Python). "Acreditado" = cliente_acreditado no nulo ni vacío, igual
    # que el `if m.cliente_acreditado` anterior.
    conteos = {}
    if extractos:
        acreditado = and_(MovimientoBanco.cliente_acreditado.isnot(None),
                          MovimientoBanco.cliente_acreditado != "")
        conteos = {
            ext_id: (int(total or 0), int(acred or 0))
            for ext_id, total, acred in (
                db.query(
                    MovimientoBanco.extracto_id,
                    func.count(MovimientoBanco.id),
                    func.sum(case((acreditado, 1), else_=0)),
                )
                .filter(MovimientoBanco.extracto_id.in_([e.id for e in extractos]))
                .group_by(MovimientoBanco.extracto_id)
                .all()
            )
        }

    items = []
    for e in extractos:
        total_movs, acred = conteos.get(e.id, (0, 0))
        items.append(
            ExtractoHistorialItem(
                id=e.id,
                nombre_archivo=e.nombre_archivo,
                fecha_creacion=e.fecha_creacion,
                usuario_nombre=(e.creado_por_user.full_name if e.creado_por_user else "—"),
                total_movimientos=total_movs,
                acreditados=acred,
                banco=e.banco or "Banco Macro",
                archivado=e.archivado_at is not None,
            )
        )

    return {"total": total, "items": items}
