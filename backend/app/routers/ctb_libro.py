"""Router contabilidad — Libro diario, asientos, reportes y herramientas de administración.

Rutas expuestas (bajo el prefix /contabilidad del router padre):
  GET    /asientos/gaps
  GET    /asientos
  GET    /asientos/exportar-contable
  GET    /export-config
  PUT    /export-config
  GET    /asientos/{asiento_id}
  GET    /libro-mayor
  GET    /sumas-saldo
  GET    /balance
  POST   /reset-y-rebuild
  POST   /corregir-asientos-banco
  GET    /control-banco
  POST   /asiento-manual
  PATCH  /asientos/{asiento_id}/fecha
  DELETE /asientos/{asiento_id}
  POST   /fix-fechas-utc
"""
import logging
import time
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user, require_permission
from app.models.contabilidad import Asiento, AsientoDetalle, PlanCuenta
from app.models.user import User
from app.services.tz import hoy_art
from .ctb_common import _org_id

router = APIRouter(tags=["contabilidad"])
logger = logging.getLogger(__name__)

# Cache TTL para reportes pesados (Sumas y Saldos + Balance): hacen un GROUP BY
# sobre todos los asientos de la org y se recalculan en cada carga del módulo
# Contabilidad. Rara vez cambian en < 60 s, y se invalidan explícitamente en
# cada mutación de asientos (ver _invalidar_reportes), con el TTL como respaldo.
# Mismo criterio ya usado para la cartera global (_cartera_cache).
_reportes_cache: dict[tuple, tuple[float, object]] = {}  # (oid, tipo, desde, hasta) → (ts, payload)
_REPORTES_TTL = 60  # segundos


def _reportes_get(oid: int, tipo: str, desde, hasta):
    hit = _reportes_cache.get((oid, tipo, desde, hasta))
    if hit and time.monotonic() - hit[0] < _REPORTES_TTL:
        return hit[1]
    return None


def _reportes_set(oid: int, tipo: str, desde, hasta, payload):
    _reportes_cache[(oid, tipo, desde, hasta)] = (time.monotonic(), payload)


def _invalidar_reportes(oid: int) -> None:
    """Limpia los caches derivados de asientos para una org tras una mutación:
    los reportes (sumas-saldo/balance) y la cartera global. Se llama después de
    cada commit que toca asientos en este router."""
    for k in [k for k in _reportes_cache if k[0] == oid]:
        _reportes_cache.pop(k, None)
    try:
        from app.routers.ctb_ctas_corrientes import _cartera_cache
        _cartera_cache.pop(oid, None)
    except Exception:
        pass


