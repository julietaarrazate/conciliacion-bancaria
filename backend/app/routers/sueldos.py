"""Router del módulo Liquidador de Sueldos y F931.

Endpoints (prefix /sueldos):
  Convenios / Categorías / Empleados (CRUD) — admin_accounting (escritura), view_accounting (lectura)
  GET/PUT /sueldos/config                          — alícuotas de aportes/contribuciones (admin_accounting)
  GET  /sueldos/liquidacion?periodo=YYYY-MM        — preview (view_accounting)
  POST /sueldos/liquidacion/calcular?periodo=      — calcula y persiste (manage_finance)
  POST /sueldos/liquidacion/{id}/aprobar           — aprueba + genera asiento (manage_finance)
  POST /sueldos/liquidacion/{id}/marcar-presentada — F931 enviado, inmutable (admin_accounting)
  GET  /sueldos/liquidacion/{id}/empleado/{eid}/recibo-pdf — recibo de sueldo PDF (view_accounting)
  GET  /sueldos/liquidacion/{id}/exportar-sicoss   — archivo SICOSS, formato de referencia (manage_finance)
  GET  /sueldos/historial                          — snapshots de la org, paginado (view_accounting)

NO sustituye un sistema de liquidación de sueldos homologado ni reemplaza el
SUSS/AFIP — es una herramienta de gestión interna del estudio. Las alícuotas son
valores de referencia editables; verificar vigencia con el contador/AFIP.
"""

from decimal import Decimal
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import require_permission, can_switch_org
from app.models.sueldos import (
    ConvenioColectivo,
    CategoriaConvenio,
    Empleado,
    ConfigSueldos,
    EscalaGanancias,
    LiquidacionSueldoPeriodo,
    DetalleLiquidacionEmpleado,
)
from app.models.user import User
from app.services.auditoria import registrar_log
from app.services.sueldos_service import (
    get_o_crear_config,
    calcular_liquidacion_periodo,
    guardar_o_actualizar_liquidacion,
    aprobar_liquidacion,
    marcar_presentada,
    SueldosServiceError,
)

router = APIRouter(prefix="/sueldos", tags=["sueldos"])


# ── Helpers ───────────────────────────────────────────────────────

def _org_id(current_user: User, org_id: Optional[int]) -> int:
    if can_switch_org(current_user, org_id) and org_id:
        return org_id
    return current_user.organizacion_id or 1


def _f(v):
    return float(v) if isinstance(v, Decimal) else v


def _validar_cuil(cuil: Optional[str]) -> Optional[str]:
    if not cuil:
        return None
    digits = cuil.replace("-", "").replace(" ", "")
    if not digits.isdigit() or len(digits) != 11:
        raise HTTPException(400, "CUIL inválido: debe tener 11 dígitos numéricos")
    return digits


def _convenio_dict(c: ConvenioColectivo) -> dict:
    return {
        "id": c.id, "nombre": c.nombre, "descripcion": c.descripcion,
        "activo": c.activo,
    }


def _categoria_dict(c: CategoriaConvenio) -> dict:
    return {
        "id": c.id, "convenio_id": c.convenio_id, "nombre": c.nombre,
        "sueldo_basico": _f(c.sueldo_basico), "orden": c.orden,
    }


def _empleado_dict(e: Empleado) -> dict:
    return {
        "id": e.id, "nombre": e.nombre, "cuil": e.cuil,
        "convenio_id": e.convenio_id, "categoria_id": e.categoria_id,
        "fecha_ingreso": e.fecha_ingreso.isoformat() if e.fecha_ingreso else None,
        "sueldo_basico": _f(e.sueldo_basico), "cargas_familia": e.cargas_familia,
        "activo": e.activo,
    }


def _config_dict(c: ConfigSueldos) -> dict:
    return {
        "activo": c.activo,
        "aporte_jubilacion": _f(c.aporte_jubilacion),
        "aporte_inssjp": _f(c.aporte_inssjp),
        "aporte_obra_social": _f(c.aporte_obra_social),
        "contrib_jubilacion": _f(c.contrib_jubilacion),
        "contrib_inssjp": _f(c.contrib_inssjp),
        "contrib_obra_social": _f(c.contrib_obra_social),
        "contrib_asig_fam": _f(c.contrib_asig_fam),
        "contrib_fondo_desempleo": _f(c.contrib_fondo_desempleo),
        "alicuota_art": _f(c.alicuota_art),
        "ganancias_activo": c.ganancias_activo,
        "minimo_no_imponible": _f(c.minimo_no_imponible),
        "deduccion_especial": _f(c.deduccion_especial),
    }


