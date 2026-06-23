"""Router del módulo Control Semestral Monotributo.

Endpoints (prefix /monotributo):
  GET  /monotributo/config                         — config opt-in de la org
  PUT  /monotributo/config                         — upsert config (activo, categoría actual, tipo)
  GET  /monotributo/categorias?tipo_actividad=     — escalas de categorías (paginado por items/total)
  PUT  /monotributo/categorias/{cat_id}            — edita el límite anual de una categoría
  GET  /monotributo/control?periodo=YYYY-S1        — preview del control (no persiste)
  POST /monotributo/control/calcular?periodo=      — calcula y persiste (upsert)
  POST /monotributo/control/{id}/marcar-revisado
  GET  /monotributo/historial                      — snapshots de la org, paginado

Permisos:
  config (GET/PUT)             → admin_accounting
  categorias (GET)             → view_accounting
  categorias (PUT)             → admin_accounting
  control (GET preview)        → view_accounting
  control/calcular (POST)      → manage_finance
  marcar-revisado (POST)       → admin_accounting
  historial (GET)              → view_accounting

⚠️ Los límites de categoría sembrados son VALORES DE REFERENCIA. El admin debe
verificarlos y actualizarlos contra la tabla oficial vigente de arca.gob.ar antes
de tomar decisiones reales de recategorización.
"""

from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import require_permission, can_switch_org
from app.models.monotributo import (
    CategoriaMonotributo, MonotributoConfig, ControlMonotributo,
)
from app.models.user import User
from app.services.auditoria import registrar_log
from app.services.monotributo_service import (
    calcular_control_semestral,
    guardar_o_actualizar_control,
    marcar_revisado,
    MonotributoServiceError,
)

router = APIRouter(prefix="/monotributo", tags=["monotributo"])


# ── Helpers ───────────────────────────────────────────────────────

def _org_id(current_user: User, org_id: Optional[int]) -> int:
    if can_switch_org(current_user, org_id) and org_id:
        return org_id
    return current_user.organizacion_id or 1


def _f(v):
    return float(v) if isinstance(v, Decimal) else v


def _categoria_dict(c: CategoriaMonotributo) -> dict:
    return {
        "id": c.id,
        "categoria": c.categoria,
        "tipo_actividad": c.tipo_actividad,
        "limite_anual": c.limite_anual,
        "orden": c.orden,
    }


def _control_dict(c: ControlMonotributo) -> dict:
    return {
        "id": c.id,
        "organizacion_id": c.organizacion_id,
        "periodo": c.periodo,
        "fecha_corte": c.fecha_corte,
        "ingresos_12m": c.ingresos_12m,
        "categoria_actual": c.categoria_actual,
        "limite_categoria_actual": c.limite_categoria_actual,
        "porcentaje_uso": c.porcentaje_uso,
        "categoria_sugerida": c.categoria_sugerida,
        "excede": c.excede,
        "estado": c.estado,
        "fecha_revision": c.fecha_revision,
        "detalle": c.detalle,
        "created_at": c.created_at,
        "updated_at": c.updated_at,
    }


# ── Schemas ───────────────────────────────────────────────────────

class ConfigIn(BaseModel):
    activo: bool = False
    categoria_actual: Optional[str] = None
    tipo_actividad: str = "servicios"


class LimiteIn(BaseModel):
    limite_anual: float


# ── Config ────────────────────────────────────────────────────────

@router.get("/config")
def get_config(
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin_accounting")),
):
    """Devuelve la config del módulo para la org. Si no existe fila, devuelve los
    defaults (apagado) sin crearla."""
    oid = _org_id(current_user, org_id)
    cfg = (
        db.query(MonotributoConfig)
        .filter(MonotributoConfig.organizacion_id == oid)
        .first()
    )
    if cfg is None:
        return {
            "activo": False,
            "categoria_actual": None,
            "tipo_actividad": "servicios",
        }
    return {
        "activo": cfg.activo,
        "categoria_actual": cfg.categoria_actual,
        "tipo_actividad": cfg.tipo_actividad,
    }


@router.put("/config")
def put_config(
    body: ConfigIn,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin_accounting")),
):
    """Upsert de la config del módulo (1 fila por org)."""
    oid = _org_id(current_user, org_id)
    if body.tipo_actividad not in ("servicios", "bienes"):
        raise HTTPException(422, "tipo_actividad debe ser 'servicios' o 'bienes'")

    cfg = (
        db.query(MonotributoConfig)
        .filter(MonotributoConfig.organizacion_id == oid)
        .first()
    )
    if cfg is None:
        cfg = MonotributoConfig(organizacion_id=oid)
        db.add(cfg)

    cfg.activo = body.activo
    cfg.categoria_actual = body.categoria_actual or None
    cfg.tipo_actividad = body.tipo_actividad

    registrar_log(db, current_user.id, "monotributo_config", oid, "UPDATE", {
        "activo": body.activo,
        "categoria_actual": cfg.categoria_actual,
        "tipo_actividad": cfg.tipo_actividad,
    })
    db.commit()
    db.refresh(cfg)
    return {
        "activo": cfg.activo,
        "categoria_actual": cfg.categoria_actual,
        "tipo_actividad": cfg.tipo_actividad,
    }


