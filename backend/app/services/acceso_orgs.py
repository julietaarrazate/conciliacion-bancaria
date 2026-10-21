"""Qué organizaciones puede ver/operar un usuario (vistas que cruzan orgs:
Vencimientos, Procesos masivos).

Superadmin: todas las activas. Resto: la propia + las de `allowed_org_ids`
(misma regla que `middleware.auth.can_switch_org`).
"""
from typing import Iterable, List, Optional

from sqlalchemy.orm import Session

from app.middleware.auth import can_switch_org
from app.models.organizacion import Organizacion
from app.models.user import User


def orgs_accesibles(db: Session, user: User, pedidas: Optional[Iterable[int]] = None) -> List[int]:
    """Ids de orgs activas accesibles, ordenados. Con `pedidas`, solo las que
    estén pedidas y sean accesibles (las ajenas se descartan sin error)."""
    q = db.query(Organizacion.id).filter(Organizacion.activo.isnot(False))
    if not user.is_superadmin:
        q = q.filter(Organizacion.id.in_({user.organizacion_id or 1, *(user.allowed_org_ids or [])}))
    if pedidas is not None:
        q = q.filter(Organizacion.id.in_(set(pedidas)))
    return [o.id for o in q.order_by(Organizacion.id).all()]


def puede_org(user: User, org_id: int) -> bool:
    return org_id == (user.organizacion_id or 1) or can_switch_org(user, org_id)