def _escala_dict(t: EscalaGanancias) -> dict:
    return {
        "id": t.id,
        "tramo_desde": _f(t.tramo_desde),
        "tramo_hasta": _f(t.tramo_hasta) if t.tramo_hasta is not None else None,
        "alicuota": _f(t.alicuota),
        "monto_fijo": _f(t.monto_fijo),
    }


def _liquidacion_dict(liq: LiquidacionSueldoPeriodo, incluir_detalle: bool = False) -> dict:
    d = {
        "id": liq.id,
        "organizacion_id": liq.organizacion_id,
        "periodo": liq.periodo,
        "estado": liq.estado,
        "total_bruto": liq.total_bruto,
        "total_aportes": liq.total_aportes,
        "total_contribuciones": liq.total_contribuciones,
        "total_neto": liq.total_neto,
        "fecha_aprobacion": liq.fecha_aprobacion,
        "fecha_presentacion": liq.fecha_presentacion,
        "created_at": liq.created_at,
        "updated_at": liq.updated_at,
    }
    if incluir_detalle:
        d["detalle"] = [{
            "empleado_id": x.empleado_id,
            "sueldo_bruto": x.sueldo_bruto,
            "sac_proporcional": x.sac_proporcional,
            "total_aportes": x.total_aportes,
            "total_contribuciones": x.total_contribuciones,
            "sueldo_neto": x.sueldo_neto,
            "retencion_ganancias": x.retencion_ganancias,
            "detalle_json": x.detalle_json,
        } for x in liq.detalles]
    return d


# ── Schemas ───────────────────────────────────────────────────────

class ConvenioIn(BaseModel):
    nombre: str
    descripcion: Optional[str] = None
    activo: bool = True


class ConvenioUpdateIn(BaseModel):
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    activo: Optional[bool] = None


class CategoriaIn(BaseModel):
    nombre: str
    sueldo_basico: float = 0.0
    orden: int = 0


class CategoriaUpdateIn(BaseModel):
    nombre: Optional[str] = None
    sueldo_basico: Optional[float] = None
    orden: Optional[int] = None


class EmpleadoIn(BaseModel):
    nombre: str
    cuil: Optional[str] = None
    convenio_id: Optional[int] = None
    categoria_id: Optional[int] = None
    fecha_ingreso: Optional[str] = None  # ISO date
    sueldo_basico: Optional[float] = None
    cargas_familia: int = 0
    activo: bool = True


class EmpleadoUpdateIn(BaseModel):
    nombre: Optional[str] = None
    cuil: Optional[str] = None
    convenio_id: Optional[int] = None
    categoria_id: Optional[int] = None
    fecha_ingreso: Optional[str] = None
    sueldo_basico: Optional[float] = None
    cargas_familia: Optional[int] = None
    activo: Optional[bool] = None


class ConfigIn(BaseModel):
    activo: bool = False
    aporte_jubilacion: float = 0.0
    aporte_inssjp: float = 0.0
    aporte_obra_social: float = 0.0
    contrib_jubilacion: float = 0.0
    contrib_inssjp: float = 0.0
    contrib_obra_social: float = 0.0
    contrib_asig_fam: float = 0.0
    contrib_fondo_desempleo: float = 0.0
    alicuota_art: float = 0.0
    ganancias_activo: bool = False
    minimo_no_imponible: float = 0.0
    deduccion_especial: float = 0.0


class EscalaTramoIn(BaseModel):
    tramo_desde: float = 0.0
    tramo_hasta: Optional[float] = None  # None = último tramo (sin techo)
    alicuota: float = 0.0
    monto_fijo: float = 0.0


class EscalaTramoUpdateIn(BaseModel):
    tramo_desde: Optional[float] = None
    tramo_hasta: Optional[float] = None
    alicuota: Optional[float] = None
    monto_fijo: Optional[float] = None
    limpiar_tramo_hasta: bool = False  # True = forzar tramo_hasta a NULL (último tramo)


# ── Convenios ─────────────────────────────────────────────────────