# ── Categorías ────────────────────────────────────────────────────

@router.get("/categorias")
def listar_categorias(
    tipo_actividad: Optional[str] = Query(None),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("view_accounting")),
):
    """Lista las escalas de categorías de la org, ordenadas por `orden`.

    ⚠️ Límites de REFERENCIA — verificar contra arca.gob.ar antes de usarlos."""
    oid = _org_id(current_user, org_id)
    q = db.query(CategoriaMonotributo).filter(
        CategoriaMonotributo.organizacion_id == oid
    )
    if tipo_actividad:
        q = q.filter(CategoriaMonotributo.tipo_actividad == tipo_actividad)
    items = q.order_by(
        CategoriaMonotributo.tipo_actividad.asc(),
        CategoriaMonotributo.orden.asc(),
    ).all()
    return {"items": [_categoria_dict(c) for c in items], "total": len(items)}


@router.put("/categorias/{cat_id}")
def editar_limite_categoria(
    cat_id: int,
    body: LimiteIn,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin_accounting")),
):
    """Edita el límite anual de una categoría (no permite cambiar categoria/tipo)."""
    oid = _org_id(current_user, org_id)
    c = (
        db.query(CategoriaMonotributo)
        .filter(
            CategoriaMonotributo.id == cat_id,
            CategoriaMonotributo.organizacion_id == oid,
        )
        .first()
    )
    if not c:
        raise HTTPException(404, "Categoría no encontrada")
    if body.limite_anual < 0:
        raise HTTPException(422, "limite_anual no puede ser negativo")

    c.limite_anual = Decimal(str(body.limite_anual))
    registrar_log(db, current_user.id, "monotributo_categoria", c.id, "UPDATE", {
        "categoria": c.categoria,
        "tipo_actividad": c.tipo_actividad,
        "limite_anual": body.limite_anual,
    })
    db.commit()
    db.refresh(c)
    return _categoria_dict(c)


# ── Control semestral ─────────────────────────────────────────────

@router.get("/control")
def preview_control(
    periodo: str = Query(..., description="Período YYYY-S1 / YYYY-S2"),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("view_accounting")),
):
    """Calcula el control semestral del período sin persistir (preview)."""
    oid = _org_id(current_user, org_id)
    try:
        calc = calcular_control_semestral(db, oid, periodo)
    except MonotributoServiceError as ex:
        raise HTTPException(400, str(ex))
    return calc


@router.post("/control/calcular")
def calcular_y_guardar(
    periodo: str = Query(..., description="Período YYYY-S1 / YYYY-S2"),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage_finance")),
):
    """Calcula y persiste el control semestral (upsert por org+período)."""
    oid = _org_id(current_user, org_id)
    try:
        c = guardar_o_actualizar_control(db, oid, periodo)
    except MonotributoServiceError as ex:
        raise HTTPException(400, str(ex))
    registrar_log(db, current_user.id, "monotributo_control", c.id, "CALCULAR", {
        "periodo": periodo,
        "ingresos_12m": float(c.ingresos_12m),
        "categoria_sugerida": c.categoria_sugerida,
        "excede": c.excede,
    })
    db.commit()
    return _control_dict(c)


@router.post("/control/{control_id}/marcar-revisado")
def marcar_control_revisado(
    control_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin_accounting")),
):
    """Marca el control como revisado."""
    c = db.query(ControlMonotributo).filter(ControlMonotributo.id == control_id).first()
    if not c:
        raise HTTPException(404, "Control no encontrado")
    if not current_user.is_superadmin and not can_switch_org(current_user, c.organizacion_id) \
            and c.organizacion_id != (current_user.organizacion_id or 1):
        raise HTTPException(403, "Sin acceso")
    try:
        c = marcar_revisado(db, c.organizacion_id, c.periodo)
    except MonotributoServiceError as ex:
        raise HTTPException(400, str(ex))
    registrar_log(db, current_user.id, "monotributo_control", c.id, "REVISAR", {
        "periodo": c.periodo,
    })
    db.commit()
    return _control_dict(c)


# ── Historial ─────────────────────────────────────────────────────

@router.get("/historial")
def historial(
    org_id: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("view_accounting")),
):
    """Lista los snapshots de control de la org, período descendente."""
    oid = _org_id(current_user, org_id)
    q = (
        db.query(ControlMonotributo)
        .filter(ControlMonotributo.organizacion_id == oid)
        .order_by(ControlMonotributo.periodo.desc(), ControlMonotributo.id.desc())
    )
    total = q.count()
    items = q.offset(offset).limit(limit).all()
    return {"items": [_control_dict(c) for c in items], "total": total}
