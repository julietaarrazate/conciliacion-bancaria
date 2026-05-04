from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, case
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
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/historial", tags=["historial"])


def _build_planillas_query(db: Session, current_user: User, cliente=None, desde=None, hasta=None, org_id=None):
    """Query que agrega stats de planilla_rows en SQL — sin N+1."""
    stats = (
        db.query(
            PlanillaRow.planilla_id,
            func.count(PlanillaRow.id).label("total_filas"),
            func.sum(case((PlanillaRow.status == "ok", 1), else_=0)).label("acreditadas"),
            func.sum(case((PlanillaRow.status == "no está", 1), else_=0)).label("no_encontradas"),
            func.sum(case((PlanillaRow.status == "duplicado", 1), else_=0)).label("duplicadas"),
            func.sum(case((PlanillaRow.status == "faltan datos", 1), else_=0)).label("sin_datos"),
        )
        .group_by(PlanillaRow.planilla_id)
        .subquery()
    )

    q = (
        db.query(
            Planilla,
            Cliente.nombre,
            User.full_name,
            stats.c.total_filas,
            stats.c.acreditadas,
            stats.c.no_encontradas,
            stats.c.duplicadas,
            stats.c.sin_datos,
        )
        .join(Cliente, Planilla.cliente_id == Cliente.id)
        .join(User, Planilla.usuario_id == User.id)
        .outerjoin(stats, Planilla.id == stats.c.planilla_id)
    )

    if current_user.is_superadmin and org_id:
        q = q.filter(Planilla.organizacion_id == org_id)
    elif not current_user.is_superadmin:
        q = q.filter(Planilla.organizacion_id == (current_user.organizacion_id or 1))

    if cliente:
        q = q.filter(Cliente.nombre.ilike(f"%{cliente}%"))
    if desde:
        q = q.filter(Planilla.fecha_carga >= desde)
    if hasta:
        q = q.filter(Planilla.fecha_carga <= hasta)

    return q


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
    q = _build_planillas_query(db, current_user, cliente, desde, hasta, org_id)
    total = q.count()
    rows = q.order_by(desc(Planilla.fecha_carga)).offset(skip).limit(limit).all()

    items = [
        PlanillaHistorialItem(
            id=p.id,
            cliente_nombre=c_nombre,
            nombre_archivo=p.nombre_archivo,
            fecha_carga=p.fecha_carga,
            usuario_nombre=u_nombre,
            total_filas=int(s_total or 0),
            acreditadas=int(s_ok or 0),
            no_encontradas=int(s_no or 0),
            duplicadas=int(s_dup or 0),
            sin_datos=int(s_sin or 0),
        )
        for p, c_nombre, u_nombre, s_total, s_ok, s_no, s_dup, s_sin in rows
    ]

    return {"total": total, "items": items}


@router.get("/planillas/export")
def export_historial_xlsx(
    cliente: Optional[str] = Query(None),
    desde: Optional[datetime] = Query(None),
    hasta: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    q = _build_planillas_query(db, current_user, cliente, desde, hasta)
    rows = q.order_by(desc(Planilla.fecha_carga)).all()

    items = [
        {
            "cliente_nombre": c_nombre,
            "nombre_archivo": p.nombre_archivo,
            "fecha_carga": p.fecha_carga,
            "usuario_nombre": u_nombre,
            "total_filas": int(s_total or 0),
            "acreditadas": int(s_ok or 0),
            "no_encontradas": int(s_no or 0),
            "duplicadas": int(s_dup or 0),
            "sin_datos": int(s_sin or 0),
        }
        for p, c_nombre, u_nombre, s_total, s_ok, s_no, s_dup, s_sin in rows
    ]

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
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user)
):
    mov_count = (
        db.query(MovimientoBanco.extracto_id, func.count(MovimientoBanco.id).label("total"))
        .group_by(MovimientoBanco.extracto_id)
        .subquery()
    )

    q = (
        db.query(ExtractoBancario, User.full_name, mov_count.c.total)
        .join(User, ExtractoBancario.creado_por == User.id)
        .outerjoin(mov_count, ExtractoBancario.id == mov_count.c.extracto_id)
    )

    if desde:
        q = q.filter(ExtractoBancario.fecha_creacion >= desde)
    if hasta:
        q = q.filter(ExtractoBancario.fecha_creacion <= hasta)

    total = q.count()
    rows = q.order_by(desc(ExtractoBancario.fecha_creacion)).offset(skip).limit(limit).all()

    items = [
        ExtractoHistorialItem(
            id=e.id,
            nombre_archivo=e.nombre_archivo,
            fecha_creacion=e.fecha_creacion,
            usuario_nombre=u_nombre,
            total_movimientos=int(mov_total or 0),
        )
        for e, u_nombre, mov_total in rows
    ]

    return {"total": total, "items": items}