@router.get("/convenios")
def listar_convenios(
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("view_accounting")),
):
    oid = _org_id(current_user, org_id)
    items = (
        db.query(ConvenioColectivo)
        .filter(ConvenioColectivo.organizacion_id == oid)
        .order_by(ConvenioColectivo.nombre.asc())
        .all()
    )
    return {"items": [_convenio_dict(c) for c in items], "total": len(items)}


@router.post("/convenios")
def crear_convenio(
    body: ConvenioIn,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin_accounting")),
):
    oid = _org_id(current_user, org_id)
    nombre = (body.nombre or "").strip()
    if not nombre:
        raise HTTPException(422, "El nombre del convenio es obligatorio")
    dup = (
        db.query(ConvenioColectivo)
        .filter(ConvenioColectivo.organizacion_id == oid, ConvenioColectivo.nombre == nombre)
        .first()
    )
    if dup is not None:
        raise HTTPException(409, f"Ya existe un convenio '{nombre}' en esta organización")
    c = ConvenioColectivo(
        organizacion_id=oid, nombre=nombre,
        descripcion=(body.descripcion or None), activo=body.activo,
    )
    db.add(c)
    registrar_log(db, current_user.id, "sueldos_convenio", oid, "CREATE", {"nombre": nombre})
    db.commit()
    db.refresh(c)
    return _convenio_dict(c)


@router.put("/convenios/{convenio_id}")
def editar_convenio(
    convenio_id: int,
    body: ConvenioUpdateIn,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin_accounting")),
):
    oid = _org_id(current_user, org_id)
    c = (
        db.query(ConvenioColectivo)
        .filter(ConvenioColectivo.id == convenio_id, ConvenioColectivo.organizacion_id == oid)
        .first()
    )
    if c is None:
        raise HTTPException(404, "Convenio no encontrado")
    if body.nombre is not None:
        nombre = body.nombre.strip()
        if not nombre:
            raise HTTPException(422, "El nombre no puede quedar vacío")
        dup = (
            db.query(ConvenioColectivo)
            .filter(
                ConvenioColectivo.organizacion_id == oid,
                ConvenioColectivo.nombre == nombre,
                ConvenioColectivo.id != convenio_id,
            )
            .first()
        )
        if dup is not None:
            raise HTTPException(409, f"Ya existe un convenio '{nombre}'")
        c.nombre = nombre
    if body.descripcion is not None:
        c.descripcion = body.descripcion or None
    if body.activo is not None:
        c.activo = body.activo
    registrar_log(db, current_user.id, "sueldos_convenio", c.id, "UPDATE", {"nombre": c.nombre})
    db.commit()
    db.refresh(c)
    return _convenio_dict(c)


@router.delete("/convenios/{convenio_id}")
def borrar_convenio(
    convenio_id: int,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("delete_records")),
):
    oid = _org_id(current_user, org_id)
    c = (
        db.query(ConvenioColectivo)
        .filter(ConvenioColectivo.id == convenio_id, ConvenioColectivo.organizacion_id == oid)
        .first()
    )
    if c is None:
        raise HTTPException(404, "Convenio no encontrado")
    # desvincular empleados que apuntan a este convenio/categorías
    db.query(Empleado).filter(
        Empleado.convenio_id == convenio_id, Empleado.organizacion_id == oid
    ).update({Empleado.convenio_id: None, Empleado.categoria_id: None}, synchronize_session=False)
    db.delete(c)  # cascade borra las categorías
    registrar_log(db, current_user.id, "sueldos_convenio", convenio_id, "DELETE", {})
    db.commit()
    return {"ok": True}


# ── Categorías ────────────────────────────────────────────────────

@router.get("/convenios/{convenio_id}/categorias")
def listar_categorias(
    convenio_id: int,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("view_accounting")),
):
    oid = _org_id(current_user, org_id)
    conv = (
        db.query(ConvenioColectivo)
        .filter(ConvenioColectivo.id == convenio_id, ConvenioColectivo.organizacion_id == oid)
        .first()
    )
    if conv is None:
        raise HTTPException(404, "Convenio no encontrado")
    items = (
        db.query(CategoriaConvenio)
        .filter(CategoriaConvenio.convenio_id == convenio_id)
        .order_by(CategoriaConvenio.orden.asc(), CategoriaConvenio.id.asc())
        .all()
    )
    return {"items": [_categoria_dict(c) for c in items], "total": len(items)}


