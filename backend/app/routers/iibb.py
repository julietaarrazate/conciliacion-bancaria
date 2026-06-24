"""Router del módulo Ingresos Brutos (IIBB) y Convenio Multilateral.

Endpoints (prefix /iibb):
  GET  /iibb/config                          — config opt-in de la org
  PUT  /iibb/config                          — upsert config (activo, modo, jurisdicción única)
  GET  /iibb/jurisdicciones                  — jurisdicciones de la org (paginado items/total)
  POST /iibb/jurisdicciones                  — crea una jurisdicción
  PUT  /iibb/jurisdicciones/{id}             — edita nombre/alícuota/coeficiente/activa
  GET  /iibb/proyeccion?periodo=YYYY-MM      — preview (no persiste)
  POST /iibb/proyeccion/calcular?periodo=    — calcula y persiste (upsert)
  POST /iibb/proyeccion/{id}/marcar-presentada
  GET  /iibb/historial                       — snapshots de la org, paginado

Permisos:
  config (GET/PUT)             → admin_accounting
  jurisdicciones (GET/POST/PUT)→ admin_accounting
  proyeccion (GET preview)     → view_accounting
  proyeccion/calcular (POST)   → manage_finance
  marcar-presentada (POST)     → admin_accounting
  historial (GET)              → view_accounting

Las alícuotas y coeficientes NO se siembran con valores reales — cada
jurisdicción tiene su régimen y cambian con frecuencia. El admin debe completar
y verificar todo contra AGIP (CABA), ARBA (Buenos Aires) o el organismo de cada
provincia. Todo es editable vía estos endpoints.
"""

from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import require_permission, can_switch_org
from app.models.iibb import IIBBConfig, JurisdiccionIIBB, ProyeccionIIBB
from app.models.user import User
from app.services.auditoria import registrar_log
from app.services.iibb_service import (
    calcular_proyeccion_iibb,
    guardar_o_actualizar_proyeccion,
    marcar_presentada,
    IIBBServiceError,
)

router = APIRouter(prefix="/iibb", tags=["iibb"])


# ── Helpers ───────────────────────────────────────────────────────

def _org_id(current_user: User, org_id: Optional[int]) -> int:
    if can_switch_org(current_user, org_id) and org_id:
        return org_id
    return current_user.organizacion_id or 1


def _f(v):
    return float(v) if isinstance(v, Decimal) else v


def _jurisdiccion_dict(j: JurisdiccionIIBB) -> dict:
    return {
        "id": j.id,
        "nombre": j.nombre,
        "alicuota": _f(j.alicuota),
        "coeficiente_distribucion": _f(j.coeficiente_distribucion),
        "activa": j.activa,
        "orden": j.orden,
    }


def _config_dict(c: Optional[IIBBConfig]) -> dict:
    if c is None:
        return {"activo": False, "modo": "simple", "jurisdiccion_unica_id": None}
    return {
        "activo": c.activo,
        "modo": c.modo,
        "jurisdiccion_unica_id": c.jurisdiccion_unica_id,
    }


def _proyeccion_dict(p: ProyeccionIIBB) -> dict:
    return {
        "id": p.id,
        "organizacion_id": p.organizacion_id,
        "periodo": p.periodo,
        "ingreso_total": p.ingreso_total,
        "impuesto_total": p.impuesto_total,
        "detalle_por_jurisdiccion": p.detalle_por_jurisdiccion,
        "estado": p.estado,
        "fecha_presentacion": p.fecha_presentacion,
        "created_at": p.created_at,
        "updated_at": p.updated_at,
    }


# ── Schemas ───────────────────────────────────────────────────────

class ConfigIn(BaseModel):
    activo: bool = False
    modo: str = "simple"
    jurisdiccion_unica_id: Optional[int] = None


class JurisdiccionIn(BaseModel):
    nombre: str
    alicuota: float = 0.0
    coeficiente_distribucion: float = 0.0
    activa: bool = True
    orden: int = 0


class JurisdiccionUpdateIn(BaseModel):
    nombre: Optional[str] = None
    alicuota: Optional[float] = None
    coeficiente_distribucion: Optional[float] = None
    activa: Optional[bool] = None
    orden: Optional[int] = None


# ── Config ────────────────────────────────────────────────────────

