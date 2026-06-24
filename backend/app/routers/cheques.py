"""Router cheques — agregador delgado.

Importa los 3 sub-módulos y los incluye bajo el prefijo /cheques.
main.py no necesita cambios: sigue haciendo `app.include_router(cheques.router)`.

Sub-módulos:
  cheques_reportes.py     — /exportar, /deposito/exportar, /deposito
  cheques_crud.py         — /bulk-ocr, /bulk-crear, /portadores, CRUD principal
                            (/{cheque_id}), foto, /importar
  cheques_acreditacion.py — /{cheque_id}/acreditar, /acreditar, /{cheque_id}/rechazar

Orden de registro CRÍTICO: cheques_reportes (rutas literales /exportar,
/deposito*) debe registrarse ANTES que cheques_crud (que define
GET/PATCH/DELETE /{cheque_id}) para que FastAPI no confunda esas rutas
literales con el path param. Replica el orden original del monolito.

GET "" y POST "" (listar/crear cheque) están declarados ACÁ directamente
(no en cheques_crud.py): este router es el único que tiene el prefix
"/cheques" propio, así que un path vacío es válido para FastAPI y resuelve
a exactamente "/cheques" (sin barra final). Si se declararan en un
sub-router sin prefix propio e incluyeran vía `include_router()`, FastAPI
lanza `FastAPIError: Prefix and path cannot be both empty`.

Helpers compartidos: cheques_common.py (_org_id, _cheque_dict, _local_interior,
                                         _parse_date, schemas Pydantic)
"""
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.cheque import Cheque
from app.models.cliente import Cliente
from app.models.portador import Portador
from app.services.motor_contable import registrar_cheque
from app.services.auditoria import registrar_log
from app.services.tz import hoy_art

from .cheques_reportes import router as _reportes_router
from .cheques_crud import router as _crud_router
from .cheques_acreditacion import router as _acreditacion_router

from .cheques_common import (
    ChequeIn, AcreditarIn, AcreditarMasivoIn, RechazarIn, PortadorIn,
    BulkOcrItem, BulkCrearItem, BulkCrearIn, FotoIn,
    _org_id, _local_interior, _cheque_dict, _parse_date,
)

router = APIRouter(prefix="/cheques", tags=["cheques"])
limiter = Limiter(key_func=get_remote_address)


# ── CRUD principal: listar / crear (paths vacíos, ver nota arriba) ──

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
@limiter.limit("30/minute")
def crear_cheque(
    request: Request,
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
        if not cli.cuenta_contable_id:
            raise HTTPException(
                400,
                f"El cliente '{cli.nombre}' no tiene cuenta contable configurada. "
                "Creala en Contabilidad → Clientes antes de registrar cheques."
            )
    if body.portador_id:
        if not db.query(Portador).filter(Portador.id == body.portador_id, Portador.organizacion_id == oid).first():
            raise HTTPException(404, "Portador no encontrado")

    li = body.local_interior or _local_interior(body.codigo_postal)

    # % comisión: usa el del body si vino; si no, lo hereda del cliente según
    # local/interior (con fallback al % general del cliente).
    if body.porcentaje_comision is not None:
        pct_comision = Decimal(str(body.porcentaje_comision))
    elif body.cliente_id and cli:
        if li == "local" and cli.porcentaje_comision_local is not None:
            pct_comision = cli.porcentaje_comision_local
        elif li == "interior" and cli.porcentaje_comision_interior is not None:
            pct_comision = cli.porcentaje_comision_interior
        else:
            pct_comision = cli.porcentaje_comision
    else:
        pct_comision = None

    c = Cheque(
        organizacion_id=oid,
        cliente_id=body.cliente_id,
        portador_id=body.portador_id,
        numero=body.numero,
        banco_origen=body.banco_origen,
        librador=body.librador,
        monto=body.monto,
        comision=body.comision,
        porcentaje_comision=pct_comision,
        codigo_postal=body.codigo_postal,
        local_interior=li,
        fecha_emision=body.fecha_emision,
        fecha_deposito=body.fecha_deposito or hoy_art(),
        estado="registrado",
        notas=body.notas,
        usuario_id=current_user.id,
    )
    db.add(c)
    db.flush()

    registrar_cheque(
        db=db, cheque_id=c.id, org_id=oid, usuario_id=current_user.id,
        titular=c.librador or "", monto=c.monto, comision=c.comision,
        fecha=c.fecha_deposito or hoy_art(),
    )
    registrar_log(db, current_user.id, "cheques", c.id, "INSERT",
                  {"monto": c.monto, "librador": c.librador, "cliente_id": c.cliente_id,
                   "fecha_deposito": str(c.fecha_deposito) if c.fecha_deposito else None})
    db.commit()
    db.refresh(c)
    return _cheque_dict(c)


router.include_router(_reportes_router)
router.include_router(_crud_router)
router.include_router(_acreditacion_router)

# Re-exportar helpers/schemas para compatibilidad con tests y otros módulos
# que pudieran importarlos directamente desde cheques.
__all__ = [
    "router", "ChequeIn", "AcreditarIn", "AcreditarMasivoIn", "RechazarIn", "PortadorIn",
    "BulkOcrItem", "BulkCrearItem", "BulkCrearIn", "FotoIn",
    "_org_id", "_local_interior", "_cheque_dict", "_parse_date",
]