@router.get("/asientos/gaps")
def get_asientos_gaps(
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Devuelve los numero_asiento faltantes en la secuencia (solo superadmin/admin_accounting)."""
    oid = _org_id(current_user, org_id)
    rows = db.query(Asiento.numero_asiento).filter(
        Asiento.organizacion_id == oid,
        Asiento.numero_asiento.isnot(None)
    ).order_by(Asiento.numero_asiento).all()
    nums = [r[0] for r in rows]
    if not nums:
        return {"gaps": [], "total": 0, "max": 0, "count": 0}
    max_n = nums[-1]
    existing = set(nums)
    gaps = [n for n in range(1, max_n + 1) if n not in existing]
    return {
        "count": len(nums),
        "max": max_n,
        "gaps": gaps,
        "total_gaps": len(gaps),
    }


@router.get("/asientos")
def get_asientos(
    org_id: Optional[int] = Query(None),
    desde: Optional[str] = Query(None),
    hasta: Optional[str] = Query(None),
    modulo: Optional[str] = Query(None),
    cuenta_id: Optional[int] = Query(None),
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
    if cuenta_id:
        q = q.filter(Asiento.id.in_(
            db.query(AsientoDetalle.asiento_id).filter(AsientoDetalle.cuenta_id == cuenta_id)
        ))
    total = q.count()
    items = q.order_by(Asiento.numero_asiento.desc().nullslast(), Asiento.id.desc()).offset(skip).limit(limit).all()

    # Batch: cuentas involucradas por asiento (para mostrar en columna Cuenta)
    ids = [a.id for a in items]
    cuentas_por_asiento: dict[int, list[str]] = {a.id: [] for a in items}
    if ids:
        for det, pc in (
            db.query(AsientoDetalle, PlanCuenta)
            .join(PlanCuenta, AsientoDetalle.cuenta_id == PlanCuenta.id)
            .filter(AsientoDetalle.asiento_id.in_(ids))
            .all()
        ):
            cuentas_por_asiento[det.asiento_id].append(f"{pc.codigo} {pc.nombre}")

    return {
        "total": total,
        "items": [
            {
                "id": a.id,
                "numero_asiento": a.numero_asiento or a.id,
                "fecha": a.fecha,
                "descripcion": a.descripcion,
                "modulo": a.modulo,
                "referencia_id": a.referencia_id,
                "created_at": a.created_at,
                "cuentas": cuentas_por_asiento.get(a.id, []),
            }
            for a in items
        ],
    }


@router.get("/asientos/exportar-contable")
def exportar_asientos_contable(
    desde: Optional[str] = Query(None),
    hasta: Optional[str] = Query(None),
    formato: str = Query("csv", description="csv | tango | holistor | regisoft"),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("view_accounting")),
):
    """Exporta el libro diario en formato importable por software contable argentino."""
    from fastapi.responses import Response
    from app.services.export_contable import exportar_asientos

    if formato not in ("csv", "tango", "holistor", "regisoft"):
        raise HTTPException(400, f"Formato inválido: '{formato}'. Use csv, tango, holistor o regisoft.")

    oid = _org_id(current_user, org_id)
    # Leer config de export de la org
    from app.models.organizacion import Organizacion
    org = db.query(Organizacion).filter(Organizacion.id == oid).first()
    export_cfg: dict = {}
    if org and isinstance(org.configuracion, dict):
        export_cfg = {
            "separador": org.configuracion.get("export_separador", ","),
            "encoding": org.configuracion.get("export_encoding", "utf-8"),
            "formato_fecha": org.configuracion.get("export_formato_fecha", "DD/MM/YYYY"),
            "mapeo_cuentas_export": org.configuracion.get("mapeo_cuentas_export", {}),
        }

    try:
        content, filename, content_type, cuentas_sin_mapeo = exportar_asientos(
            db=db, org_id=oid, desde=desde, hasta=hasta,
            formato=formato, config=export_cfg,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error("exportar-asientos-contable error: %s", e)
        raise HTTPException(500, "Error al generar el archivo de exportación")

    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Access-Control-Expose-Headers": "Content-Disposition, X-Cuentas-Sin-Mapeo",
    }
    if cuentas_sin_mapeo:
        headers["X-Cuentas-Sin-Mapeo"] = ",".join(cuentas_sin_mapeo)

    return Response(content=content, media_type=content_type, headers=headers)


@router.get("/export-config")
def get_export_config(
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("view_accounting")),
):
    """Lee la configuración de export contable de la organización."""
    from app.models.organizacion import Organizacion

    oid = _org_id(current_user, org_id)
    org = db.query(Organizacion).filter(Organizacion.id == oid).first()
    cfg: dict = {}
    if org and isinstance(org.configuracion, dict):
        cfg = org.configuracion

    return {
        "separador": cfg.get("export_separador", ","),
        "encoding": cfg.get("export_encoding", "utf-8"),
        "formato_fecha": cfg.get("export_formato_fecha", "DD/MM/YYYY"),
        "formato_default": cfg.get("export_formato_default", "csv"),
        "mapeo_cuentas_export": cfg.get("mapeo_cuentas_export", {}),
    }


class ExportConfigBody(BaseModel):
    separador: Optional[str] = None
    encoding: Optional[str] = None
    formato_fecha: Optional[str] = None
    formato_default: Optional[str] = None
    mapeo_cuentas_export: Optional[dict] = None


@router.put("/export-config")
def put_export_config(
    body: ExportConfigBody,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin_accounting")),
):
    """Guarda preferencias de export contable en Organizacion.configuracion."""
    from app.models.organizacion import Organizacion

    oid = _org_id(current_user, org_id)
    org = db.query(Organizacion).filter(Organizacion.id == oid).first()
    if not org:
        raise HTTPException(404, "Organización no encontrada")

    cfg = dict(org.configuracion or {})

    if body.separador is not None:
        if body.separador not in (",", ";", "\t"):
            raise HTTPException(400, "Separador inválido. Use ',', ';' o '\\t'.")
        cfg["export_separador"] = body.separador
    if body.encoding is not None:
        if body.encoding not in ("utf-8", "latin-1"):
            raise HTTPException(400, "Encoding inválido. Use 'utf-8' o 'latin-1'.")
        cfg["export_encoding"] = body.encoding
    if body.formato_fecha is not None:
        if body.formato_fecha not in ("DD/MM/YYYY", "YYYY-MM-DD"):
            raise HTTPException(400, "Formato de fecha inválido. Use 'DD/MM/YYYY' o 'YYYY-MM-DD'.")
        cfg["export_formato_fecha"] = body.formato_fecha
    if body.formato_default is not None:
        if body.formato_default not in ("csv", "tango", "holistor", "regisoft"):
            raise HTTPException(400, "Formato inválido.")
        cfg["export_formato_default"] = body.formato_default
    if body.mapeo_cuentas_export is not None:
        # Validar que sea dict de str→str
        for k, v in body.mapeo_cuentas_export.items():
            if not isinstance(k, str) or not isinstance(v, str):
                raise HTTPException(400, "mapeo_cuentas_export debe ser un objeto con claves y valores de tipo texto.")
        cfg["mapeo_cuentas_export"] = body.mapeo_cuentas_export

    org.configuracion = cfg
    db.commit()
    return {"ok": True, "config": {
        "separador": cfg.get("export_separador", ","),
        "encoding": cfg.get("export_encoding", "utf-8"),
        "formato_fecha": cfg.get("export_formato_fecha", "DD/MM/YYYY"),
        "formato_default": cfg.get("export_formato_default", "csv"),
        "mapeo_cuentas_export": cfg.get("mapeo_cuentas_export", {}),
    }}


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
    if cuenta.organizacion_id != oid:
        raise HTTPException(403, "Cuenta no pertenece a la organización")

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
    # Decimal: debe/haber son Numeric(12,2) → Decimal (float + Decimal = TypeError).
    saldo = Decimal("0")
    for detalle, asiento in q.all():
        saldo += (detalle.debe or Decimal("0")) - (detalle.haber or Decimal("0"))
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

    cached = _reportes_get(oid, "sumas", desde, hasta)
    if cached is not None:
        return cached

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
        debe  = round(r.total_debe or 0,  2)
        haber = round(r.total_haber or 0, 2)
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
    _reportes_set(oid, "sumas", desde, hasta, rows)
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

    cached = _reportes_get(oid, "balance", desde, hasta)
    if cached is not None:
        return cached

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
        debe  = round(r.total_debe or 0,  2)
        haber = round(r.total_haber or 0, 2)
        totales[r.tipo] = {
            "total_debe":  debe,
            "total_haber": haber,
            "saldo":       round(debe - haber, 2),
        }

    activo    = totales.get("activo",    {}).get("saldo", 0)
    pasivo    = totales.get("pasivo",    {}).get("saldo", 0)
    resultado = totales.get("resultado", {}).get("saldo", 0)

    result = {
        "activo":    totales.get("activo",    {"total_debe": 0, "total_haber": 0, "saldo": 0}),
        "pasivo":    totales.get("pasivo",    {"total_debe": 0, "total_haber": 0, "saldo": 0}),
        "resultado": totales.get("resultado", {"total_debe": 0, "total_haber": 0, "saldo": 0}),
        "ecuacion_ok": round(activo, 2) == round(abs(pasivo) + abs(resultado), 2),
    }
    _reportes_set(oid, "balance", desde, hasta, result)
    return result


@router.post("/reset-y-rebuild")
def reset_y_rebuild_asientos(
    dry_run: bool = Query(True, description="True = solo muestra qué haría; False = ejecuta"),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """"Empezar limpio": borra y reconstruye desde los datos reales SOLO los
    asientos que sabe reconstruir (modelo de cuentas transitorias, oct 2026):
    - extracto_banco: un asiento por día del extracto principal (Banco Macro
      contra 2-1-1-1 / 2-1-1-2), solo extractos no borrados;
    - um_lote: un asiento por lote de UM importado (mismas cuentas);
    - reclasificación por planilla conciliada, un bucket por ORIGEN del
      movimiento (reclass_planilla_principal / um_reclass_planilla), siempre
      No identificado D / Cliente H por el NETO + la comisión aparte;
    más las versiones viejas de esos mismos módulos (extracto, um_mov, um_reclass,
    cc_inicial, reclass_planilla_extracto, planilla) y los reversos de todos.
    TODO lo demás (pagos/egresos y sus reversos, cheques, tarjetas, sueldos,
    liquidaciones, caja, ARCA, ajustes manuales…) se CONSERVA intacto. Al final
    renumera 1..N todos los asientos de la org por (fecha, id), incluidos los
    conservados. Idempotente. Solo superadmin. Una sola transacción.
    """
    if not current_user.is_superadmin:
        raise HTTPException(status_code=403, detail="Solo superadmin")

    from app.services.asientos_banco import plan_reconstruccion, reconstruir_asientos_banco
    from app.services.auditoria import registrar_log

    oid = _org_id(current_user, org_id)

    # Self-heal: garantiza las columnas que usa el rebuild aunque Render no haya
    # corrido el safety net de startup todavía (numero_asiento para renumerar,
    # movimientos_banco.asiento_id para marcar los movimientos registrados).
    for ddl in (
        "ALTER TABLE asientos ADD COLUMN IF NOT EXISTS numero_asiento INTEGER",
        "ALTER TABLE movimientos_banco ADD COLUMN IF NOT EXISTS asiento_id INTEGER",
    ):
        try:
            db.execute(text(ddl))
            db.commit()
        except Exception as _col_ex:
            db.rollback()
            logger.warning("reset-y-rebuild: no se pudo asegurar columna (%s): %s", ddl, _col_ex)

    plan = plan_reconstruccion(db, oid)
    if dry_run:
        return {"dry_run": True, **plan, "msg": "Ejecutá con dry_run=false para aplicar los cambios."}

    try:
        res = reconstruir_asientos_banco(db, oid, current_user.id)
        db.commit()
    except Exception as ex:
        db.rollback()
        logger.error("reset-y-rebuild error: %s", ex)
        raise HTTPException(status_code=500, detail=str(ex))
    _invalidar_reportes(oid)
    registrar_log(db, current_user.id, "asientos", 0, "RESET_Y_REBUILD", {
        "org_id": oid, "borrados": res["borrados"], "creados": res["creados"],
        "conservados": res["conservados"],
    })
    return {
        "dry_run": False,
        **res,
        "msg": (
            f"Libro Diario reconstruido: {res['creados']} asientos nuevos, {res['conservados']} "
            f"conservados, numerados del 1 al {res['total_libro']}."
        ),
    }


@router.post("/corregir-asientos-banco")
def corregir_asientos_banco_endpoint(
    dry_run: bool = Query(True, description="True = solo muestra qué haría (no guarda nada); False = ejecuta"),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Corrige el histórico al modelo de cuentas transitorias (oct 2026): reversa
    los asientos "extracto" viejos y las reclasificaciones que debitaron Pasivo
    Corriente 2-1-0-0, rehace esas reclasificaciones contra 2-1-1-1 y registra
    los movimientos del extracto principal que no tienen asiento. Nunca borra ni
    edita asientos existentes ni renumera. Idempotente. Solo superadmin, dry_run
    por defecto (el dry_run arma todo y hace rollback: no persiste nada).
    Detalle en services/asientos_banco.py::corregir_asientos_banco."""
    if not current_user.is_superadmin:
        raise HTTPException(status_code=403, detail="Solo superadmin")

    from app.services.asientos_banco import corregir_asientos_banco
    from app.services.auditoria import registrar_log

    oid = _org_id(current_user, org_id)
    try:
        res = corregir_asientos_banco(db, oid, current_user.id, dry_run=dry_run)
        if dry_run:
            return {**res, "msg": "Ejecutá con dry_run=false para aplicar la corrección."}
        db.commit()
    except HTTPException:
        raise
    except Exception as ex:
        db.rollback()
        logger.error("corregir-asientos-banco error (org %s): %s", oid, ex)
        raise HTTPException(status_code=500, detail=str(ex))
    _invalidar_reportes(oid)
    if not res["nada_que_corregir"]:
        registrar_log(db, current_user.id, "asientos", 0, "CORREGIR_ASIENTOS_BANCO", {
            "org_id": oid,
            "reversados": [a["id"] for a in res["a_reversar"]],
            "creados_por_modulo": res["a_crear_por_modulo"],
            "saldos_antes": res["saldos_antes"],
            "saldos_despues": res["saldos_despues"],
        })
    return {
        **res,
        "msg": (
            "Nada que corregir." if res["nada_que_corregir"]
            else f"Corrección aplicada: {len(res['a_crear'])} asientos nuevos ({len(res['a_reversar'])} reversos de asientos viejos)."
        ),
    }


@router.get("/control-banco")
def get_control_banco(
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("view_accounting")),
):
    """Control del banco: saldo de Banco Macro en el Libro vs. la suma de los
    movimientos de los extractos y el saldo del último extracto, más los saldos
    de las transitorias 2-1-1-1 (cobros a imputar) y 2-1-1-2 (pagos a imputar)."""
    from app.services.asientos_banco import control_banco

    return control_banco(db, _org_id(current_user, org_id))


