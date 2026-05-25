"""Búsqueda global — clientes, planillas, movimientos, cheques."""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.cliente import Cliente
from app.models.extracto import MovimientoBanco
from app.models.planilla import Planilla
from app.models.cheque import Cheque
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/search", tags=["search"])


def _resolver_org(user: User, org_id_param: Optional[int]) -> int:
    if org_id_param and user.is_superadmin:
        return org_id_param
    return user.organizacion_id or 1


@router.get("")
def search_global(
    q: str = Query("", min_length=0),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = q.strip()
    if len(q) < 2:
        return {"clientes": [], "planillas": [], "movimientos": [], "cheques": []}
    org = _resolver_org(current_user, org_id)
    term = f"%{q.lower()}%"

    clientes = (
        db.query(Cliente)
        .filter(Cliente.organizacion_id == org, func.lower(Cliente.nombre).like(term))
        .limit(6).all()
    )
    planillas = (
        db.query(Planilla)
        .join(Cliente, Planilla.cliente_id == Cliente.id, isouter=True)
        .filter(
            Planilla.organizacion_id == org,
            Planilla.deleted_at.is_(None),
            func.lower(Cliente.nombre).like(term),
        )
        .order_by(Planilla.fecha_carga.desc())
        .limit(5).all()
    )
    movimientos = (
        db.query(MovimientoBanco)
        .filter(
            MovimientoBanco.organizacion_id == org,
            func.lower(MovimientoBanco.titular).like(term),
        )
        .order_by(MovimientoBanco.fecha.desc())
        .limit(6).all()
    )
    cheques = (
        db.query(Cheque)
        .filter(
            Cheque.organizacion_id == org,
            func.lower(Cheque.emisor).like(term),
        )
        .order_by(Cheque.fecha_emision.desc())
        .limit(4).all()
    )

    return {
        "clientes": [{"id": c.id, "nombre": c.nombre} for c in clientes],
        "planillas": [
            {
                "id": p.id,
                "cliente": p.cliente.nombre if p.cliente else "—",
                "archivo": p.nombre_archivo,
                "fecha": str(p.fecha_carga)[:10] if p.fecha_carga else None,
            }
            for p in planillas
        ],
        "movimientos": [
            {
                "id": m.id,
                "titular": m.titular,
                "monto": float(m.monto or 0),
                "fecha": str(m.fecha) if m.fecha else None,
                "extracto_id": m.extracto_id,
            }
            for m in movimientos
        ],
        "cheques": [
            {
                "id": c.id,
                "numero": c.numero,
                "emisor": c.emisor,
                "monto": float(c.monto or 0),
            }
            for c in cheques
        ],
    }