@router.post("/convenios/{convenio_id}/categorias")
def crear_categoria(
    convenio_id: int,
    body: CategoriaIn,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin_accounting")),
):
    oid = _org_id(current_user, org_id)
    conv = (
        db.query(ConvenioColectivo)
        .filter(ConvenioColectivo.id == convenio_id, ConvenioColectivo.organizacion_id == oid)
        .first()
    )
    if conv is None:
        raise HTTPException(404, "Convenio no encontrado")
    nombre = (body.nombre or "").strip()
    if not nombre:
        raise HTTPException(422, "El nombre de la categoría es obligatorio")
    if body.sueldo_basico < 0:
        raise HTTPException(422, "El sueldo básico no puede ser negativo")
    dup = (
        db.query(CategoriaConvenio)
        .filter(CategoriaConvenio.convenio_id == convenio_id, CategoriaConvenio.nombre == nombre)
        .first()
    )
    if dup is not None:
        raise HTTPException(409, f"Ya existe una categoría '{nombre}' en este convenio")
    c = CategoriaConvenio(
        convenio_id=convenio_id, nombre=nombre,
        sueldo_basico=Decimal(str(body.sueldo_basico)), orden=body.orden,
    )
    db.add(c)
    registrar_log(db, current_user.id, "sueldos_categoria", convenio_id, "CREATE", {"nombre": nombre})
    db.commit()
    db.refresh(c)
    return _categoria_dict(c)


@router.put("/categorias/{categoria_id}")
def editar_categoria(
    categoria_id: int,
    body: CategoriaUpdateIn,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin_accounting")),
):
    oid = _org_id(current_user, org_id)
    c = (
        db.query(CategoriaConvenio)
        .join(ConvenioColectivo, CategoriaConvenio.convenio_id == ConvenioColectivo.id)
        .filter(CategoriaConvenio.id == categoria_id, ConvenioColectivo.organizacion_id == oid)
        .first()
    )
    if c is None:
        raise HTTPException(404, "Categoría no encontrada")
    if body.nombre is not None:
        nombre = body.nombre.strip()
        if not nombre:
            raise HTTPException(422, "El nombre no puede quedar vacío")
        dup = (
            db.query(CategoriaConvenio)
            .filter(
                CategoriaConvenio.convenio_id == c.convenio_id,
                CategoriaConvenio.nombre == nombre,
                CategoriaConvenio.id != categoria_id,
            )
            .first()
        )
        if dup is not None:
            raise HTTPException(409, f"Ya existe una categoría '{nombre}'")
        c.nombre = nombre
    if body.sueldo_basico is not None:
        if body.sueldo_basico < 0:
            raise HTTPException(422, "El sueldo básico no puede ser negativo")
        c.sueldo_basico = Decimal(str(body.sueldo_basico))
    if body.orden is not None:
        c.orden = body.orden
    registrar_log(db, current_user.id, "sueldos_categoria", c.id, "UPDATE", {"nombre": c.nombre})
    db.commit()
    db.refresh(c)
    return _categoria_dict(c)


@router.delete("/categorias/{categoria_id}")
def borrar_categoria(
    categoria_id: int,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("delete_records")),
):
    oid = _org_id(current_user, org_id)
    c = (
        db.query(CategoriaConvenio)
        .join(ConvenioColectivo, CategoriaConvenio.convenio_id == ConvenioColectivo.id)
        .filter(CategoriaConvenio.id == categoria_id, ConvenioColectivo.organizacion_id == oid)
        .first()
    )
    if c is None:
        raise HTTPException(404, "Categoría no encontrada")
    db.query(Empleado).filter(
        Empleado.categoria_id == categoria_id, Empleado.organizacion_id == oid
    ).update({Empleado.categoria_id: None}, synchronize_session=False)
    db.delete(c)
    registrar_log(db, current_user.id, "sueldos_categoria", categoria_id, "DELETE", {})
    db.commit()
    return {"ok": True}


# ── Empleados ─────────────────────────────────────────────────────