# ── Ajuste manual del Libro Diario ──────────────────────────────────────────

class AsientoManualIn(BaseModel):
    cuenta_debe_id: int
    cuenta_haber_id: int
    monto: float
    fecha: str
    descripcion: str


@router.post("/asiento-manual")
def post_asiento_manual(
    body: AsientoManualIn,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin_accounting")),
):
    from decimal import Decimal, InvalidOperation
    from datetime import date as _date
    from app.services.motor_contable import registrar_ajuste_manual

    oid = _org_id(current_user, org_id)
    cuenta_debe = db.query(PlanCuenta).filter(PlanCuenta.id == body.cuenta_debe_id, PlanCuenta.organizacion_id == oid).first()
    cuenta_haber = db.query(PlanCuenta).filter(PlanCuenta.id == body.cuenta_haber_id, PlanCuenta.organizacion_id == oid).first()
    if not cuenta_debe or not cuenta_haber:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    if body.cuenta_debe_id == body.cuenta_haber_id:
        raise HTTPException(status_code=400, detail="Las cuentas Debe y Haber no pueden ser la misma")
    for c in (cuenta_debe, cuenta_haber):
        if db.query(PlanCuenta).filter(PlanCuenta.parent_id == c.id).first():
            raise HTTPException(status_code=400, detail=f"'{c.nombre}' no es cuenta hoja (tiene subcuentas)")
    try:
        monto = Decimal(str(body.monto))
    except InvalidOperation:
        raise HTTPException(status_code=400, detail="Monto inválido")
    if monto <= 0:
        raise HTTPException(status_code=400, detail="El monto debe ser mayor que cero")
    try:
        fecha = _date.fromisoformat(body.fecha)
    except ValueError:
        raise HTTPException(status_code=400, detail="Fecha inválida")
    try:
        asiento_id = registrar_ajuste_manual(
            db=db, org_id=oid, usuario_id=current_user.id,
            cuenta_debe_id=cuenta_debe.id, cuenta_haber_id=cuenta_haber.id,
            monto=monto, fecha=fecha,
            descripcion=body.descripcion.strip() or f"Ajuste manual: {cuenta_debe.nombre} / {cuenta_haber.nombre}",
        )
        db.commit()
        _invalidar_reportes(oid)
        return {"ok": True, "asiento_id": asiento_id}
    except Exception as ex:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(ex))