@router.get("/config")
def get_config(
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin_accounting")),
):
    """Devuelve la config del módulo para la org (defaults apagados si no existe)."""
    oid = _org_id(current_user, org_id)
    cfg = (
        db.query(IIBBConfig)
        .filter(IIBBConfig.organizacion_id == oid)
        .first()
    )
    return _config_dict(cfg)


@router.put("/config")
def put_config(
    body: ConfigIn,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin_accounting")),
):
    """Upsert de la config del módulo (1 fila por org)."""
    oid = _org_id(current_user, org_id)
    if body.modo not in ("simple", "convenio_multilateral"):
        raise HTTPException(422, "modo debe ser 'simple' o 'convenio_multilateral'")

    if body.jurisdiccion_unica_id is not None:
        jur = (
            db.query(JurisdiccionIIBB)
            .filter(
                JurisdiccionIIBB.id == body.jurisdiccion_unica_id,
                JurisdiccionIIBB.organizacion_id == oid,
            )
            .first()
        )
        if jur is None:
            raise HTTPException(404, "La jurisdicción única indicada no existe")

    cfg = (
        db.query(IIBBConfig)
        .filter(IIBBConfig.organizacion_id == oid)
        .first()
    )
    if cfg is None:
        cfg = IIBBConfig(organizacion_id=oid)
        db.add(cfg)

    cfg.activo = body.activo
    cfg.modo = body.modo
    cfg.jurisdiccion_unica_id = (
        body.jurisdiccion_unica_id if body.modo == "simple" else None
    )

    registrar_log(db, current_user.id, "iibb_config", oid, "UPDATE", {
        "activo": body.activo,
        "modo": body.modo,
        "jurisdiccion_unica_id": cfg.jurisdiccion_unica_id,
    })
    db.commit()
    db.refresh(cfg)
    return _config_dict(cfg)


# ── Jurisdicciones ────────────────────────────────────────────────

@router.get("/jurisdicciones")
def listar_jurisdicciones(
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin_accounting")),
):
    """Lista las jurisdicciones de la org, ordenadas por `orden`.

    ⚠️ Alícuotas/coeficientes de REFERENCIA — verificar contra AGIP/ARBA/organismo
    provincial antes de usarlos."""
    oid = _org_id(current_user, org_id)
    items = (
        db.query(JurisdiccionIIBB)
        .filter(JurisdiccionIIBB.organizacion_id == oid)
        .order_by(JurisdiccionIIBB.orden.asc(), JurisdiccionIIBB.id.asc())
        .all()
    )
    return {"items": [_jurisdiccion_dict(j) for j in items], "total": len(items)}


def _validar_tasas(alicuota: Optional[float], coef: Optional[float]) -> None:
    if alicuota is not None and (alicuota < 0 or alicuota > 1):
        raise HTTPException(422, "alicuota debe estar entre 0 y 1 (ej. 0.05 = 5%)")
    if coef is not None and (coef < 0 or coef > 1):
        raise HTTPException(422, "coeficiente_distribucion debe estar entre 0 y 1 (ej. 0.6 = 60%)")


@router.post("/jurisdicciones")
def crear_jurisdiccion(
    body: JurisdiccionIn,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin_accounting")),
):
    """Crea una jurisdicción para la org."""
    oid = _org_id(current_user, org_id)
    nombre = (body.nombre or "").strip()
    if not nombre:
        raise HTTPException(422, "El nombre de la jurisdicción es obligatorio")
    _validar_tasas(body.alicuota, body.coeficiente_distribucion)

    dup = (
        db.query(JurisdiccionIIBB)
        .filter(
            JurisdiccionIIBB.organizacion_id == oid,
            JurisdiccionIIBB.nombre == nombre,
        )
        .first()
    )
    if dup is not None:
        raise HTTPException(409, f"Ya existe una jurisdicción '{nombre}' en esta organización")

    j = JurisdiccionIIBB(
        organizacion_id=oid,
        nombre=nombre,
        alicuota=Decimal(str(body.alicuota)),
        coeficiente_distribucion=Decimal(str(body.coeficiente_distribucion)),
        activa=body.activa,
        orden=body.orden,
    )
    db.add(j)
    registrar_log(db, current_user.id, "iibb_jurisdiccion", oid, "CREATE", {
        "nombre": nombre, "alicuota": body.alicuota,
        "coeficiente_distribucion": body.coeficiente_distribucion,
    })
    db.commit()
    db.refresh(j)
    return _jurisdiccion_dict(j)