def _parse_fecha(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        raise HTTPException(422, "fecha_ingreso inválida (use formato YYYY-MM-DD)")


def _validar_fks_empleado(db: Session, oid: int, convenio_id, categoria_id) -> None:
    if convenio_id is not None:
        conv = (
            db.query(ConvenioColectivo)
            .filter(ConvenioColectivo.id == convenio_id, ConvenioColectivo.organizacion_id == oid)
            .first()
        )
        if conv is None:
            raise HTTPException(404, "Convenio no encontrado")
    if categoria_id is not None:
        cat = (
            db.query(CategoriaConvenio)
            .join(ConvenioColectivo, CategoriaConvenio.convenio_id == ConvenioColectivo.id)
            .filter(CategoriaConvenio.id == categoria_id, ConvenioColectivo.organizacion_id == oid)
            .first()
        )
        if cat is None:
            raise HTTPException(404, "Categoría no encontrada")


@router.get("/empleados")
def listar_empleados(
    org_id: Optional[int] = Query(None),
    incluir_inactivos: bool = Query(False),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("view_accounting")),
):
    oid = _org_id(current_user, org_id)
    q = (
        db.query(Empleado)
        .filter(Empleado.organizacion_id == oid, Empleado.deleted_at.is_(None))
    )
    if not incluir_inactivos:
        q = q.filter(Empleado.activo == True)  # noqa: E712
    q = q.order_by(Empleado.nombre.asc(), Empleado.id.asc())
    total = q.count()
    items = q.offset(offset).limit(limit).all()
    return {"items": [_empleado_dict(e) for e in items], "total": total}


@router.post("/empleados")
def crear_empleado(
    body: EmpleadoIn,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin_accounting")),
):
    oid = _org_id(current_user, org_id)
    nombre = (body.nombre or "").strip()
    if not nombre:
        raise HTTPException(422, "El nombre del empleado es obligatorio")
    cuil = _validar_cuil(body.cuil)
    if body.sueldo_basico is not None and body.sueldo_basico < 0:
        raise HTTPException(422, "El sueldo básico no puede ser negativo")
    _validar_fks_empleado(db, oid, body.convenio_id, body.categoria_id)
    e = Empleado(
        organizacion_id=oid, nombre=nombre, cuil=cuil,
        convenio_id=body.convenio_id, categoria_id=body.categoria_id,
        fecha_ingreso=_parse_fecha(body.fecha_ingreso),
        sueldo_basico=(Decimal(str(body.sueldo_basico)) if body.sueldo_basico is not None else None),
        cargas_familia=body.cargas_familia, activo=body.activo,
    )
    db.add(e)
    registrar_log(db, current_user.id, "sueldos_empleado", oid, "CREATE", {"nombre": nombre})
    db.commit()
    db.refresh(e)
    return _empleado_dict(e)


@router.put("/empleados/{empleado_id}")
def editar_empleado(
    empleado_id: int,
    body: EmpleadoUpdateIn,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin_accounting")),
):
    oid = _org_id(current_user, org_id)
    e = (
        db.query(Empleado)
        .filter(Empleado.id == empleado_id, Empleado.organizacion_id == oid, Empleado.deleted_at.is_(None))
        .first()
    )
    if e is None:
        raise HTTPException(404, "Empleado no encontrado")
    _validar_fks_empleado(db, oid, body.convenio_id, body.categoria_id)
    if body.nombre is not None:
        nombre = body.nombre.strip()
        if not nombre:
            raise HTTPException(422, "El nombre no puede quedar vacío")
        e.nombre = nombre
    if body.cuil is not None:
        e.cuil = _validar_cuil(body.cuil)
    if body.convenio_id is not None:
        e.convenio_id = body.convenio_id
    if body.categoria_id is not None:
        e.categoria_id = body.categoria_id
    if body.fecha_ingreso is not None:
        e.fecha_ingreso = _parse_fecha(body.fecha_ingreso)
    if body.sueldo_basico is not None:
        if body.sueldo_basico < 0:
            raise HTTPException(422, "El sueldo básico no puede ser negativo")
        e.sueldo_basico = Decimal(str(body.sueldo_basico))
    if body.cargas_familia is not None:
        e.cargas_familia = body.cargas_familia
    if body.activo is not None:
        e.activo = body.activo
    registrar_log(db, current_user.id, "sueldos_empleado", e.id, "UPDATE", {"nombre": e.nombre})
    db.commit()
    db.refresh(e)
    return _empleado_dict(e)


