from datetime import date, datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.pago import Pago, Gasto
from app.models.cliente import Cliente
from app.services.motor_contable import registrar_pago, registrar_gasto

router = APIRouter(tags=["pagos_gastos"])


# ── helpers ─────────────────────────────────────────────────────

def _org_id(current_user: User, org_id: Optional[int]) -> int:
    if current_user.is_superadmin and org_id:
        return org_id
    return current_user.organizacion_id or 1


# ── Pagos ────────────────────────────────────────────────────────

class PagoIn(BaseModel):
    cliente_id: Optional[int] = None
    concepto:   Optional[str] = None
    monto:      float
    medio:      str = "banco"   # banco | efectivo
    fecha:      Optional[date] = None
    referencia: Optional[str] = None
    notas:      Optional[str] = None


def _pago_dict(p: Pago) -> dict:
    return {
        "id":             p.id,
        "organizacion_id": p.organizacion_id,
        "cliente_id":     p.cliente_id,
        "cliente_nombre": p.cliente.nombre if p.cliente else None,
        "concepto":       p.concepto,
        "monto":          p.monto,
        "medio":          p.medio,
        "fecha":          p.fecha,
        "referencia":     p.referencia,
        "notas":          p.notas,
        "created_at":     p.created_at,
    }


@router.get("/pagos")
def list_pagos(
    org_id:     Optional[int] = Query(None),
    cliente_id: Optional[int] = Query(None),
    medio:      Optional[str] = Query(None),
    desde:      Optional[str] = Query(None),
    hasta:      Optional[str] = Query(None),
    skip:       int = 0,
    limit:      int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    oid = _org_id(current_user, org_id)
    q = db.query(Pago).filter(Pago.organizacion_id == oid)
    if cliente_id:
        q = q.filter(Pago.cliente_id == cliente_id)
    if medio:
        q = q.filter(Pago.medio == medio)
    if desde:
        q = q.filter(Pago.fecha >= desde)
    if hasta:
        q = q.filter(Pago.fecha <= hasta)
    total = q.count()
    items = q.order_by(Pago.created_at.desc()).offset(skip).limit(limit).all()
    return {"total": total, "items": [_pago_dict(p) for p in items]}


@router.post("/pagos")
def crear_pago(
    body: PagoIn,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    oid = _org_id(current_user, org_id)
    if body.monto <= 0:
        raise HTTPException(400, "El monto debe ser mayor a 0")
    if body.medio not in ("banco", "efectivo"):
        raise HTTPException(400, "Medio debe ser 'banco' o 'efectivo'")

    cliente_nombre = ""
    if body.cliente_id:
        cli = db.query(Cliente).filter(Cliente.id == body.cliente_id, Cliente.organizacion_id == oid).first()
        if not cli:
            raise HTTPException(404, "Cliente no encontrado")
        cliente_nombre = cli.nombre

    p = Pago(
        organizacion_id=oid,
        cliente_id=body.cliente_id,
        concepto=body.concepto,
        monto=body.monto,
        medio=body.medio,
        fecha=body.fecha or date.today(),
        referencia=body.referencia,
        notas=body.notas,
        usuario_id=current_user.id,
    )
    db.add(p)
    db.flush()

    registrar_pago(
        db=db,
        pago_id=p.id,
        org_id=oid,
        usuario_id=current_user.id,
        concepto=p.concepto or "",
        cliente_nombre=cliente_nombre,
        monto=p.monto,
        medio=p.medio,
        fecha=p.fecha,
    )
    db.commit()
    db.refresh(p)
    return _pago_dict(p)


@router.patch("/pagos/{pago_id}")
def actualizar_pago(
    pago_id: int,
    body: PagoIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not (current_user.is_superadmin or current_user.role == "admin"):
        raise HTTPException(403, "Se requiere rol admin o superadmin")
    oid = current_user.organizacion_id or 1
    p = db.query(Pago).filter(Pago.id == pago_id).first()
    if not p:
        raise HTTPException(404, "Pago no encontrado")
    if not current_user.is_superadmin and p.organizacion_id != oid:
        raise HTTPException(403, "Sin acceso")
    if body.monto is not None and body.monto <= 0:
        raise HTTPException(400, "El monto debe ser mayor a 0")
    if body.medio not in ("banco", "efectivo"):
        raise HTTPException(400, "Medio inválido")
    p.cliente_id = body.cliente_id
    p.concepto   = body.concepto
    p.monto      = body.monto
    p.medio      = body.medio
    p.fecha      = body.fecha
    p.referencia = body.referencia
    p.notas      = body.notas
    db.commit()
    db.refresh(p)
    return _pago_dict(p)


@router.delete("/pagos/{pago_id}")
def eliminar_pago(
    pago_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not (current_user.is_superadmin or current_user.role == "admin"):
        raise HTTPException(403, "Se requiere rol admin o superadmin")
    oid = current_user.organizacion_id or 1
    p = db.query(Pago).filter(Pago.id == pago_id).first()
    if not p:
        raise HTTPException(404, "Pago no encontrado")
    if not current_user.is_superadmin and p.organizacion_id != oid:
        raise HTTPException(403, "Sin acceso")

    # Reverso contable ANTES de borrar (preserva trazabilidad)
    from app.services.motor_contable import reversar_asientos
    reversar_asientos(db, modulo="pago", referencia_id=pago_id,
                      org_id=p.organizacion_id, usuario_id=current_user.id,
                      motivo=f"Pago #{pago_id} eliminado por {current_user.email}")

    db.delete(p)
    db.commit()
    return {"ok": True}


# ── Gastos ───────────────────────────────────────────────────────

class GastoIn(BaseModel):
    concepto:   str
    categoria:  Optional[str] = None   # impuestos | bancarios | otros
    monto:      float
    medio:      str = "banco"
    fecha:      Optional[date] = None
    referencia: Optional[str] = None
    notas:      Optional[str] = None


def _gasto_dict(g: Gasto) -> dict:
    return {
        "id":             g.id,
        "organizacion_id": g.organizacion_id,
        "concepto":       g.concepto,
        "categoria":      g.categoria,
        "monto":          g.monto,
        "medio":          g.medio,
        "fecha":          g.fecha,
        "referencia":     g.referencia,
        "notas":          g.notas,
        "created_at":     g.created_at,
    }


@router.get("/gastos")
def list_gastos(
    org_id:    Optional[int] = Query(None),
    categoria: Optional[str] = Query(None),
    medio:     Optional[str] = Query(None),
    desde:     Optional[str] = Query(None),
    hasta:     Optional[str] = Query(None),
    skip:      int = 0,
    limit:     int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    oid = _org_id(current_user, org_id)
    q = db.query(Gasto).filter(Gasto.organizacion_id == oid)
    if categoria:
        q = q.filter(Gasto.categoria == categoria)
    if medio:
        q = q.filter(Gasto.medio == medio)
    if desde:
        q = q.filter(Gasto.fecha >= desde)
    if hasta:
        q = q.filter(Gasto.fecha <= hasta)
    total = q.count()
    items = q.order_by(Gasto.created_at.desc()).offset(skip).limit(limit).all()
    return {"total": total, "items": [_gasto_dict(g) for g in items]}


@router.post("/gastos")
def crear_gasto(
    body: GastoIn,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    oid = _org_id(current_user, org_id)
    if body.monto <= 0:
        raise HTTPException(400, "El monto debe ser mayor a 0")
    if body.medio not in ("banco", "efectivo"):
        raise HTTPException(400, "Medio debe ser 'banco' o 'efectivo'")

    g = Gasto(
        organizacion_id=oid,
        concepto=body.concepto,
        categoria=body.categoria,
        monto=body.monto,
        medio=body.medio,
        fecha=body.fecha or date.today(),
        referencia=body.referencia,
        notas=body.notas,
        usuario_id=current_user.id,
    )
    db.add(g)
    db.flush()

    registrar_gasto(
        db=db,
        gasto_id=g.id,
        org_id=oid,
        usuario_id=current_user.id,
        concepto=g.concepto,
        monto=g.monto,
        medio=g.medio,
        fecha=g.fecha,
    )
    db.commit()
    db.refresh(g)
    return _gasto_dict(g)


@router.patch("/gastos/{gasto_id}")
def actualizar_gasto(
    gasto_id: int,
    body: GastoIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not (current_user.is_superadmin or current_user.role == "admin"):
        raise HTTPException(403, "Se requiere rol admin o superadmin")
    oid = current_user.organizacion_id or 1
    g = db.query(Gasto).filter(Gasto.id == gasto_id).first()
    if not g:
        raise HTTPException(404, "Gasto no encontrado")
    if not current_user.is_superadmin and g.organizacion_id != oid:
        raise HTTPException(403, "Sin acceso")
    if body.monto <= 0:
        raise HTTPException(400, "El monto debe ser mayor a 0")
    if body.medio not in ("banco", "efectivo"):
        raise HTTPException(400, "Medio inválido")
    g.concepto   = body.concepto
    g.categoria  = body.categoria
    g.monto      = body.monto
    g.medio      = body.medio
    g.fecha      = body.fecha
    g.referencia = body.referencia
    g.notas      = body.notas
    db.commit()
    db.refresh(g)
    return _gasto_dict(g)


@router.delete("/gastos/{gasto_id}")
def eliminar_gasto(
    gasto_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not (current_user.is_superadmin or current_user.role == "admin"):
        raise HTTPException(403, "Se requiere rol admin o superadmin")
    oid = current_user.organizacion_id or 1
    g = db.query(Gasto).filter(Gasto.id == gasto_id).first()
    if not g:
        raise HTTPException(404, "Gasto no encontrado")
    if not current_user.is_superadmin and g.organizacion_id != oid:
        raise HTTPException(403, "Sin acceso")

    # Reverso contable ANTES de borrar (preserva trazabilidad)
    from app.services.motor_contable import reversar_asientos
    reversar_asientos(db, modulo="gasto", referencia_id=gasto_id,
                      org_id=g.organizacion_id, usuario_id=current_user.id,
                      motivo=f"Gasto #{gasto_id} eliminado por {current_user.email}")

    db.delete(g)
    db.commit()
    return {"ok": True}
