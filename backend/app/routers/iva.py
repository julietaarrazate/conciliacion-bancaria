"""Router del módulo IVA Proyección y DDJJ.

Endpoints (prefix /iva):
  GET  /iva/config                          — cuentas configurables (tasa_iva)
  PUT  /iva/config/{cuenta_id}              — setea tasa_iva de una cuenta hoja
  GET  /iva/proyeccion?periodo=             — preview (no persiste)
  POST /iva/proyeccion/calcular?periodo=    — calcula y persiste (upsert)
  POST /iva/proyeccion/{id}/marcar-presentada
  GET  /iva/historial                       — snapshots de la org, paginado

Permisos:
  config (GET/PUT)            → admin_accounting
  proyeccion (GET preview)    → view_accounting
  proyeccion/calcular (POST)  → manage_finance
  marcar-presentada (POST)    → admin_accounting
  historial (GET)             → view_accounting
"""

from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import require_permission, can_switch_org
from app.models.contabilidad import PlanCuenta
from app.models.proyeccion_iva import ProyeccionIva
from app.models.user import User
from app.services.auditoria import registrar_log
from app.services.iva_service import (
    calcular_proyeccion_iva,
    guardar_o_actualizar_proyeccion,
    marcar_presentada,
    IvaServiceError,
)

router = APIRouter(prefix="/iva", tags=["iva"])


# ── Helpers ───────────────────────────────────────────────────────

def _org_id(current_user: User, org_id: Optional[int]) -> int:
    if can_switch_org(current_user, org_id) and org_id:
        return org_id
    return current_user.organizacion_id or 1


def _f(v):
    return float(v) if isinstance(v, Decimal) else v


def _proyeccion_dict(p: ProyeccionIva) -> dict:
    return {
        "id": p.id,
        "organizacion_id": p.organizacion_id,
        "periodo": p.periodo,
        "debito_fiscal": p.debito_fiscal,
        "credito_fiscal": p.credito_fiscal,
        "saldo": p.saldo,
        "estado": p.estado,
        "fecha_presentacion": p.fecha_presentacion,
        "detalle": p.detalle,
        "created_at": p.created_at,
        "updated_at": p.updated_at,
    }


# ── Schemas ───────────────────────────────────────────────────────

class TasaIvaIn(BaseModel):
    tasa_iva: Optional[float] = None


# ── Config: tasa_iva por cuenta ───────────────────────────────────

@router.get("/config")
def get_config(
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin_accounting")),
):
    """Lista las cuentas hoja de tipo resultado (ingresos/gastos) con su tasa_iva
    actual — para que el admin configure cuáles están gravadas."""
    oid = _org_id(current_user, org_id)

    parent_ids = {
        pid for (pid,) in db.query(PlanCuenta.parent_id).filter(
            PlanCuenta.organizacion_id == oid,
            PlanCuenta.parent_id.isnot(None),
        ).all()
    }
    cuentas = (
        db.query(PlanCuenta)
        .filter(
            PlanCuenta.organizacion_id == oid,
            PlanCuenta.activo == True,
            PlanCuenta.tipo == "resultado",
        )
        .order_by(PlanCuenta.codigo)
        .all()
    )
    items = [
        {
            "id": c.id,
            "codigo": c.codigo,
            "nombre": c.nombre,
            "tipo": c.tipo,
            "es_ingreso": c.codigo.startswith("3-1"),
            "tasa_iva": _f(c.tasa_iva),
        }
        for c in cuentas
        if c.id not in parent_ids  # solo cuentas hoja
    ]
    return {"items": items, "total": len(items)}


