"""Router cheques — acreditación (individual y masiva) y rechazo.

Rutas expuestas (bajo el prefix /cheques del router padre):
  POST /{cheque_id}/acreditar
  POST /acreditar
  POST /{cheque_id}/rechazar
"""
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.cheque import Cheque
from app.models.cliente import Cliente
from app.models.contabilidad import PlanCuenta
from app.services.motor_contable import acreditar_cheque, rechazar_cheque
from app.services.auditoria import registrar_log
from app.services.tz import hoy_art

from .cheques_common import AcreditarIn, AcreditarMasivoIn, RechazarIn, _org_id, _cheque_dict

router = APIRouter(tags=["cheques"])


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
    if c.estado not in ("registrado", "depositado", "pendiente"):
        raise HTTPException(400, f"Cheque ya está {c.estado}")

    # Verificar que el banco elegido existe
    banco_cuenta = db.query(PlanCuenta).filter(PlanCuenta.id == body.banco_cuenta_id).first()
    if not banco_cuenta:
        raise HTTPException(404, "Cuenta de banco no encontrada")

    # Verificar que el cliente tiene cuenta contable
    cli = db.query(Cliente).filter(Cliente.id == c.cliente_id).first() if c.cliente_id else None
    if not cli or not cli.cuenta_contable_id:
        raise HTTPException(400, "El cliente no tiene cuenta contable configurada")

    c.estado          = "acreditado"
    c.fecha_acred     = body.fecha_acred or hoy_art()
    c.banco_cuenta_id = body.banco_cuenta_id
    db.flush()

    neto = Decimal(str(c.monto)) - Decimal(str(c.comision or 0))
    acreditar_cheque(
        db=db, cheque_id=c.id, org_id=c.organizacion_id, usuario_id=current_user.id,
        titular=c.librador or c.titular or "",
        monto=Decimal(str(c.monto)), neto=neto,
        banco_cuenta_id=body.banco_cuenta_id,
        cliente_cuenta_id=cli.cuenta_contable_id,
        fecha=c.fecha_acred,
    )
    registrar_log(db, current_user.id, "cheques", c.id, "ACREDITAR",
                  {"monto": float(c.monto), "fecha_acred": str(c.fecha_acred),
                   "banco": banco_cuenta.nombre})
    db.commit()
    db.refresh(c)
    return _cheque_dict(c)


@router.post("/acreditar")
def acreditar_masivo(
    body: AcreditarMasivoIn,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Acredita uno o varios cheques de una sola vez (flujo Por depósito)."""
    oid = _org_id(current_user, org_id)

    banco_cuenta = db.query(PlanCuenta).filter(PlanCuenta.id == body.banco_cuenta_id).first()
    if not banco_cuenta:
        raise HTTPException(404, "Cuenta de banco no encontrada")

    fecha = body.fecha_acred or hoy_art()
    resultados = []
    for cheque_id in body.cheque_ids:
        c = db.query(Cheque).filter(Cheque.id == cheque_id, Cheque.organizacion_id == oid).first()
        if not c:
            resultados.append({"id": cheque_id, "ok": False, "error": "No encontrado"})
            continue
        if c.estado not in ("registrado", "depositado", "pendiente"):
            resultados.append({"id": cheque_id, "ok": False, "error": f"Estado {c.estado}"})
            continue
        cli = db.query(Cliente).filter(Cliente.id == c.cliente_id).first() if c.cliente_id else None
        if not cli or not cli.cuenta_contable_id:
            resultados.append({"id": cheque_id, "ok": False,
                               "error": f"Cliente sin cuenta contable"})
            continue

        c.estado          = "acreditado"
        c.fecha_acred     = fecha
        c.banco_cuenta_id = body.banco_cuenta_id
        db.flush()

        neto = Decimal(str(c.monto)) - Decimal(str(c.comision or 0))
        acreditar_cheque(
            db=db, cheque_id=c.id, org_id=c.organizacion_id, usuario_id=current_user.id,
            titular=c.librador or c.titular or "",
            monto=Decimal(str(c.monto)), neto=neto,
            banco_cuenta_id=body.banco_cuenta_id,
            cliente_cuenta_id=cli.cuenta_contable_id,
            fecha=fecha,
        )
        registrar_log(db, current_user.id, "cheques", c.id, "ACREDITAR",
                      {"monto": float(c.monto), "banco": banco_cuenta.nombre})
        resultados.append({"id": cheque_id, "ok": True})

    db.commit()
    ok_count = sum(1 for r in resultados if r["ok"])
    return {"acreditados": ok_count, "total": len(body.cheque_ids), "detalle": resultados}


@router.post("/{cheque_id}/rechazar")
def rechazar(
    cheque_id: int,
    body: RechazarIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    oid = current_user.organizacion_id or 1
    c = db.query(Cheque).filter(Cheque.id == cheque_id).first()
    if not c:
        raise HTTPException(404, "Cheque no encontrado")
    if not current_user.is_superadmin and c.organizacion_id != oid:
        raise HTTPException(403, "Sin acceso")
    if c.estado != "acreditado":
        raise HTTPException(400, "Solo se pueden rechazar cheques acreditados")

    cli = db.query(Cliente).filter(Cliente.id == c.cliente_id).first() if c.cliente_id else None
    if not cli or not cli.cuenta_contable_id:
        raise HTTPException(400, "El cliente no tiene cuenta contable configurada")
    if not c.banco_cuenta_id:
        raise HTTPException(400, "El cheque no tiene banco registrado de la acreditación")

    c.estado           = "rechazado"
    c.fecha_rechazo    = body.fecha_rechazo or hoy_art()
    c.fisico           = body.fisico
    c.fecha_devolucion = body.fecha_devolucion
    db.flush()

    rechazar_cheque(
        db=db, cheque_id=c.id, org_id=c.organizacion_id, usuario_id=current_user.id,
        titular=c.librador or c.titular or "",
        monto=Decimal(str(c.monto)),
        gastos=Decimal(str(body.gastos_bancarios)),
        banco_cuenta_id=c.banco_cuenta_id,
        cliente_cuenta_id=cli.cuenta_contable_id,
        fecha=c.fecha_rechazo,
    )
    registrar_log(db, current_user.id, "cheques", c.id, "RECHAZAR",
                  {"monto": float(c.monto), "gastos": body.gastos_bancarios,
                   "fecha_rechazo": str(c.fecha_rechazo), "fisico": c.fisico})
    db.commit()
    db.refresh(c)
    return _cheque_dict(c)