@router.delete("/empleados/{empleado_id}")
def borrar_empleado(
    empleado_id: int,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("delete_records")),
):
    """Soft delete del empleado (mismo patrón que Planilla: deleted_at)."""
    from app.services.tz import now_art
    oid = _org_id(current_user, org_id)
    e = (
        db.query(Empleado)
        .filter(Empleado.id == empleado_id, Empleado.organizacion_id == oid, Empleado.deleted_at.is_(None))
        .first()
    )
    if e is None:
        raise HTTPException(404, "Empleado no encontrado")
    e.deleted_at = now_art()
    e.activo = False
    registrar_log(db, current_user.id, "sueldos_empleado", empleado_id, "DELETE", {})
    db.commit()
    return {"ok": True}


# ── Config (alícuotas) ────────────────────────────────────────────

@router.get("/config")
def get_config(
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin_accounting")),
):
    oid = _org_id(current_user, org_id)
    cfg = get_o_crear_config(db, oid)
    return _config_dict(cfg)


@router.put("/config")
def put_config(
    body: ConfigIn,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin_accounting")),
):
    oid = _org_id(current_user, org_id)
    campos = [
        "aporte_jubilacion", "aporte_inssjp", "aporte_obra_social",
        "contrib_jubilacion", "contrib_inssjp", "contrib_obra_social",
        "contrib_asig_fam", "contrib_fondo_desempleo", "alicuota_art",
    ]
    for c in campos:
        v = getattr(body, c)
        if v < 0 or v > 1:
            raise HTTPException(422, f"{c} debe estar entre 0 y 1 (ej. 0.11 = 11%)")
    if body.minimo_no_imponible < 0:
        raise HTTPException(422, "minimo_no_imponible no puede ser negativo")
    if body.deduccion_especial < 0:
        raise HTTPException(422, "deduccion_especial no puede ser negativo")
    cfg = get_o_crear_config(db, oid)
    cfg.activo = body.activo
    for c in campos:
        setattr(cfg, c, Decimal(str(getattr(body, c))))
    cfg.ganancias_activo = body.ganancias_activo
    cfg.minimo_no_imponible = Decimal(str(body.minimo_no_imponible))
    cfg.deduccion_especial = Decimal(str(body.deduccion_especial))
    registrar_log(db, current_user.id, "sueldos_config", oid, "UPDATE", {"activo": body.activo})
    db.commit()
    db.refresh(cfg)
    return _config_dict(cfg)


# ── Escala de Ganancias 4ta categoría ──────────────────────────────
# NO viene sembrada con valores reales: la escala de AFIP/ARCA cambia
# varias veces por año. El admin_accounting debe cargar/actualizar los
# tramos vigentes antes de activar ganancias_activo en /sueldos/config.

@router.get("/escala-ganancias")
def listar_escala_ganancias(
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("view_accounting")),
):
    oid = _org_id(current_user, org_id)
    items = (
        db.query(EscalaGanancias)
        .filter(EscalaGanancias.organizacion_id == oid)
        .order_by(EscalaGanancias.tramo_desde.asc())
        .all()
    )
    return {"items": [_escala_dict(t) for t in items], "total": len(items)}


@router.post("/escala-ganancias")
def crear_tramo_ganancias(
    body: EscalaTramoIn,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin_accounting")),
):
    oid = _org_id(current_user, org_id)
    if body.tramo_desde < 0:
        raise HTTPException(422, "tramo_desde no puede ser negativo")
    if body.tramo_hasta is not None and body.tramo_hasta <= body.tramo_desde:
        raise HTTPException(422, "tramo_hasta debe ser mayor que tramo_desde")
    if body.alicuota < 0 or body.alicuota > 1:
        raise HTTPException(422, "alicuota debe estar entre 0 y 1 (ej. 0.27 = 27%)")
    if body.monto_fijo < 0:
        raise HTTPException(422, "monto_fijo no puede ser negativo")
    t = EscalaGanancias(
        organizacion_id=oid,
        tramo_desde=Decimal(str(body.tramo_desde)),
        tramo_hasta=(Decimal(str(body.tramo_hasta)) if body.tramo_hasta is not None else None),
        alicuota=Decimal(str(body.alicuota)),
        monto_fijo=Decimal(str(body.monto_fijo)),
    )
    db.add(t)
    registrar_log(db, current_user.id, "sueldos_escala_ganancias", oid, "CREATE", {
        "tramo_desde": body.tramo_desde, "tramo_hasta": body.tramo_hasta,
    })
    db.commit()
    db.refresh(t)
    return _escala_dict(t)


