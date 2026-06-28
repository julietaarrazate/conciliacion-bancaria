"""Router contabilidad — Plan de cuentas y reglas contables.

Rutas expuestas (bajo el prefix /contabilidad del router padre):
  GET  /stats
  GET  /plan-cuentas
  GET  /reglas
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.contabilidad import Asiento, AsientoDetalle, PlanCuenta, ReglaContable
from app.models.user import User
from .ctb_common import _org_id

router = APIRouter(tags=["contabilidad"])


@router.get("/stats")
def get_stats(
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Conteos del módulo contable."""
    oid = _org_id(current_user, org_id)
    return {
        "plan_cuentas":    db.query(PlanCuenta).filter(PlanCuenta.organizacion_id == oid).count(),
        "reglas":          db.query(ReglaContable).filter(ReglaContable.organizacion_id == oid).count(),
        "asientos":        db.query(Asiento).filter(Asiento.organizacion_id == oid).count(),
        "asiento_detalle": db.query(AsientoDetalle).join(Asiento).filter(Asiento.organizacion_id == oid).count(),
    }


@router.get("/plan-cuentas")
def get_plan_cuentas(
    org_id: Optional[int] = Query(None),
    limit: int = Query(1000, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    oid = _org_id(current_user, org_id)
    q = (
        db.query(PlanCuenta)
        .filter(PlanCuenta.organizacion_id == oid, PlanCuenta.activo == True)
        .order_by(PlanCuenta.codigo)
    )
    total = q.count()
    cuentas = q.offset(offset).limit(limit).all()
    return {
        "items": [
            {
                "id": c.id,
                "codigo": c.codigo,
                "nombre": c.nombre,
                "tipo": c.tipo,
                "parent_id": c.parent_id,
                "nivel": c.nivel,
                "activo": c.activo,
            }
            for c in cuentas
        ],
        "total": total,
    }


@router.get("/reglas")
def get_reglas(
    org_id: Optional[int] = Query(None),
    limit: int = Query(1000, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    oid = _org_id(current_user, org_id)
    q = (
        db.query(ReglaContable)
        .filter(ReglaContable.organizacion_id == oid, ReglaContable.activo == True)
        .order_by(ReglaContable.evento)
    )
    total = q.count()
    # selectinload de las cuentas debe/haber: antes cada regla disparaba 2
    # queries extra (N+1) al serializar r.cuenta_debe / r.cuenta_haber.
    reglas = (
        q.options(
            selectinload(ReglaContable.cuenta_debe),
            selectinload(ReglaContable.cuenta_haber),
        )
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "items": [
            {
                "id": r.id,
                "evento": r.evento,
                "descripcion": r.descripcion,
                "debe": {
                    "id": r.cuenta_debe.id,
                    "codigo": r.cuenta_debe.codigo,
                    "nombre": r.cuenta_debe.nombre,
                },
                "haber": {
                    "id": r.cuenta_haber.id,
                    "codigo": r.cuenta_haber.codigo,
                    "nombre": r.cuenta_haber.nombre,
                },
            }
            for r in reglas
        ],
        "total": total,
    }
