from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from typing import Optional
from datetime import datetime

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
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/historial", tags=["historial"])


@router.get("/planillas", response_model=HistorialPlanillasResponse)
def list_planillas(
    skip: int = 0,
    limit: int = 50,
    cliente: Optional[str] = Query(None),
    desde: Optional[datetime] = Query(None),
    hasta: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user)
):
    """Lista planillas reconciliadas con sus stats. Filtros por cliente y fechas."""
    q = db.query(Planilla).join(Cliente, Planilla.cliente_id == Cliente.id)

    if cliente:
        q = q.filter(Cliente.nombre.ilike(f"%{cliente}%"))
    if desde:
        q = q.filter(Planilla.fecha_carga >= desde)
    if hasta:
        q = q.filter(Planilla.fecha_carga <= hasta)

    total = q.count()
    planillas = (
        q.order_by(desc(Planilla.fecha_carga))
        .offset(skip)
        .limit(limit)
        .all()
    )

    items = []
    for p in planillas:
        statuses = [r.status for r in p.rows]
        items.append(
            PlanillaHistorialItem(
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
        )

    return {"total": total, "items": items}


@router.get("/extractos", response_model=HistorialExtractosResponse)
def list_extractos(
    skip: int = 0,
    limit: int = 50,
    desde: Optional[datetime] = Query(None),
    hasta: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user)
):
    """Lista extractos bancarios cargados"""
    q = db.query(ExtractoBancario)

    if desde:
        q = q.filter(ExtractoBancario.fecha_creacion >= desde)
    if hasta:
        q = q.filter(ExtractoBancario.fecha_creacion <= hasta)

    total = q.count()
    extractos = (
        q.order_by(desc(ExtractoBancario.fecha_creacion))
        .offset(skip)
        .limit(limit)
        .all()
    )

    items = []
    for e in extractos:
        items.append(
            ExtractoHistorialItem(
                id=e.id,
                nombre_archivo=e.nombre_archivo,
                fecha_creacion=e.fecha_creacion,
                usuario_nombre=e.creado_por_user.full_name,
                total_movimientos=len(e.movimientos)
            )
        )

    return {"total": total, "items": items}