@router.put("/escala-ganancias/{tramo_id}")
def editar_tramo_ganancias(
    tramo_id: int,
    body: EscalaTramoUpdateIn,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin_accounting")),
):
    oid = _org_id(current_user, org_id)
    t = (
        db.query(EscalaGanancias)
        .filter(EscalaGanancias.id == tramo_id, EscalaGanancias.organizacion_id == oid)
        .first()
    )
    if t is None:
        raise HTTPException(404, "Tramo no encontrado")
    if body.tramo_desde is not None:
        if body.tramo_desde < 0:
            raise HTTPException(422, "tramo_desde no puede ser negativo")
        t.tramo_desde = Decimal(str(body.tramo_desde))
    if body.limpiar_tramo_hasta:
        t.tramo_hasta = None
    elif body.tramo_hasta is not None:
        t.tramo_hasta = Decimal(str(body.tramo_hasta))
    if t.tramo_hasta is not None and Decimal(str(t.tramo_hasta)) <= Decimal(str(t.tramo_desde)):
        raise HTTPException(422, "tramo_hasta debe ser mayor que tramo_desde")
    if body.alicuota is not None:
        if body.alicuota < 0 or body.alicuota > 1:
            raise HTTPException(422, "alicuota debe estar entre 0 y 1 (ej. 0.27 = 27%)")
        t.alicuota = Decimal(str(body.alicuota))
    if body.monto_fijo is not None:
        if body.monto_fijo < 0:
            raise HTTPException(422, "monto_fijo no puede ser negativo")
        t.monto_fijo = Decimal(str(body.monto_fijo))
    registrar_log(db, current_user.id, "sueldos_escala_ganancias", t.id, "UPDATE", {})
    db.commit()
    db.refresh(t)
    return _escala_dict(t)


@router.delete("/escala-ganancias/{tramo_id}")
def borrar_tramo_ganancias(
    tramo_id: int,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin_accounting")),
):
    oid = _org_id(current_user, org_id)
    t = (
        db.query(EscalaGanancias)
        .filter(EscalaGanancias.id == tramo_id, EscalaGanancias.organizacion_id == oid)
        .first()
    )
    if t is None:
        raise HTTPException(404, "Tramo no encontrado")
    db.delete(t)
    registrar_log(db, current_user.id, "sueldos_escala_ganancias", tramo_id, "DELETE", {})
    db.commit()
    return {"ok": True}


# ── Liquidación ───────────────────────────────────────────────────

@router.get("/liquidacion")
def preview_liquidacion(
    periodo: str = Query(..., description="Período YYYY-MM"),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("view_accounting")),
):
    oid = _org_id(current_user, org_id)
    try:
        calc = calcular_liquidacion_periodo(db, oid, periodo)
    except SueldosServiceError as ex:
        raise HTTPException(400, str(ex))
    return calc


@router.post("/liquidacion/calcular")
def calcular_y_guardar(
    periodo: str = Query(..., description="Período YYYY-MM"),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage_finance")),
):
    oid = _org_id(current_user, org_id)
    try:
        liq = guardar_o_actualizar_liquidacion(db, oid, periodo)
    except SueldosServiceError as ex:
        raise HTTPException(400, str(ex))
    registrar_log(db, current_user.id, "sueldos_liquidacion", liq.id, "CALCULAR", {
        "periodo": periodo, "total_bruto": float(liq.total_bruto),
    })
    db.commit()
    return _liquidacion_dict(liq, incluir_detalle=True)


@router.post("/liquidacion/{liquidacion_id}/aprobar")
def aprobar(
    liquidacion_id: int,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage_finance")),
):
    oid = _org_id(current_user, org_id)
    try:
        liq = aprobar_liquidacion(db, oid, liquidacion_id, current_user.id)
    except SueldosServiceError as ex:
        raise HTTPException(400, str(ex))
    registrar_log(db, current_user.id, "sueldos_liquidacion", liq.id, "APROBAR", {"periodo": liq.periodo})
    db.commit()
    return _liquidacion_dict(liq, incluir_detalle=True)


@router.post("/liquidacion/{liquidacion_id}/marcar-presentada")
def marcar_liquidacion_presentada(
    liquidacion_id: int,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin_accounting")),
):
    oid = _org_id(current_user, org_id)
    try:
        liq = marcar_presentada(db, oid, liquidacion_id)
    except SueldosServiceError as ex:
        raise HTTPException(400, str(ex))
    registrar_log(db, current_user.id, "sueldos_liquidacion", liq.id, "PRESENTAR", {"periodo": liq.periodo})
    db.commit()
    return _liquidacion_dict(liq)


