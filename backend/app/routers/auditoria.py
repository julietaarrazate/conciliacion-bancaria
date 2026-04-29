from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Optional
from datetime import datetime

from app.database import get_db
from app.models.auditoria import AuditoriaLog
from app.models.user import User
from app.schemas.auditoria import AuditoriaListResponse, AuditoriaLogResponse
from app.middleware.auth import require_permission

router = APIRouter(prefix="/auditoria", tags=["auditoria"])


@router.get("", response_model=AuditoriaListResponse)
def list_auditoria(
    skip: int = 0,
    limit: int = 100,
    tabla: Optional[str] = Query(None),
    accion: Optional[str] = Query(None),
    usuario_id: Optional[int] = Query(None),
    desde: Optional[datetime] = Query(None),
    hasta: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("view_audit"))
):
    """
    Lista logs de auditoría con filtros opcionales.
    Requiere permiso 'view_audit' (admin o auditor).
    """
    q = db.query(AuditoriaLog)

    if tabla:
        q = q.filter(AuditoriaLog.tabla == tabla)
    if accion:
        q = q.filter(AuditoriaLog.accion == accion)
    if usuario_id is not None:
        q = q.filter(AuditoriaLog.usuario_id == usuario_id)
    if desde:
        q = q.filter(AuditoriaLog.timestamp >= desde)
    if hasta:
        q = q.filter(AuditoriaLog.timestamp <= hasta)

    total = q.count()

    rows = (
        q.order_by(desc(AuditoriaLog.timestamp))
        .offset(skip)
        .limit(limit)
        .all()
    )

    items = []
    for log in rows:
        items.append(
            AuditoriaLogResponse(
                id=log.id,
                usuario_id=log.usuario_id,
                usuario_nombre=log.usuario.full_name if log.usuario else None,
                usuario_email=log.usuario.email if log.usuario else None,
                tabla=log.tabla,
                registro_id=log.registro_id,
                accion=log.accion,
                cambios=log.cambios,
                timestamp=log.timestamp
            )
        )

    return {"total": total, "items": items}
