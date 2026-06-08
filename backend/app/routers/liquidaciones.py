from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from typing import Optional
from datetime import date, datetime
import io

from app.database import get_db
from app.models.liquidacion import Liquidacion, LiquidacionDetalle, CierrePeriodo
from app.models.planilla import Planilla, PlanillaRow
from app.models.cliente import Cliente
from app.models.organizacion import Organizacion
from app.models.user import User
from app.middleware.auth import get_current_user, require_permission, can_switch_org
from app.services.auditoria import registrar_log

router = APIRouter(prefix="/liquidaciones", tags=["liquidaciones"])


def _get_org_config(db: Session, org_id: int) -> dict:
    org = db.query(Organizacion).filter(Organizacion.id == org_id).first()
    return org.configuracion if org and org.configuracion else {}


def _liquidacion_for_user(db: Session, liq_id: int, current_user: User) -> Liquidacion:
    """Resuelve una liquidacion con aislamiento multi-tenant."""
    q = db.query(Liquidacion).filter(Liquidacion.id == liq_id)
    if not current_user.is_superadmin:
        q = q.filter(Liquidacion.organizacion_id == current_user.organizacion_id)
    liq = q.first()
    if not liq:
        raise HTTPException(404, "Liquidación no encontrada")
    return liq


def _comision_cliente(config: dict, cliente_nombre: str) -> Decimal:
    """Obtiene el % de comision para un cliente segun la config de la org."""
    comisiones = config.get("comisiones", {})
    por_cliente = comisiones.get("por_cliente", {})
    if cliente_nombre in por_cliente:
        return Decimal(str(por_cliente[cliente_nombre]))
    return Decimal(str(comisiones.get("porcentaje_default", 1.5)))


def _calcular_monto_y_comision(
    db: Session, org_id: int, cliente_id: int,
    desde: date, hasta: date,
    pct_fallback: Optional[Decimal] = None,
) -> tuple:
    """
    Returns (monto_total, comision_total, pct_efectivo).
    Priority: per-planilla % → pct_fallback → 0.
    Only includes planilla rows (TT). Cheques se liquidan por separado en su módulo.
    """
    from app.models.extracto import MovimientoBanco as MB

    cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()
    if not cliente:
        return Decimal("0"), Decimal("0"), Decimal("0")

    rows_q = db.query(PlanillaRow, Planilla).join(
        Planilla, PlanillaRow.planilla_id == Planilla.id
    ).filter(
        Planilla.organizacion_id == org_id,
        Planilla.cliente_id == cliente_id,
        Planilla.deleted_at.is_(None),
        PlanillaRow.status == "ok",
        or_(
            and_(
                PlanillaRow.fecha_acred.isnot(None),
                PlanillaRow.fecha_acred >= desde,
                PlanillaRow.fecha_acred <= hasta,
            ),
            and_(
                PlanillaRow.fecha_acred.is_(None),
                func.date(Planilla.fecha_carga) >= desde,
                func.date(Planilla.fecha_carga) <= hasta,
            ),
        )
    ).all()

    monto_total = Decimal("0")
    comision_total = Decimal("0")

    # Batch-fetch de movimientos — evita N+1 (una query IN en lugar de una por fila)
    mov_ids = {row.orden_movimiento_acreditado for row, _ in rows_q if row.orden_movimiento_acreditado}
    movs_map: dict = {}
    if mov_ids:
        movs_map = {m.id: m for m in db.query(MB).filter(MB.id.in_(mov_ids)).all()}

    for row, planilla in rows_q:
        if row.orden_movimiento_acreditado:
            mov = movs_map.get(row.orden_movimiento_acreditado)
            monto_fila = (mov.monto if mov else row.monto) or Decimal("0")
        else:
            monto_fila = row.monto or Decimal("0")

        pct = (
            Decimal(str(planilla.porcentaje_comision))
            if planilla.porcentaje_comision is not None
            else (pct_fallback or Decimal("0"))
        )
        monto_total += monto_fila
        comision_total += monto_fila * pct / 100

    pct_efectivo = (
        round(comision_total / monto_total * 100, 4) if monto_total > 0 else Decimal("0")
    )
    return round(monto_total, 2), round(comision_total, 2), pct_efectivo