@router.get("/liquidacion/{liquidacion_id}/empleado/{empleado_id}/recibo-pdf")
def recibo_sueldo_pdf_endpoint(
    liquidacion_id: int,
    empleado_id: int,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("view_accounting")),
):
    """Recibo de sueldo en PDF de un empleado para un período ya liquidado.

    Liquidación interna de gestión — no reemplaza el recibo oficial de sueldo
    según la Ley de Contrato de Trabajo (Ley 20.744).
    """
    from fastapi.responses import StreamingResponse
    import io
    from app.services.pdf_export import recibo_sueldo_pdf

    oid = _org_id(current_user, org_id)
    liq = (
        db.query(LiquidacionSueldoPeriodo)
        .filter(
            LiquidacionSueldoPeriodo.id == liquidacion_id,
            LiquidacionSueldoPeriodo.organizacion_id == oid,
        )
        .first()
    )
    if not liq:
        raise HTTPException(404, "Liquidación no encontrada")

    det = next((x for x in liq.detalles if x.empleado_id == empleado_id), None)
    if not det:
        raise HTTPException(404, "El empleado no tiene detalle en esta liquidación")

    emp = (
        db.query(Empleado)
        .filter(Empleado.id == empleado_id, Empleado.organizacion_id == oid)
        .first()
    )
    if not emp:
        raise HTTPException(404, "Empleado no encontrado")

    empleado_dict = _empleado_dict(emp)
    empleado_dict["convenio_nombre"] = emp.convenio.nombre if emp.convenio else None
    empleado_dict["categoria_nombre"] = emp.categoria.nombre if emp.categoria else None

    detalle_dict = {
        "sueldo_bruto": det.sueldo_bruto,
        "sac_proporcional": det.sac_proporcional,
        "total_aportes": det.total_aportes,
        "total_contribuciones": det.total_contribuciones,
        "sueldo_neto": det.sueldo_neto,
        "retencion_ganancias": det.retencion_ganancias,
        "detalle_json": det.detalle_json,
    }

    pdf_bytes = recibo_sueldo_pdf(detalle_dict, empleado_dict, liq.periodo)
    nombre_safe = "".join(c for c in (emp.nombre or "empleado") if c.isalnum() or c in " _-").strip().replace(" ", "_")
    fname = f"recibo_{nombre_safe}_{liq.periodo}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@router.get("/liquidacion/{liquidacion_id}/exportar-sicoss")
def exportar_sicoss(
    liquidacion_id: int,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage_finance")),
):
    """Exporta la liquidación como archivo SICOSS (texto, ancho fijo).

    Formato de referencia — ver el docstring de app/services/sicoss_export.py
    para el detalle de qué columnas son confiables y cuáles son placeholder.
    Verificá contra la última especificación de AFIP/Mis Aplicaciones Web
    antes de importarlo: puede requerir ajustes.
    """
    from fastapi.responses import StreamingResponse
    import io
    from app.services.sicoss_export import generar_archivo_sicoss

    oid = _org_id(current_user, org_id)
    liq = (
        db.query(LiquidacionSueldoPeriodo)
        .filter(
            LiquidacionSueldoPeriodo.id == liquidacion_id,
            LiquidacionSueldoPeriodo.organizacion_id == oid,
        )
        .first()
    )
    if not liq:
        raise HTTPException(404, "Liquidación no encontrada")
    if liq.estado == "borrador":
        raise HTTPException(
            400,
            "La liquidación está en borrador. Aprobala antes de exportar el archivo SICOSS.",
        )

    contenido = generar_archivo_sicoss(db, oid, liq.periodo)
    fname = f"sicoss_{liq.periodo}.txt"
    return StreamingResponse(
        io.BytesIO(contenido),
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@router.get("/historial")
def historial(
    org_id: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("view_accounting")),
):
    oid = _org_id(current_user, org_id)
    q = (
        db.query(LiquidacionSueldoPeriodo)
        .filter(LiquidacionSueldoPeriodo.organizacion_id == oid)
        .order_by(LiquidacionSueldoPeriodo.periodo.desc(), LiquidacionSueldoPeriodo.id.desc())
    )
    total = q.count()
    items = q.offset(offset).limit(limit).all()
    return {"items": [_liquidacion_dict(p) for p in items], "total": total}