@router.put("/config/{cuenta_id}")
def set_tasa_iva(
    cuenta_id: int,
    body: TasaIvaIn,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin_accounting")),
):
    """Setea (o limpia, con null) la tasa_iva de una cuenta hoja de la org."""
    oid = _org_id(current_user, org_id)
    c = (
        db.query(PlanCuenta)
        .filter(PlanCuenta.id == cuenta_id, PlanCuenta.organizacion_id == oid)
        .first()
    )
    if not c:
        raise HTTPException(404, "Cuenta no encontrada")
    if db.query(PlanCuenta).filter(PlanCuenta.parent_id == c.id).first():
        raise HTTPException(400, f"'{c.nombre}' no es cuenta hoja (tiene subcuentas)")

    if body.tasa_iva is not None and (body.tasa_iva < 0 or body.tasa_iva > 1):
        raise HTTPException(422, "tasa_iva debe estar entre 0 y 1 (ej. 0.21 = 21%)")

    c.tasa_iva = Decimal(str(body.tasa_iva)) if body.tasa_iva is not None else None
    registrar_log(db, current_user.id, "iva_config", c.id, "UPDATE",
                  {"codigo": c.codigo, "tasa_iva": body.tasa_iva})
    db.commit()
    db.refresh(c)
    return {
        "id": c.id,
        "codigo": c.codigo,
        "nombre": c.nombre,
        "tasa_iva": _f(c.tasa_iva),
    }


# ── Proyección ────────────────────────────────────────────────────

@router.get("/proyeccion")
def preview_proyeccion(
    periodo: str = Query(..., description="Período YYYY-MM"),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("view_accounting")),
):
    """Calcula la proyección de IVA del período sin persistir (preview)."""
    oid = _org_id(current_user, org_id)
    try:
        calc = calcular_proyeccion_iva(db, oid, periodo)
    except IvaServiceError as ex:
        raise HTTPException(400, str(ex))
    return {
        "periodo": calc["periodo"],
        "debito_fiscal": calc["debito_fiscal"],
        "credito_fiscal": calc["credito_fiscal"],
        "credito_fiscal_real": calc["credito_fiscal_real"],
        "credito_fiscal_proyectado": calc["credito_fiscal_proyectado"],
        "saldo": calc["saldo"],
        "detalle": calc["detalle"],
    }


@router.post("/proyeccion/calcular")
def calcular_y_guardar(
    periodo: str = Query(..., description="Período YYYY-MM"),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage_finance")),
):
    """Calcula y persiste la proyección (upsert por org+período)."""
    oid = _org_id(current_user, org_id)
    try:
        p = guardar_o_actualizar_proyeccion(db, oid, periodo)
    except IvaServiceError as ex:
        raise HTTPException(400, str(ex))
    registrar_log(db, current_user.id, "iva_proyeccion", p.id, "CALCULAR",
                  {"periodo": periodo, "saldo": float(p.saldo)})
    db.commit()
    return _proyeccion_dict(p)


@router.post("/proyeccion/{proyeccion_id}/marcar-presentada")
def marcar_proyeccion_presentada(
    proyeccion_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin_accounting")),
):
    """Marca la proyección como presentada (DDJJ enviada)."""
    p = db.query(ProyeccionIva).filter(ProyeccionIva.id == proyeccion_id).first()
    if not p:
        raise HTTPException(404, "Proyección no encontrada")
    if not current_user.is_superadmin and not can_switch_org(current_user, p.organizacion_id) \
            and p.organizacion_id != (current_user.organizacion_id or 1):
        raise HTTPException(403, "Sin acceso")
    try:
        p = marcar_presentada(db, p.organizacion_id, p.periodo)
    except IvaServiceError as ex:
        raise HTTPException(400, str(ex))
    registrar_log(db, current_user.id, "iva_proyeccion", p.id, "PRESENTAR",
                  {"periodo": p.periodo})
    db.commit()
    return _proyeccion_dict(p)


# ── Historial ─────────────────────────────────────────────────────

@router.get("/historial")
def historial(
    org_id: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("view_accounting")),
):
    """Lista los snapshots de proyección de la org, período descendente."""
    oid = _org_id(current_user, org_id)
    q = (
        db.query(ProyeccionIva)
        .filter(ProyeccionIva.organizacion_id == oid)
        .order_by(ProyeccionIva.periodo.desc(), ProyeccionIva.id.desc())
    )
    total = q.count()
    items = q.offset(offset).limit(limit).all()
    return {"items": [_proyeccion_dict(p) for p in items], "total": total}