@router.put("/jurisdicciones/{jur_id}")
def editar_jurisdiccion(
    jur_id: int,
    body: JurisdiccionUpdateIn,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin_accounting")),
):
    """Edita una jurisdicción (update parcial)."""
    oid = _org_id(current_user, org_id)
    j = (
        db.query(JurisdiccionIIBB)
        .filter(
            JurisdiccionIIBB.id == jur_id,
            JurisdiccionIIBB.organizacion_id == oid,
        )
        .first()
    )
    if j is None:
        raise HTTPException(404, "Jurisdicción no encontrada")
    _validar_tasas(body.alicuota, body.coeficiente_distribucion)

    if body.nombre is not None:
        nombre = body.nombre.strip()
        if not nombre:
            raise HTTPException(422, "El nombre no puede quedar vacío")
        dup = (
            db.query(JurisdiccionIIBB)
            .filter(
                JurisdiccionIIBB.organizacion_id == oid,
                JurisdiccionIIBB.nombre == nombre,
                JurisdiccionIIBB.id != jur_id,
            )
            .first()
        )
        if dup is not None:
            raise HTTPException(409, f"Ya existe una jurisdicción '{nombre}'")
        j.nombre = nombre
    if body.alicuota is not None:
        j.alicuota = Decimal(str(body.alicuota))
    if body.coeficiente_distribucion is not None:
        j.coeficiente_distribucion = Decimal(str(body.coeficiente_distribucion))
    if body.activa is not None:
        j.activa = body.activa
    if body.orden is not None:
        j.orden = body.orden

    registrar_log(db, current_user.id, "iibb_jurisdiccion", j.id, "UPDATE", {
        "nombre": j.nombre, "alicuota": _f(j.alicuota),
        "coeficiente_distribucion": _f(j.coeficiente_distribucion),
        "activa": j.activa,
    })
    db.commit()
    db.refresh(j)
    return _jurisdiccion_dict(j)


# ── Proyección ────────────────────────────────────────────────────

@router.get("/proyeccion")
def preview_proyeccion(
    periodo: str = Query(..., description="Período YYYY-MM"),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("view_accounting")),
):
    """Calcula la proyección de IIBB del período sin persistir (preview)."""
    oid = _org_id(current_user, org_id)
    try:
        calc = calcular_proyeccion_iibb(db, oid, periodo)
    except IIBBServiceError as ex:
        raise HTTPException(400, str(ex))
    return calc


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
    except IIBBServiceError as ex:
        raise HTTPException(400, str(ex))
    registrar_log(db, current_user.id, "iibb_proyeccion", p.id, "CALCULAR", {
        "periodo": periodo, "impuesto_total": float(p.impuesto_total),
    })
    db.commit()
    return _proyeccion_dict(p)


@router.post("/proyeccion/{proyeccion_id}/marcar-presentada")
def marcar_proyeccion_presentada(
    proyeccion_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin_accounting")),
):
    """Marca la proyección como presentada (DDJJ enviada)."""
    p = db.query(ProyeccionIIBB).filter(ProyeccionIIBB.id == proyeccion_id).first()
    if not p:
        raise HTTPException(404, "Proyección no encontrada")
    if not current_user.is_superadmin and not can_switch_org(current_user, p.organizacion_id) \
            and p.organizacion_id != (current_user.organizacion_id or 1):
        raise HTTPException(403, "Sin acceso")
    try:
        p = marcar_presentada(db, p.organizacion_id, p.periodo)
    except IIBBServiceError as ex:
        raise HTTPException(400, str(ex))
    registrar_log(db, current_user.id, "iibb_proyeccion", p.id, "PRESENTAR", {
        "periodo": p.periodo,
    })
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
        db.query(ProyeccionIIBB)
        .filter(ProyeccionIIBB.organizacion_id == oid)
        .order_by(ProyeccionIIBB.periodo.desc(), ProyeccionIIBB.id.desc())
    )
    total = q.count()
    items = q.offset(offset).limit(limit).all()
    return {"items": [_proyeccion_dict(p) for p in items], "total": total}
