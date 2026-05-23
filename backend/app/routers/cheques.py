from datetime import date, datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.cheque import Cheque
from app.models.cliente import Cliente
from app.services.motor_contable import registrar_cheque, acreditar_cheque, rechazar_cheque

router = APIRouter(prefix="/cheques", tags=["cheques"])


class ChequeIn(BaseModel):
    cliente_id:     Optional[int] = None
    numero:         Optional[str] = None
    banco_origen:   Optional[str] = None
    titular:        Optional[str] = None
    monto:          float
    comision:       float = 0.0
    fecha_emision:  Optional[date] = None
    fecha_deposito: Optional[date] = None
    notas:          Optional[str] = None


class AcreditarIn(BaseModel):
    fecha_acred: Optional[date] = None


def _org_id(current_user: User, org_id: Optional[int]) -> int:
    if current_user.is_superadmin and org_id:
        return org_id
    return current_user.organizacion_id or 1


def _cheque_dict(c: Cheque) -> dict:
    return {
        "id":             c.id,
        "organizacion_id": c.organizacion_id,
        "cliente_id":     c.cliente_id,
        "cliente_nombre": c.cliente.nombre if c.cliente else None,
        "numero":         c.numero,
        "banco_origen":   c.banco_origen,
        "titular":        c.titular,
        "monto":          c.monto,
        "comision":       c.comision,
        "fecha_emision":  c.fecha_emision,
        "fecha_deposito": c.fecha_deposito,
        "fecha_acred":    c.fecha_acred,
        "estado":         c.estado,
        "notas":          c.notas,
        "created_at":     c.created_at,
    }


@router.get("")
def list_cheques(
    org_id:     Optional[int] = Query(None),
    estado:     Optional[str] = Query(None),
    cliente_id: Optional[int] = Query(None),
    desde:      Optional[str] = Query(None),
    hasta:      Optional[str] = Query(None),
    skip:       int = 0,
    limit:      int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    oid = _org_id(current_user, org_id)
    q = db.query(Cheque).filter(Cheque.organizacion_id == oid)
    if estado:
        q = q.filter(Cheque.estado == estado)
    if cliente_id:
        q = q.filter(Cheque.cliente_id == cliente_id)
    if desde:
        q = q.filter(Cheque.fecha_deposito >= desde)
    if hasta:
        q = q.filter(Cheque.fecha_deposito <= hasta)
    total = q.count()
    items = q.order_by(Cheque.created_at.desc()).offset(skip).limit(limit).all()
    return {"total": total, "items": [_cheque_dict(c) for c in items]}


@router.post("")
def crear_cheque(
    body: ChequeIn,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    oid = _org_id(current_user, org_id)
    if body.cliente_id:
        cli = db.query(Cliente).filter(Cliente.id == body.cliente_id, Cliente.organizacion_id == oid).first()
        if not cli:
            raise HTTPException(404, "Cliente no encontrado")

    c = Cheque(
        organizacion_id=oid,
        cliente_id=body.cliente_id,
        numero=body.numero,
        banco_origen=body.banco_origen,
        titular=body.titular,
        monto=body.monto,
        comision=body.comision,
        fecha_emision=body.fecha_emision,
        fecha_deposito=body.fecha_deposito or date.today(),
        estado="pendiente",
        notas=body.notas,
        usuario_id=current_user.id,
    )
    db.add(c)
    db.flush()

    registrar_cheque(
        db=db,
        cheque_id=c.id,
        org_id=oid,
        usuario_id=current_user.id,
        titular=c.titular or "",
        monto=c.monto,
        comision=c.comision,
        fecha=c.fecha_deposito or date.today(),
    )
    db.commit()
    db.refresh(c)
    return _cheque_dict(c)


@router.get("/{cheque_id}")
def get_cheque(
    cheque_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    oid = current_user.organizacion_id or 1
    c = db.query(Cheque).filter(Cheque.id == cheque_id).first()
    if not c:
        raise HTTPException(404, "Cheque no encontrado")
    if not current_user.is_superadmin and c.organizacion_id != oid:
        raise HTTPException(403, "Sin acceso")
    return _cheque_dict(c)


@router.patch("/{cheque_id}")
def editar_cheque(
    cheque_id: int,
    body: ChequeIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    oid = current_user.organizacion_id or 1
    c = db.query(Cheque).filter(Cheque.id == cheque_id).first()
    if not c:
        raise HTTPException(404, "Cheque no encontrado")
    if not current_user.is_superadmin and c.organizacion_id != oid:
        raise HTTPException(403, "Sin acceso")
    if c.estado != "pendiente":
        raise HTTPException(400, "Solo se pueden editar cheques pendientes")
    for field in ("cliente_id", "numero", "banco_origen", "titular", "monto",
                  "comision", "fecha_emision", "fecha_deposito", "notas"):
        val = getattr(body, field, None)
        if val is not None:
            setattr(c, field, val)
    db.commit()
    db.refresh(c)
    return _cheque_dict(c)


@router.post("/{cheque_id}/acreditar")
def acreditar(
    cheque_id: int,
    body: AcreditarIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    oid = current_user.organizacion_id or 1
    c = db.query(Cheque).filter(Cheque.id == cheque_id).first()
    if not c:
        raise HTTPException(404, "Cheque no encontrado")
    if not current_user.is_superadmin and c.organizacion_id != oid:
        raise HTTPException(403, "Sin acceso")
    if c.estado != "pendiente":
        raise HTTPException(400, f"Cheque ya está {c.estado}")

    c.estado = "acreditado"
    c.fecha_acred = body.fecha_acred or date.today()
    db.flush()

    acreditar_cheque(
        db=db,
        cheque_id=c.id,
        org_id=c.organizacion_id,
        usuario_id=current_user.id,
        titular=c.titular or "",
        monto=c.monto,
        fecha=c.fecha_acred,
    )
    db.commit()
    db.refresh(c)
    return _cheque_dict(c)


@router.post("/{cheque_id}/rechazar")
def rechazar(
    cheque_id: int,
    body: AcreditarIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    oid = current_user.organizacion_id or 1
    c = db.query(Cheque).filter(Cheque.id == cheque_id).first()
    if not c:
        raise HTTPException(404, "Cheque no encontrado")
    if not current_user.is_superadmin and c.organizacion_id != oid:
        raise HTTPException(403, "Sin acceso")
    if c.estado != "pendiente":
        raise HTTPException(400, f"Cheque ya está {c.estado}")

    c.estado = "rechazado"
    c.fecha_acred = body.fecha_acred or date.today()
    db.flush()

    rechazar_cheque(
        db=db,
        cheque_id=c.id,
        org_id=c.organizacion_id,
        usuario_id=current_user.id,
        titular=c.titular or "",
        monto=c.monto,
        fecha=c.fecha_acred,
    )
    db.commit()
    db.refresh(c)
    return _cheque_dict(c)


@router.delete("/{cheque_id}")
def eliminar_cheque(
    cheque_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    oid = current_user.organizacion_id or 1
    c = db.query(Cheque).filter(Cheque.id == cheque_id).first()
    if not c:
        raise HTTPException(404, "Cheque no encontrado")
    if not current_user.is_superadmin and c.organizacion_id != oid:
        raise HTTPException(403, "Sin acceso")
    if c.estado != "pendiente":
        raise HTTPException(400, "Solo se pueden eliminar cheques pendientes")
    db.delete(c)
    db.commit()
    return {"ok": True}