class PatchFechaBody(BaseModel):
    fecha: str  # YYYY-MM-DD

@router.patch("/asientos/{asiento_id}/fecha")
def patch_asiento_fecha(
    asiento_id: int,
    body: PatchFechaBody,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin_accounting")),
):
    """Editar la fecha de un asiento individual (solo superadmin)."""
    from datetime import date as _date
    oid = _org_id(current_user, org_id)
    a = db.query(Asiento).filter(Asiento.id == asiento_id, Asiento.organizacion_id == oid).first()
    if not a:
        raise HTTPException(404, "Asiento no encontrado")
    try:
        a.fecha = _date.fromisoformat(body.fecha)
    except ValueError:
        raise HTTPException(400, "Formato de fecha inválido (YYYY-MM-DD)")
    db.commit()
    _invalidar_reportes(oid)
    return {"ok": True, "id": a.id, "fecha": str(a.fecha)}


@router.delete("/asientos/{asiento_id}")
def delete_asiento_manual(
    asiento_id: int,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin_accounting")),
):
    from app.services.motor_contable import _next_numero_asiento

    oid = _org_id(current_user, org_id)
    asiento = db.query(Asiento).filter(Asiento.id == asiento_id, Asiento.organizacion_id == oid).first()
    if not asiento:
        raise HTTPException(status_code=404, detail="Asiento no encontrado")
    if asiento.modulo != "ajuste_manual":
        raise HTTPException(status_code=400, detail="Solo se pueden revertir asientos de ajuste manual")
    ya_reversado = db.query(Asiento).filter(
        Asiento.modulo == "ajuste_manual_reverso",
        Asiento.referencia_id == asiento_id,
        Asiento.organizacion_id == oid,
    ).first()
    if ya_reversado:
        raise HTTPException(status_code=400, detail="Este asiento ya fue revertido")
    lineas_orig = db.query(AsientoDetalle).filter(AsientoDetalle.asiento_id == asiento_id).all()
    try:
        reverso = Asiento(
            fecha=hoy_art(),
            descripcion=f"REVERSO #{asiento_id}: {asiento.descripcion or ''} — Revertido manualmente",
            modulo="ajuste_manual_reverso",
            referencia_id=asiento_id,
            organizacion_id=oid,
            usuario_id=current_user.id,
            numero_asiento=_next_numero_asiento(db, oid),
        )
        db.add(reverso)
        db.flush()
        for linea in lineas_orig:
            db.add(AsientoDetalle(asiento_id=reverso.id, cuenta_id=linea.cuenta_id, debe=linea.haber, haber=linea.debe))
        db.commit()
        _invalidar_reportes(oid)
        return {"ok": True, "reverso_id": reverso.id}
    except Exception as ex:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(ex))


