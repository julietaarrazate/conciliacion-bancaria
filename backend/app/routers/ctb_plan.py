"""Router contabilidad — Plan de cuentas y reglas contables.

Rutas expuestas (bajo el prefix /contabilidad del router padre):
  GET  /stats
  GET  /plan-cuentas
  GET  /reglas
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    oid = _org_id(current_user, org_id)
    cuentas = (
        db.query(PlanCuenta)
        .filter(PlanCuenta.organizacion_id == oid, PlanCuenta.activo == True)
        .order_by(PlanCuenta.codigo)
        .all()
    )
    return [
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
    ]


@router.get("/reglas")
def get_reglas(
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    oid = _org_id(current_user, org_id)
    reglas = (
        db.query(ReglaContable)
        .filter(ReglaContable.organizacion_id == oid, ReglaContable.activo == True)
        .order_by(ReglaContable.evento)
        .all()
    )
    return [
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
    ]
