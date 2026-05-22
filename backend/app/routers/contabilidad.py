from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.contabilidad import PlanCuenta, ReglaContable, Asiento

router = APIRouter(prefix="/contabilidad", tags=["contabilidad"])


def _org_id(current_user: User, org_id: Optional[int]) -> int:
    if current_user.is_superadmin and org_id:
        return org_id
    return current_user.organizacion_id or 1


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


@router.get("/asientos")
def get_asientos(
    org_id: Optional[int] = Query(None),
    desde: Optional[str] = Query(None),
    hasta: Optional[str] = Query(None),
    modulo: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    oid = _org_id(current_user, org_id)
    q = db.query(Asiento).filter(Asiento.organizacion_id == oid)
    if desde:
        q = q.filter(Asiento.fecha >= desde)
    if hasta:
        q = q.filter(Asiento.fecha <= hasta)
    if modulo:
        q = q.filter(Asiento.modulo == modulo)
    total = q.count()
    items = q.order_by(Asiento.fecha.desc(), Asiento.id.desc()).offset(skip).limit(limit).all()
    return {
        "total": total,
        "items": [
            {
                "id": a.id,
                "fecha": a.fecha,
                "descripcion": a.descripcion,
                "modulo": a.modulo,
                "referencia_id": a.referencia_id,
                "created_at": a.created_at,
            }
            for a in items
        ],
    }


@router.get("/asientos/{asiento_id}")
def get_asiento_detalle(
    asiento_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    oid = current_user.organizacion_id or 1
    a = db.query(Asiento).filter(Asiento.id == asiento_id).first()
    if not a:
        raise HTTPException(404, "Asiento no encontrado")
    if not current_user.is_superadmin and a.organizacion_id != oid:
        raise HTTPException(403, "Sin acceso")
    return {
        "id": a.id,
        "fecha": a.fecha,
        "descripcion": a.descripcion,
        "modulo": a.modulo,
        "referencia_id": a.referencia_id,
        "created_at": a.created_at,
        "lineas": [
            {
                "id": l.id,
                "cuenta": {
                    "id": l.cuenta.id,
                    "codigo": l.cuenta.codigo,
                    "nombre": l.cuenta.nombre,
                },
                "debe": l.debe,
                "haber": l.haber,
            }
            for l in a.lineas
        ],
    }