# ── POST /liquidaciones/generar ───────────────────────────────────────────────

@router.post("/generar")
def generar_liquidacion(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("reconcile"))
):
    """
    Genera una liquidacion en estado borrador para el periodo indicado.
    Agrupa lo conciliado por cliente y calcula comisiones segun config de la org.
    """
    org_id = current_user.organizacion_id or 1
    config = _get_org_config(db, org_id)

    try:
        periodo_inicio = date.fromisoformat(payload["periodo_inicio"])
        periodo_fin    = date.fromisoformat(payload["periodo_fin"])
    except (KeyError, ValueError):
        raise HTTPException(400, "periodo_inicio y periodo_fin requeridos (YYYY-MM-DD)")

    # Verificar que no haya un cierre ya existente para este periodo
    cierre = db.query(CierrePeriodo).filter(
        CierrePeriodo.organizacion_id == org_id,
        CierrePeriodo.periodo_inicio == periodo_inicio,
        CierrePeriodo.periodo_fin == periodo_fin
    ).first()
    if cierre:
        raise HTTPException(400, "Ya existe un cierre para este período")

    # % fallback: form override solamente. Si la planilla no tiene % propio → 0.
    # NO se hereda el % del cliente (cada planilla debe tener su propio %).
    pct_form = payload.get("porcentaje_comision")
    pct_form = Decimal(str(pct_form)) if pct_form is not None else None

    # Obtener clientes activos de la org
    clientes = db.query(Cliente).filter(Cliente.organizacion_id == org_id).all()

    detalles = []
    total_conciliado = Decimal("0")
    total_comision   = Decimal("0")

    for cliente in clientes:
        # Si hay override del form, aplica a todos los ítems sin % propio.
        # Si no, los ítems sin % propio quedan en 0 (no se hereda del cliente).
        pct_fallback = pct_form if pct_form is not None else Decimal("0")

        monto, comision, pct_efectivo = _calcular_monto_y_comision(
            db, org_id, cliente.id, periodo_inicio, periodo_fin, pct_fallback
        )
        if monto == 0:
            continue

        neto = round(monto - comision, 2)

        detalles.append({
            "cliente_id": cliente.id,
            "cliente_nombre": cliente.nombre,
            "monto_conciliado": monto,
            "porcentaje_comision": pct_efectivo,
            "monto_comision": comision,
            "monto_neto": neto
        })
        total_conciliado += monto
        total_comision   += comision

    total_neto = round(total_conciliado - total_comision, 2)

    liq = Liquidacion(
        organizacion_id=org_id,
        periodo_inicio=periodo_inicio,
        periodo_fin=periodo_fin,
        estado="borrador",
        total_conciliado=round(total_conciliado, 2),
        total_comision=round(total_comision, 2),
        total_neto=total_neto,
        notas=payload.get("notas"),
        created_by=current_user.id
    )
    db.add(liq)
    db.flush()

    for d in detalles:
        db.add(LiquidacionDetalle(liquidacion_id=liq.id, **d))

    db.commit()
    db.refresh(liq)

    registrar_log(db, current_user.id, "liquidaciones", liq.id, "INSERT", {
        "periodo": f"{periodo_inicio} → {periodo_fin}",
        "total_conciliado": total_conciliado,
        "clientes": len(detalles)
    })

    return _liq_response(liq)


# ── GET /liquidaciones ────────────────────────────────────────────────────────

