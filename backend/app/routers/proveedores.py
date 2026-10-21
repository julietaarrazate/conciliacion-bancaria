"""Ficha de proveedores propios de la organización (ver services/proveedores.py)."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import can_switch_org, require_permission
from app.models.proveedor import Proveedor
from app.models.user import User
from app.services import proveedores as svc
from app.services.acceso_orgs import puede_org
from app.services.auditoria import registrar_log

router = APIRouter(prefix="/proveedores", tags=["proveedores"])


def _org_id(user: User, org_id_param: Optional[int] = None) -> int:
    if org_id_param and can_switch_org(user, org_id_param):
        return org_id_param
    return user.organizacion_id or 1


def _buscar(db: Session, user: User, proveedor_id: int) -> Proveedor:
    prov = db.get(Proveedor, proveedor_id)
    if prov is None or not puede_org(user, prov.organizacion_id):
        raise HTTPException(404, "Proveedor no encontrado")
    return prov


@router.get("")
def listar(
    q: Optional[str] = Query(None),
    incluir_inactivos: bool = Query(False),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("view_accounting")),
):
    return svc.listar(db, _org_id(current_user, org_id), q, incluir_inactivos)


@router.post("")
def crear(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("reconcile")),
):
    oid = _org_id(current_user, payload.get("org_id"))
    try:
        prov = svc.crear(db, oid, payload)
    except svc.ProveedorInvalido as ex:
        raise HTTPException(422, str(ex))
    registrar_log(db, current_user.id, "proveedores", prov.id, "INSERT",
                  {"cuit": prov.cuit, "razon_social": prov.razon_social})
    return svc.proveedor_dict(prov)


@router.post("/sincronizar")
def sincronizar(
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("reconcile")),
):
    """Trae a la ficha los emisores de las facturas recibidas (IVA)."""
    oid = _org_id(current_user, org_id)
    creados = svc.sincronizar_desde_comprobantes(db, oid)
    if creados:
        registrar_log(db, current_user.id, "proveedores", 0, "SINCRONIZAR",
                      {"organizacion_id": oid, "creados": creados})
    return {"creados": creados}


@router.patch("/{proveedor_id}")
def editar(
    proveedor_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("reconcile")),
):
    prov = _buscar(db, current_user, proveedor_id)
    try:
        prov = svc.actualizar(db, prov, payload)
    except svc.ProveedorInvalido as ex:
        raise HTTPException(422, str(ex))
    registrar_log(db, current_user.id, "proveedores", prov.id, "UPDATE",
                  {k: payload[k] for k in payload if k != "org_id"})
    return svc.proveedor_dict(prov)


@router.delete("/{proveedor_id}")
def dar_de_baja(
    proveedor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("reconcile")),
):
    """Baja lógica: el proveedor puede tener pagos e historial, no se borra."""
    prov = _buscar(db, current_user, proveedor_id)
    svc.actualizar(db, prov, {"activo": False})
    registrar_log(db, current_user.id, "proveedores", prov.id, "BAJA", {"razon_social": prov.razon_social})
    return {"ok": True}