# ── Diagnóstico y fix de fechas con timezone incorrecto ────────────────────────

@router.post("/fix-fechas-utc")
def fix_fechas_utc(
    dry_run: bool = Query(True),
    org_id: Optional[int] = Query(None),
    desde: Optional[str] = Query(None),
    hasta: Optional[str] = Query(None),
    modulo: Optional[str] = Query(None),
    direccion: str = Query("atrasar"),  # "atrasar" (−1 día) o "adelantar" (+1 día)
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin_accounting")),
):
    """
    Corrige fechas de asientos y egresos en un rango de fechas dado.
    direccion=atrasar  → resta 1 día (para registros UTC-creados 1 día adelantado)
    direccion=adelantar → suma 1 día (para registros ingresados con fecha de ayer por error)
    dry_run=true: solo muestra los afectados sin modificar nada.
    """
    from datetime import timedelta
    from app.models.egreso import Egreso

    oid = _org_id(current_user, org_id)
    delta = timedelta(days=1) if direccion == "adelantar" else timedelta(days=-1)

    a_q = db.query(Asiento).filter(Asiento.organizacion_id == oid)
    if desde:
        a_q = a_q.filter(Asiento.fecha >= desde)
    if hasta:
        a_q = a_q.filter(Asiento.fecha <= hasta)
    if modulo:
        a_q = a_q.filter(Asiento.modulo == modulo)
    asientos_q = a_q.all()

    try:
        e_q = db.query(Egreso).filter(Egreso.organizacion_id == oid)
        if desde:
            e_q = e_q.filter(Egreso.fecha >= desde)
        if hasta:
            e_q = e_q.filter(Egreso.fecha <= hasta)
        egresos_q = e_q.all()
    except Exception:
        egresos_q = []

    asientos_afectados = [
        {"id": a.id, "fecha_actual": str(a.fecha), "created_at_utc": str(a.created_at),
         "modulo": a.modulo, "descripcion": (a.descripcion or '')[:60]}
        for a in asientos_q
    ]
    egresos_afectados = [
        {"id": e.id, "fecha_actual": str(e.fecha), "created_at_utc": str(e.created_at),
         "descripcion": (e.descripcion or '')[:60]}
        for e in egresos_q
    ]

    if not dry_run:
        for a in asientos_q:
            if a.fecha:
                a.fecha = a.fecha + delta
        for e in egresos_q:
            if e.fecha:
                e.fecha = e.fecha + delta
        db.commit()
        _invalidar_reportes(oid)

    accion = "+1 día (adelantado)" if direccion == "adelantar" else "−1 día (atrasado)"
    return {
        "dry_run": dry_run,
        "direccion": direccion,
        "asientos_afectados": len(asientos_afectados),
        "egresos_afectados": len(egresos_afectados),
        "detalle_asientos": asientos_afectados,
        "detalle_egresos": egresos_afectados,
        "mensaje": (
            f"Solo conteo — no se modificó nada. ({len(asientos_afectados)} asientos + {len(egresos_afectados)} egresos en el rango)." if dry_run else
            f"Fechas corregidas {accion}: {len(asientos_afectados)} asientos + {len(egresos_afectados)} egresos."
        ),
    }
