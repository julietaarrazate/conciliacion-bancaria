from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import desc, func
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


def _planilla_to_item(p: Planilla) -> PlanillaHistorialItem:
    statuses = [r.status for r in p.rows]
    return PlanillaHistorialItem(
        id=p.id,
        cliente_nombre=p.cliente.nombre,
        nombre_archivo=p.nombre_archivo,
        fecha_carga=p.fecha_carga,
        usuario_nombre=p.usuario.full_name,
        total_filas=len(statuses),
        acreditadas=sum(1 for s in statuses if s == "ok"),
        no_encontradas=sum(1 for s in statuses if s == "no está"),
        duplicadas=sum(
            1 for s in statuses
            if s == "duplicado" or (isinstance(s, str) and s.startswith("acreditado"))
        ),
        sin_datos=sum(1 for s in statuses if s == "faltan datos")
    )


def _build_q(db, current_user, cliente=None, desde=None, hasta=None, org_id=None):
    q = (
        db.query(Planilla)
        .join(Cliente, Planilla.cliente_id == Cliente.id)
        .options(
            joinedload(Planilla.cliente),
            joinedload(Planilla.usuario),
            selectinload(Planilla.rows),
        )
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
    q = _build_q(db, current_user, cliente, desde, hasta, org_id)
    total = db.query(func.count(Planilla.id)).filter(
        Planilla.organizacion_id == (current_user.organizacion_id or 1) if not current_user.is_superadmin else True
    ).scalar() or 0
    planillas = q.order_by(desc(Planilla.fecha_carga)).offset(skip).limit(limit).all()
    return {"total": total, "items": [_planilla_to_item(p) for p in planillas]}


@router.get("/planillas/export")
def export_historial_xlsx(
    cliente: Optional[str] = Query(None),
    desde: Optional[datetime] = Query(None),
    hasta: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    planillas = _build_q(db, current_user, cliente, desde, hasta).order_by(desc(Planilla.fecha_carga)).all()
    items = []
    for p in planillas:
        statuses = [r.status for r in p.rows]
        items.append({
            "cliente_nombre": p.cliente.nombre,
            "nombre_archivo": p.nombre_archivo,
            "fecha_carga": p.fecha_carga,
            "usuario_nombre": p.usuario.full_name,
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
    return {
        "total": total,
        "items": [
            ExtractoHistorialItem(
                id=e.id,
                nombre_archivo=e.nombre_archivo,
                fecha_creacion=e.fecha_creacion,
                usuario_nombre=u_nombre,
                total_movimientos=int(mov_total or 0),
            )
            for e, u_nombre, mov_total in rows
        ]
    }