@router.get("")
def list_liquidaciones(
    estado: Optional[str] = Query(None),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    oid = org_id if can_switch_org(current_user, org_id) and org_id else (current_user.organizacion_id or 1)
    q = db.query(Liquidacion).filter(Liquidacion.organizacion_id == oid)
    if estado:
        q = q.filter(Liquidacion.estado == estado)
    items = q.order_by(Liquidacion.created_at.desc()).all()
    return [_liq_response(l) for l in items]


# ── GET /liquidaciones/{id} ───────────────────────────────────────────────────

@router.get("/{liq_id}")
def get_liquidacion(
    liq_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    liq = _liquidacion_for_user(db, liq_id, current_user)
    return _liq_detalle_response(liq)


# ── POST /liquidaciones/{id}/aprobar ─────────────────────────────────────────

@router.post("/{liq_id}/aprobar")
def aprobar_liquidacion(
    liq_id: int,
    payload: dict = {},
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage_users"))
):
    liq = _liquidacion_for_user(db, liq_id, current_user)
    if liq.estado != "borrador":
        raise HTTPException(400, f"Solo se puede aprobar en estado borrador (actual: {liq.estado})")

    liq.estado      = "aprobada"
    liq.aprobado_by = current_user.id
    liq.aprobado_at = datetime.utcnow()
    if payload.get("notas"):
        liq.notas = payload["notas"]
    db.commit()

    registrar_log(db, current_user.id, "liquidaciones", liq.id, "UPDATE",
                  {"estado": "aprobada", "periodo": f"{liq.periodo_inicio} → {liq.periodo_fin}"})

    return {"ok": True, "estado": "aprobada", "id": liq_id}


# ── POST /liquidaciones/{id}/marcar-pagada ────────────────────────────────────

@router.post("/{liq_id}/marcar-pagada")
def marcar_pagada(
    liq_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage_users"))
):
    liq = _liquidacion_for_user(db, liq_id, current_user)
    if liq.estado != "aprobada":
        raise HTTPException(400, "Solo se puede marcar como pagada una liquidación aprobada")
    liq.estado = "pagada"
    db.commit()
    registrar_log(db, current_user.id, "liquidaciones", liq.id, "UPDATE", {"estado": "pagada"})
    return {"ok": True, "estado": "pagada"}


# ── DELETE /liquidaciones/{id} ────────────────────────────────────────────────

@router.delete("/{liq_id}")
def eliminar_liquidacion(
    liq_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("delete_records"))
):
    """Elimina una liquidación en estado borrador. No se pueden borrar aprobadas ni pagadas."""
    liq = _liquidacion_for_user(db, liq_id, current_user)
    if liq.estado != "borrador":
        raise HTTPException(400, "Solo se pueden eliminar liquidaciones en estado borrador")
    db.query(LiquidacionDetalle).filter(LiquidacionDetalle.liquidacion_id == liq.id).delete()
    db.delete(liq)
    db.commit()
    return {"ok": True}

@router.get("/{liq_id}/exportar")
def exportar_liquidacion(
    liq_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    liq = _liquidacion_for_user(db, liq_id, current_user)

    # Revisiones manuales del periodo
    revisiones = db.query(
        PlanillaRow, Planilla
    ).join(Planilla, PlanillaRow.planilla_id == Planilla.id).filter(
        Planilla.organizacion_id == liq.organizacion_id,
        Planilla.fecha_carga >= datetime.combine(liq.periodo_inicio, datetime.min.time()),
        Planilla.fecha_carga <= datetime.combine(liq.periodo_fin, datetime.max.time()),
        PlanillaRow.comentario_revision.isnot(None)
    ).all()

    from app.services.excel_export import export_liquidacion_excel
    xlsx = export_liquidacion_excel(liq, revisiones)
    fname = f"liquidacion_{liq.periodo_inicio}_{liq.periodo_fin}.xlsx"
    return StreamingResponse(io.BytesIO(xlsx),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'})


# ── POST /periodos/cerrar ─────────────────────────────────────────────────────

@router.post("/periodos/cerrar")
def cerrar_periodo(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage_users"))
):
    """
    Cierra el período: valida que no haya EN_REVISION pendientes,
    genera la liquidación automáticamente y bloquea el período.
    """
    org_id = current_user.organizacion_id or 1
    config = _get_org_config(db, org_id)

    if not config.get("requiere_cierre_periodo", False):
        raise HTTPException(400, "Esta organización no tiene habilitado el cierre de período")

    try:
        periodo_inicio = date.fromisoformat(payload["periodo_inicio"])
        periodo_fin    = date.fromisoformat(payload["periodo_fin"])
    except (KeyError, ValueError):
        raise HTTPException(400, "periodo_inicio y periodo_fin requeridos (YYYY-MM-DD)")

    # Verificar que no haya EN_REVISION pendientes
    pendientes = db.query(PlanillaRow).join(
        Planilla, PlanillaRow.planilla_id == Planilla.id
    ).filter(
        Planilla.organizacion_id == org_id,
        Planilla.fecha_carga >= datetime.combine(periodo_inicio, datetime.min.time()),
        Planilla.fecha_carga <= datetime.combine(periodo_fin, datetime.max.time()),
        PlanillaRow.status == "EN_REVISION"
    ).count()

    if pendientes > 0:
        raise HTTPException(400,
            f"No se puede cerrar: hay {pendientes} filas EN_REVISION pendientes de resolver")

    # Generar liquidación automática
    liq_payload = {"periodo_inicio": str(periodo_inicio), "periodo_fin": str(periodo_fin),
                   "notas": f"Cierre automático del período"}
    liq_resp = generar_liquidacion(liq_payload, db, current_user)

    # Registrar cierre
    cierre = CierrePeriodo(
        organizacion_id=org_id,
        periodo_inicio=periodo_inicio,
        periodo_fin=periodo_fin,
        cerrado_by=current_user.id,
        liquidacion_id=liq_resp["id"]
    )
    db.add(cierre)
    db.commit()

    registrar_log(db, current_user.id, "cierres_periodo", cierre.id, "INSERT", {
        "periodo": f"{periodo_inicio} → {periodo_fin}",
        "liquidacion_id": liq_resp["id"]
    })

    return {"ok": True, "mensaje": f"Período cerrado. Liquidación #{liq_resp['id']} generada.",
            "liquidacion_id": liq_resp["id"]}


# ── GET /periodos/{periodo}/estado ────────────────────────────────────────────

@router.get("/periodos/{periodo_inicio}/{periodo_fin}/estado")
def estado_periodo(
    periodo_inicio: date,
    periodo_fin: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    org_id = current_user.organizacion_id or 1

    cerrado = db.query(CierrePeriodo).filter(
        CierrePeriodo.organizacion_id == org_id,
        CierrePeriodo.periodo_inicio == periodo_inicio,
        CierrePeriodo.periodo_fin == periodo_fin
    ).first()

    pendientes = db.query(PlanillaRow).join(
        Planilla, PlanillaRow.planilla_id == Planilla.id
    ).filter(
        Planilla.organizacion_id == org_id,
        Planilla.fecha_carga >= datetime.combine(periodo_inicio, datetime.min.time()),
        Planilla.fecha_carga <= datetime.combine(periodo_fin, datetime.max.time()),
        PlanillaRow.status == "EN_REVISION"
    ).count()

    return {
        "periodo": f"{periodo_inicio} → {periodo_fin}",
        "estado": "cerrado" if cerrado else "abierto",
        "puede_cerrarse": pendientes == 0 and not cerrado,
        "pendientes_revision": pendientes,
        "cerrado_at": cerrado.cerrado_at if cerrado else None,
        "liquidacion_id": cerrado.liquidacion_id if cerrado else None
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _liq_response(liq: Liquidacion) -> dict:
    return {
        "id": liq.id,
        "organizacion_id": liq.organizacion_id,
        "periodo_inicio": str(liq.periodo_inicio),
        "periodo_fin": str(liq.periodo_fin),
        "estado": liq.estado,
        "total_conciliado": liq.total_conciliado,
        "total_comision": liq.total_comision,
        "total_neto": liq.total_neto,
        "notas": liq.notas,
        "created_at": liq.created_at,
        "creador": liq.creador.full_name if liq.creador else None,
        "aprobador": liq.aprobador.full_name if liq.aprobador else None,
        "aprobado_at": liq.aprobado_at
    }


def _liq_detalle_response(liq: Liquidacion) -> dict:
    base = _liq_response(liq)
    base["detalles"] = [{
        "id": d.id,
        "cliente_id": d.cliente_id,
        "cliente_nombre": d.cliente_nombre,
        "monto_conciliado": d.monto_conciliado,
        "porcentaje_comision": d.porcentaje_comision,
        "monto_comision": d.monto_comision,
        "monto_neto": d.monto_neto,
        "observaciones": d.observaciones
    } for d in liq.detalles]
    return base
