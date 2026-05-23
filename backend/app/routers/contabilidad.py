from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from typing import Optional

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.contabilidad import PlanCuenta, ReglaContable, Asiento, AsientoDetalle

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


# ── Fase 3: Reportes contables ────────────────────────────────────────────────

@router.get("/libro-mayor")
def get_libro_mayor(
    cuenta_id: int = Query(..., description="ID de la cuenta a consultar"),
    desde: Optional[str] = Query(None),
    hasta: Optional[str] = Query(None),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Movimientos de una cuenta con saldo acumulado (libro mayor)."""
    oid = _org_id(current_user, org_id)
    cuenta = db.query(PlanCuenta).filter(PlanCuenta.id == cuenta_id).first()
    if not cuenta:
        raise HTTPException(404, "Cuenta no encontrada")

    q = (
        db.query(AsientoDetalle, Asiento)
        .join(Asiento, AsientoDetalle.asiento_id == Asiento.id)
        .filter(
            AsientoDetalle.cuenta_id == cuenta_id,
            Asiento.organizacion_id == oid,
        )
    )
    if desde:
        q = q.filter(Asiento.fecha >= desde)
    if hasta:
        q = q.filter(Asiento.fecha <= hasta)
    q = q.order_by(Asiento.fecha, Asiento.id)

    movimientos = []
    saldo = 0.0
    for detalle, asiento in q.all():
        saldo += detalle.debe - detalle.haber
        movimientos.append({
            "fecha":       asiento.fecha,
            "descripcion": asiento.descripcion,
            "modulo":      asiento.modulo,
            "debe":        detalle.debe,
            "haber":       detalle.haber,
            "saldo":       round(saldo, 2),
        })

    return {
        "cuenta": {"id": cuenta.id, "codigo": cuenta.codigo, "nombre": cuenta.nombre, "tipo": cuenta.tipo},
        "movimientos": movimientos,
        "total_debe":  round(sum(m["debe"]  for m in movimientos), 2),
        "total_haber": round(sum(m["haber"] for m in movimientos), 2),
        "saldo_final": round(saldo, 2),
    }


@router.get("/sumas-saldo")
def get_sumas_saldo(
    desde: Optional[str] = Query(None),
    hasta: Optional[str] = Query(None),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sumas y saldo: total debe/haber por cuenta."""
    oid = _org_id(current_user, org_id)

    q = (
        db.query(
            PlanCuenta.id,
            PlanCuenta.codigo,
            PlanCuenta.nombre,
            PlanCuenta.tipo,
            PlanCuenta.nivel,
            func.coalesce(func.sum(AsientoDetalle.debe),  0.0).label("total_debe"),
            func.coalesce(func.sum(AsientoDetalle.haber), 0.0).label("total_haber"),
        )
        .join(AsientoDetalle, AsientoDetalle.cuenta_id == PlanCuenta.id)
        .join(Asiento, AsientoDetalle.asiento_id == Asiento.id)
        .filter(Asiento.organizacion_id == oid)
    )
    if desde:
        q = q.filter(Asiento.fecha >= desde)
    if hasta:
        q = q.filter(Asiento.fecha <= hasta)
    q = q.group_by(
        PlanCuenta.id, PlanCuenta.codigo, PlanCuenta.nombre,
        PlanCuenta.tipo, PlanCuenta.nivel,
    ).order_by(PlanCuenta.codigo)

    rows = []
    for r in q.all():
        debe  = round(float(r.total_debe),  2)
        haber = round(float(r.total_haber), 2)
        saldo = round(debe - haber, 2)
        rows.append({
            "id":     r.id,
            "codigo": r.codigo,
            "nombre": r.nombre,
            "tipo":   r.tipo,
            "nivel":  r.nivel,
            "total_debe":    debe,
            "total_haber":   haber,
            "saldo_deudor":  max(saldo, 0),
            "saldo_acreedor": max(-saldo, 0),
        })
    return rows


@router.get("/balance")
def get_balance(
    desde: Optional[str] = Query(None),
    hasta: Optional[str] = Query(None),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Balance simplificado: totales por tipo de cuenta."""
    oid = _org_id(current_user, org_id)

    q = (
        db.query(
            PlanCuenta.tipo,
            func.coalesce(func.sum(AsientoDetalle.debe),  0.0).label("total_debe"),
            func.coalesce(func.sum(AsientoDetalle.haber), 0.0).label("total_haber"),
        )
        .join(AsientoDetalle, AsientoDetalle.cuenta_id == PlanCuenta.id)
        .join(Asiento, AsientoDetalle.asiento_id == Asiento.id)
        .filter(Asiento.organizacion_id == oid, PlanCuenta.tipo.isnot(None))
    )
    if desde:
        q = q.filter(Asiento.fecha >= desde)
    if hasta:
        q = q.filter(Asiento.fecha <= hasta)
    q = q.group_by(PlanCuenta.tipo)

    totales: dict = {}
    for r in q.all():
        debe  = round(float(r.total_debe),  2)
        haber = round(float(r.total_haber), 2)
        totales[r.tipo] = {
            "total_debe":  debe,
            "total_haber": haber,
            "saldo":       round(debe - haber, 2),
        }

    activo    = totales.get("activo",    {}).get("saldo", 0)
    pasivo    = totales.get("pasivo",    {}).get("saldo", 0)
    resultado = totales.get("resultado", {}).get("saldo", 0)

    return {
        "activo":    totales.get("activo",    {"total_debe": 0, "total_haber": 0, "saldo": 0}),
        "pasivo":    totales.get("pasivo",    {"total_debe": 0, "total_haber": 0, "saldo": 0}),
        "resultado": totales.get("resultado", {"total_debe": 0, "total_haber": 0, "saldo": 0}),
        "ecuacion_ok": round(activo, 2) == round(abs(pasivo) + abs(resultado), 2),
    }
