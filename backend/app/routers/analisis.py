"""Endpoints de analisis y reportes ejecutivos.

Tres bloques:
- Dashboard (KPIs del mes con comparativa al mes anterior)
- Aging de clientes (saldo pendiente por cliente, agrupado por antiguedad)
- Estado de cuenta por cliente (vista detallada de un cliente)

Todos los endpoints filtran por organizacion_id del usuario logueado
(org principal por default; superadmin puede pasar otro con ?org_id=N).

Filosofia de los KPIs:
- "conciliado" = filas de planilla con status='ok'
- "pendiente" = filas con status != 'ok' y != 'duplicado'
- "antiguedad" = dias desde fecha_carga de la planilla
"""

import logging
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, and_, case, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.cheque import Cheque
from app.models.cliente import Cliente
from app.models.extracto import MovimientoBanco
from app.models.pago import Pago, Gasto
from app.models.planilla import Planilla, PlanillaRow
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analisis", tags=["analisis"])

# Status de PlanillaRow considerados "conciliados con exito"
_STATUS_OK = {"ok", "OK", "PAGO_PARCIAL", "CONCILIADO_CON_DIFERENCIA"}
# Status que cuentan como pendientes (no contamos "duplicado" ni vacios)
_STATUS_PENDIENTE = {"pendiente", "no está", "no esta", "faltan datos", "VENCIDO", "EN_REVISION"}


def _resolver_org(current_user: User, org_id_param: Optional[int]) -> int:
    """Si es superadmin permite override de org via query param; si no, usa la suya."""
    if org_id_param and current_user.is_superadmin:
        return org_id_param
    return current_user.organizacion_id or 1


def _rango_mes(anio: int, mes: int) -> tuple[date, date]:
    """Primer y ultimo dia del mes. mes: 1-12."""
    desde = date(anio, mes, 1)
    if mes == 12:
        hasta = date(anio + 1, 1, 1) - timedelta(days=1)
    else:
        hasta = date(anio, mes + 1, 1) - timedelta(days=1)
    return desde, hasta


def _suma_planilla_rows(
    db: Session,
    org_id: int,
    desde: date,
    hasta: date,
    solo_status: Optional[set[str]] = None,
    usar_fecha_acred: bool = False,
) -> dict:
    """Suma de monto y count de PlanillaRow.

    usar_fecha_acred=True: filtra por PlanillaRow.fecha_acred (cuando se acreditó).
    usar_fecha_acred=False: filtra por Planilla.fecha_carga (cuando se cargó).
    """
    q = (
        db.query(
            func.coalesce(func.sum(PlanillaRow.monto), 0.0).label("total"),
            func.count(PlanillaRow.id).label("cantidad"),
        )
        .join(Planilla, PlanillaRow.planilla_id == Planilla.id)
        .filter(
            Planilla.organizacion_id == org_id,
            Planilla.deleted_at.is_(None),
        )
    )
    if usar_fecha_acred:
        q = q.filter(
            PlanillaRow.fecha_acred >= desde,
            PlanillaRow.fecha_acred <= hasta,
        )
    else:
        q = q.filter(
            func.date(Planilla.fecha_carga) >= desde,
            func.date(Planilla.fecha_carga) <= hasta,
        )
    if solo_status:
        q = q.filter(PlanillaRow.status.in_(list(solo_status)))
    row = q.one()
    return {"total": row.total or 0, "cantidad": int(row.cantidad or 0)}


def _kpis_periodo(db: Session, org_id: int, desde: date, hasta: date) -> dict:
    """KPIs base de un periodo arbitrario. Se reutiliza para periodo actual y anterior."""
    # Conciliado: por fecha_acred (cuando Julieta marcó la acreditación)
    conciliado = _suma_planilla_rows(db, org_id, desde, hasta, _STATUS_OK, usar_fecha_acred=True)
    # Pendiente y total: por fecha_carga (planillas cargadas en el período)
    pendiente = _suma_planilla_rows(db, org_id, desde, hasta, _STATUS_PENDIENTE)
    todo = _suma_planilla_rows(db, org_id, desde, hasta, None)

    # Movimientos del banco del mes (por fecha del movimiento, no de la carga)
    mov_q = db.query(
        func.coalesce(func.sum(MovimientoBanco.monto), 0.0),
        func.count(MovimientoBanco.id),
    ).filter(
        MovimientoBanco.organizacion_id == org_id,
        MovimientoBanco.fecha >= desde,
        MovimientoBanco.fecha <= hasta,
    ).one()
    movimientos_banco = {"total": mov_q[0] or 0, "cantidad": int(mov_q[1] or 0)}

    # Cheques cargados en el mes (por fecha_emision)
    cheq_q = db.query(
        func.coalesce(func.sum(Cheque.monto), 0.0),
        func.count(Cheque.id),
    ).filter(
        Cheque.organizacion_id == org_id,
        Cheque.fecha_emision >= desde,
        Cheque.fecha_emision <= hasta,
    ).one()
    cheques_mes = {"total": cheq_q[0] or 0, "cantidad": int(cheq_q[1] or 0)}

    # Pagos y gastos del mes
    pag_q = db.query(func.coalesce(func.sum(Pago.monto), 0.0), func.count(Pago.id)).filter(
        Pago.organizacion_id == org_id, Pago.fecha >= desde, Pago.fecha <= hasta,
    ).one()
    gas_q = db.query(func.coalesce(func.sum(Gasto.monto), 0.0), func.count(Gasto.id)).filter(
        Gasto.organizacion_id == org_id, Gasto.fecha >= desde, Gasto.fecha <= hasta,
    ).one()

    # Tasa de conciliacion (% acreditado sobre el total reportado)
    total_reportado = todo["total"]
    tasa_conciliacion = (conciliado["total"] / total_reportado * 100) if total_reportado > 0 else 0.0

    return {
        "rango": {"desde": desde.isoformat(), "hasta": hasta.isoformat()},
        "conciliado": conciliado,
        "pendiente": pendiente,
        "total_reportado": todo,
        "tasa_conciliacion_pct": round(tasa_conciliacion, 1),
        "movimientos_banco": movimientos_banco,
        "cheques_cargados": cheques_mes,
        "pagos": {"total": pag_q[0] or 0, "cantidad": int(pag_q[1] or 0)},
        "gastos": {"total": gas_q[0] or 0, "cantidad": int(gas_q[1] or 0)},
    }


def _variacion_pct(actual: float, anterior: float) -> Optional[float]:
    """Retorna variacion % vs mes anterior. None si el anterior fue 0 (no se puede dividir)."""
    if anterior == 0:
        return None
    return round((actual - anterior) / anterior * 100, 1)


def _top_clientes_mes(db: Session, org_id: int, desde: date, hasta: date, limit: int = 5) -> list:
    """Top N clientes del mes por monto OK acreditado."""
    rows = (
        db.query(
            Cliente.id,
            Cliente.nombre,
            func.coalesce(func.sum(PlanillaRow.monto), 0.0).label("total"),
            func.count(PlanillaRow.id).label("cantidad"),
        )
        .join(Planilla, PlanillaRow.planilla_id == Planilla.id)
        .join(Cliente, Planilla.cliente_id == Cliente.id)
        .filter(
            Planilla.organizacion_id == org_id,
            Planilla.deleted_at.is_(None),
            PlanillaRow.status.in_(list(_STATUS_OK)),
            func.date(Planilla.fecha_carga) >= desde,
            func.date(Planilla.fecha_carga) <= hasta,
        )
        .group_by(Cliente.id, Cliente.nombre)
        .order_by(func.sum(PlanillaRow.monto).desc())
        .limit(limit)
        .all()
    )
    return [
        {"cliente_id": r.id, "nombre": r.nombre, "total": r.total or 0, "cantidad": int(r.cantidad or 0)}
        for r in rows
    ]


def _cheques_estado(db: Session, org_id: int) -> dict:
    """Resumen actual de cheques en cartera por estado."""
    rows = (
        db.query(
            Cheque.estado,
            func.coalesce(func.sum(Cheque.monto), 0.0).label("total"),
            func.count(Cheque.id).label("cantidad"),
        )
        .filter(Cheque.organizacion_id == org_id)
        .group_by(Cheque.estado)
        .all()
    )
    salida: dict = {}
    for r in rows:
        salida[(r.estado or "pendiente").lower()] = {
            "total": r.total or 0,
            "cantidad": int(r.cantidad or 0),
        }
    return salida


def _cheques_proximos_vencimiento(db: Session, org_id: int, dias: int = 30) -> list:
    """Cheques pendientes con fecha_deposito en los proximos N dias."""
    from zoneinfo import ZoneInfo
    hoy = datetime.now(ZoneInfo("America/Argentina/Buenos_Aires")).date()
    limite = hoy + timedelta(days=dias)
    cheques = (
        db.query(Cheque)
        .filter(
            Cheque.organizacion_id == org_id,
            Cheque.estado == "pendiente",
            Cheque.fecha_deposito.isnot(None),
            Cheque.fecha_deposito >= hoy,
            Cheque.fecha_deposito <= limite,
        )
        .order_by(Cheque.fecha_deposito.asc())
        .limit(20)
        .all()
    )
    return [
        {
            "id": c.id,
            "numero": c.numero,
            "monto": c.monto or 0,
            "fecha_deposito": c.fecha_deposito.isoformat() if c.fecha_deposito else None,
            "dias_para_vencer": (c.fecha_deposito - hoy).days if c.fecha_deposito else None,
            "cliente_nombre": c.cliente.nombre if c.cliente else None,
            "titular": c.titular,
            "banco_origen": c.banco_origen,
        }
        for c in cheques
    ]


def _calcular_rango(periodo: str, anio: Optional[int], mes: Optional[int]) -> tuple[date, date, date, date, str]:
    """Devuelve (desde, hasta, prev_desde, prev_hasta, label_periodo).

    Modos soportados:
    - "hoy": hoy vs ayer
    - "semana": ultimos 7 dias vs 7 dias previos
    - "mes" (default): mes seleccionado (o actual) vs mes anterior
    """
    from zoneinfo import ZoneInfo
    hoy = datetime.now(ZoneInfo("America/Argentina/Buenos_Aires")).date()
    if periodo == "hoy":
        return hoy, hoy, hoy - timedelta(days=1), hoy - timedelta(days=1), "Hoy"
    if periodo == "semana":
        desde = hoy - timedelta(days=6)
        prev_hasta = desde - timedelta(days=1)
        prev_desde = prev_hasta - timedelta(days=6)
        return desde, hoy, prev_desde, prev_hasta, "Últimos 7 días"
    # default: mes
    a = anio or hoy.year
    m = mes or hoy.month
    desde, hasta = _rango_mes(a, m)
    if m == 1:
        prev_desde, prev_hasta = _rango_mes(a - 1, 12)
    else:
        prev_desde, prev_hasta = _rango_mes(a, m - 1)
    return desde, hasta, prev_desde, prev_hasta, f"{m:02d}/{a}"


@router.get("/dashboard")
def dashboard(
    periodo: str = Query("mes", description="hoy | semana | mes (default: mes)"),
    anio: Optional[int] = Query(None, description="Solo cuando periodo=mes: anio (default: actual)"),
    mes: Optional[int] = Query(None, ge=1, le=12, description="Solo cuando periodo=mes: mes 1-12 (default: actual)"),
    org_id: Optional[int] = Query(None, description="Solo superadmin: filtrar otra org"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Dashboard ejecutivo: KPIs del periodo elegido con comparativa al anterior.

    `periodo` controla el rango:
    - hoy     -> hoy vs ayer
    - semana  -> ultimos 7 dias vs 7 dias previos
    - mes     -> mes elegido (o actual) vs mes anterior

    Incluye top clientes, cheques en cartera, cheques proximos a vencer.
    """
    organizacion_id = _resolver_org(current_user, org_id)
    if periodo not in ("hoy", "semana", "mes"):
        periodo = "mes"

    desde, hasta, prev_desde, prev_hasta, label = _calcular_rango(periodo, anio, mes)

    kpis_actual = _kpis_periodo(db, organizacion_id, desde, hasta)
    kpis_prev = _kpis_periodo(db, organizacion_id, prev_desde, prev_hasta)

    variaciones = {
        "conciliado_pct": _variacion_pct(kpis_actual["conciliado"]["total"], kpis_prev["conciliado"]["total"]),
        "pendiente_pct": _variacion_pct(kpis_actual["pendiente"]["total"], kpis_prev["pendiente"]["total"]),
        "movimientos_pct": _variacion_pct(kpis_actual["movimientos_banco"]["total"], kpis_prev["movimientos_banco"]["total"]),
        "cheques_pct": _variacion_pct(kpis_actual["cheques_cargados"]["total"], kpis_prev["cheques_cargados"]["total"]),
        "gastos_pct": _variacion_pct(kpis_actual["gastos"]["total"], kpis_prev["gastos"]["total"]),
    }

    top = _top_clientes_mes(db, organizacion_id, desde, hasta, limit=5)
    cheques_resumen = _cheques_estado(db, organizacion_id)
    cheques_vencen = _cheques_proximos_vencimiento(db, organizacion_id, dias=30)

    return {
        "organizacion_id": organizacion_id,
        "periodo": periodo,
        "periodo_label": label,
        "periodo_actual": kpis_actual,
        "periodo_anterior": kpis_prev,
        "variaciones": variaciones,
        "top_clientes": top,
        "cheques": {
            "resumen": cheques_resumen,
            "proximos_a_vencer": cheques_vencen,
        },
    }


@router.get("/alertas")
def alertas(
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Alertas operativas del día: cheques urgentes/vencidos, filas atrasadas, movimientos sin asignar."""
    organizacion_id = _resolver_org(current_user, org_id)
    from zoneinfo import ZoneInfo
    hoy = datetime.now(ZoneInfo("America/Argentina/Buenos_Aires")).date()

    cheques_urgentes = db.query(func.count(Cheque.id)).filter(
        Cheque.organizacion_id == organizacion_id,
        Cheque.estado == "pendiente",
        Cheque.fecha_deposito.isnot(None),
        Cheque.fecha_deposito >= hoy,
        Cheque.fecha_deposito <= hoy + timedelta(days=7),
    ).scalar() or 0

    cheques_vencidos = db.query(func.count(Cheque.id)).filter(
        Cheque.organizacion_id == organizacion_id,
        Cheque.estado == "pendiente",
        Cheque.fecha_deposito.isnot(None),
        Cheque.fecha_deposito < hoy,
    ).scalar() or 0

    filas_atrasadas = (
        db.query(func.count(PlanillaRow.id))
        .join(Planilla, PlanillaRow.planilla_id == Planilla.id)
        .filter(
            Planilla.organizacion_id == organizacion_id,
            Planilla.deleted_at.is_(None),
            PlanillaRow.status.in_(list(_STATUS_PENDIENTE)),
            func.date(Planilla.fecha_carga) < hoy - timedelta(days=30),
        )
        .scalar() or 0
    )

    # Solo cuento movimientos sin asignar de los ultimos 30 dias para no
    # arrastrar historico antiguo que infla el badge artificialmente.
    movimientos_sin_asignar = db.query(func.count(MovimientoBanco.id)).filter(
        MovimientoBanco.organizacion_id == organizacion_id,
        MovimientoBanco.fecha >= hoy - timedelta(days=30),
        or_(
            MovimientoBanco.cliente_acreditado.is_(None),
            MovimientoBanco.cliente_acreditado == "",
        ),
    ).scalar() or 0

    alertas_lista = []
    if cheques_urgentes:
        alertas_lista.append({
            "tipo": "cheques_urgentes",
            "cantidad": cheques_urgentes,
            "label": "Cheques vencen en 7 días",
            "urgencia": "alta",
            "link": "/cheques",
        })
    if cheques_vencidos:
        alertas_lista.append({
            "tipo": "cheques_vencidos",
            "cantidad": cheques_vencidos,
            "label": "Cheques vencidos",
            "urgencia": "alta",
            "link": "/cheques",
        })
    if filas_atrasadas:
        alertas_lista.append({
            "tipo": "filas_atrasadas",
            "cantidad": filas_atrasadas,
            "label": "Filas pendientes +30 días",
            "urgencia": "media",
            "link": "/historial",
        })
    if movimientos_sin_asignar:
        alertas_lista.append({
            "tipo": "movimientos_sin_asignar",
            "cantidad": movimientos_sin_asignar,
            "label": "Movimientos sin asignar",
            "urgencia": "baja",
            "link": "/movimientos",
        })

    # `total` para el badge de la campana: solo cuenta TIPOS de alerta
    # accionables (urgencia alta o media). De esta forma el numero del badge
    # refleja "cuantas cosas requieren atencion" y no se infla con cientos
    # de movimientos pendientes informativos.
    total_badge = sum(1 for a in alertas_lista if a["urgencia"] in ("alta", "media"))

    return {
        "organizacion_id": organizacion_id,
        "total": total_badge,
        "total_items": sum(a["cantidad"] for a in alertas_lista),
        "alertas": alertas_lista,
    }


def _calcular_aging_cliente(planilla_carga_date: date, hoy: date) -> str:
    """Asigna bucket de antiguedad a una fila pendiente."""
    dias = (hoy - planilla_carga_date).days
    if dias <= 30:
        return "0-30"
    if dias <= 60:
        return "31-60"
    if dias <= 90:
        return "61-90"
    return "+90"


@router.get("/clientes-aging")
def clientes_aging(
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Saldo pendiente por cliente, agrupado por antiguedad (aging).

    "Pendiente" = filas reportadas en planillas que aun no se conciliaron
    contra el banco. Se considera la antiguedad desde la fecha de carga
    de la planilla.

    Buckets: 0-30, 31-60, 61-90, +90 dias.
    """
    organizacion_id = _resolver_org(current_user, org_id)
    from zoneinfo import ZoneInfo
    hoy = datetime.now(ZoneInfo("America/Argentina/Buenos_Aires")).date()

    # Traer todas las filas pendientes con su planilla (joinedload implicito por la query)
    rows = (
        db.query(
            Cliente.id.label("cliente_id"),
            Cliente.nombre.label("cliente_nombre"),
            PlanillaRow.monto,
            Planilla.fecha_carga,
        )
        .join(Planilla, PlanillaRow.planilla_id == Planilla.id)
        .join(Cliente, Planilla.cliente_id == Cliente.id)
        .filter(
            Planilla.organizacion_id == organizacion_id,
            Planilla.deleted_at.is_(None),
            PlanillaRow.status.in_(list(_STATUS_PENDIENTE)),
        )
        .all()
    )

    # Agregar por cliente y bucket
    agregados: dict[int, dict] = {}
    for r in rows:
        if not r.fecha_carga:
            continue
        carga = r.fecha_carga.date() if hasattr(r.fecha_carga, "date") else r.fecha_carga
        bucket = _calcular_aging_cliente(carga, hoy)
        dias = (hoy - carga).days

        entry = agregados.setdefault(r.cliente_id, {
            "cliente_id": r.cliente_id,
            "nombre": r.cliente_nombre,
            "total_pendiente": 0,
            "cantidad": 0,
            "dias_max": 0,
            "buckets": {"0-30": 0, "31-60": 0, "61-90": 0, "+90": 0},
        })
        entry["total_pendiente"] += r.monto or 0
        entry["cantidad"] += 1
        entry["dias_max"] = max(entry["dias_max"], dias)
        entry["buckets"][bucket] += r.monto or 0

    # Cheques pendientes por cliente (suman al "pendiente operativo")
    cheques_pendientes = (
        db.query(
            Cliente.id.label("cliente_id"),
            Cliente.nombre.label("cliente_nombre"),
            func.coalesce(func.sum(Cheque.monto), 0.0).label("total"),
            func.count(Cheque.id).label("cantidad"),
        )
        .join(Cliente, Cheque.cliente_id == Cliente.id)
        .filter(
            Cheque.organizacion_id == organizacion_id,
            Cheque.estado == "pendiente",
        )
        .group_by(Cliente.id, Cliente.nombre)
        .all()
    )
    cheques_por_cliente = {
        c.cliente_id: {"total": c.total or 0, "cantidad": int(c.cantidad or 0)}
        for c in cheques_pendientes
    }

    # Asegurar que clientes con cheques pero sin filas tambien aparezcan
    for cid, info in cheques_por_cliente.items():
        if cid not in agregados:
            cliente = db.query(Cliente).filter(Cliente.id == cid).first()
            if cliente:
                agregados[cid] = {
                    "cliente_id": cid,
                    "nombre": cliente.nombre,
                    "total_pendiente": 0,
                    "cantidad": 0,
                    "dias_max": 0,
                    "buckets": {"0-30": 0, "31-60": 0, "61-90": 0, "+90": 0},
                }

    # Mergear cheques al total operativo
    salida = []
    for cid, data in agregados.items():
        cheques_info = cheques_por_cliente.get(cid, {"total": 0, "cantidad": 0})
        data["cheques_pendientes"] = cheques_info
        data["total_operativo"] = data["total_pendiente"] + cheques_info["total"]
        salida.append(data)

    # Ordenar por total operativo desc
    salida.sort(key=lambda x: x["total_operativo"], reverse=True)

    totales = {
        "total_pendiente_planillas": sum(d["total_pendiente"] for d in salida),
        "total_cheques_pendientes": sum(d["cheques_pendientes"]["total"] for d in salida),
        "total_operativo": sum(d["total_operativo"] for d in salida),
        "clientes_con_pendiente": len([d for d in salida if d["total_operativo"] > 0]),
    }

    return {
        "organizacion_id": organizacion_id,
        "generado_en": datetime.utcnow().isoformat(),
        "totales": totales,
        "clientes": salida,
    }


@router.get("/cliente/{cliente_id}/estado-cuenta")
def estado_cuenta_cliente(
    cliente_id: int,
    desde: Optional[date] = Query(None, description="ISO date; default: 90 dias atras"),
    hasta: Optional[date] = Query(None, description="ISO date; default: hoy"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Estado de cuenta detallado de un cliente.

    Incluye: planillas con filas, cheques (con estado), pagos hechos al cliente,
    saldo conciliado vs pendiente en el periodo.
    """
    organizacion_id = current_user.organizacion_id or 1
    if current_user.is_superadmin:
        # superadmin puede ver de cualquier org si pasa cliente de otra org
        cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()
    else:
        cliente = db.query(Cliente).filter(
            Cliente.id == cliente_id,
            Cliente.organizacion_id == organizacion_id,
        ).first()

    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    organizacion_id = cliente.organizacion_id or 1

    from zoneinfo import ZoneInfo
    hoy = datetime.now(ZoneInfo("America/Argentina/Buenos_Aires")).date()
    h = hasta or hoy
    d = desde or (h - timedelta(days=90))

    # Planillas del cliente en el periodo (con sus filas)
    planillas = (
        db.query(Planilla)
        .filter(
            Planilla.cliente_id == cliente_id,
            Planilla.deleted_at.is_(None),
            func.date(Planilla.fecha_carga) >= d,
            func.date(Planilla.fecha_carga) <= h,
        )
        .order_by(Planilla.fecha_carga.desc())
        .all()
    )

    planillas_data = []
    total_conciliado = 0
    total_pendiente = 0
    cantidad_filas = 0
    for p in planillas:
        filas_data = []
        sub_ok = 0
        sub_pendiente = 0
        for row in p.rows:
            estado_norm = "ok" if row.status in _STATUS_OK else (
                "pendiente" if row.status in _STATUS_PENDIENTE else (row.status or "otro")
            )
            if estado_norm == "ok":
                sub_ok += row.monto or 0
                total_conciliado += row.monto or 0
            elif estado_norm == "pendiente":
                sub_pendiente += row.monto or 0
                total_pendiente += row.monto or 0
            cantidad_filas += 1
            filas_data.append({
                "id": row.id,
                "monto": row.monto or 0,
                "status": row.status,
                "status_norm": estado_norm,
                "titular": row.titular,
                "cuit": row.cuit,
                "fecha_acred": row.fecha_acred.isoformat() if row.fecha_acred else None,
            })
        planillas_data.append({
            "id": p.id,
            "nombre_archivo": p.nombre_archivo,
            "fecha_carga": p.fecha_carga.isoformat() if p.fecha_carga else None,
            "dias_antiguedad": (hoy - p.fecha_carga.date()).days if p.fecha_carga else None,
            "filas": filas_data,
            "subtotal_ok": sub_ok,
            "subtotal_pendiente": sub_pendiente,
        })

    # Cheques del cliente en el periodo
    cheques = (
        db.query(Cheque)
        .filter(
            Cheque.cliente_id == cliente_id,
            Cheque.fecha_emision >= d,
            Cheque.fecha_emision <= h,
        )
        .order_by(Cheque.fecha_emision.desc())
        .all()
    )
    cheques_data = [
        {
            "id": c.id,
            "numero": c.numero,
            "banco_origen": c.banco_origen,
            "titular": c.titular,
            "monto": c.monto or 0,
            "fecha_emision": c.fecha_emision.isoformat() if c.fecha_emision else None,
            "fecha_deposito": c.fecha_deposito.isoformat() if c.fecha_deposito else None,
            "fecha_acred": c.fecha_acred.isoformat() if c.fecha_acred else None,
            "estado": c.estado,
        }
        for c in cheques
    ]
    cheques_pendientes_total = sum(c["monto"] for c in cheques_data if c["estado"] == "pendiente")
    cheques_acreditados_total = sum(c["monto"] for c in cheques_data if c["estado"] == "acreditado")
    cheques_rechazados_total = sum(c["monto"] for c in cheques_data if c["estado"] == "rechazado")

    # Pagos hechos al cliente en el periodo (egresos hacia el cliente)
    pagos = (
        db.query(Pago)
        .filter(
            Pago.cliente_id == cliente_id,
            Pago.organizacion_id == organizacion_id,
            Pago.fecha >= d,
            Pago.fecha <= h,
        )
        .order_by(Pago.fecha.desc())
        .all()
    )
    pagos_data = [
        {
            "id": p.id,
            "concepto": p.concepto,
            "monto": p.monto or 0,
            "medio": p.medio,
            "fecha": p.fecha.isoformat() if p.fecha else None,
        }
        for p in pagos
    ]
    pagos_total = sum(p["monto"] for p in pagos_data)

    # Comisión: usa % propio del cliente si lo tiene, si no el default de la org
    from app.models.organizacion import Organizacion as _Org
    org = db.query(_Org).filter(_Org.id == organizacion_id).first()
    org_cfg = (org.configuracion or {}) if org else {}
    pct_default = float(org_cfg.get("comisiones", {}).get("porcentaje_default", 1.5))
    porcentaje_comision = float(cliente.porcentaje_comision) if cliente.porcentaje_comision is not None else pct_default
    # total_conciliado puede ser Decimal (Numeric 12,2); convertir para no mezclar con float
    total_conciliado_f = float(total_conciliado)
    comision_monto = round(total_conciliado_f * porcentaje_comision / 100, 2)
    neto_calculado = round(total_conciliado_f - comision_monto, 2)

    return {
        "cliente": {
            "id": cliente.id,
            "nombre": cliente.nombre,
            "cuit": cliente.cuit,
            "organizacion_id": cliente.organizacion_id,
            "porcentaje_comision": porcentaje_comision,
        },
        "periodo": {"desde": d.isoformat(), "hasta": h.isoformat()},
        "resumen": {
            "conciliado_periodo": total_conciliado,
            "pendiente_periodo": total_pendiente,
            "cantidad_filas": cantidad_filas,
            "cantidad_planillas": len(planillas_data),
            "cheques_pendientes_monto": cheques_pendientes_total,
            "cheques_acreditados_monto": cheques_acreditados_total,
            "cheques_rechazados_monto": cheques_rechazados_total,
            "pagos_realizados_monto": pagos_total,
            "porcentaje_comision": porcentaje_comision,
            "comision_monto": comision_monto,
            "neto_calculado": neto_calculado,
        },
        "planillas": planillas_data,
        "cheques": cheques_data,
        "pagos": pagos_data,
    }


# ---------------------------------------------------------------------------
# Evolucion y Flujo de Caja
# ---------------------------------------------------------------------------

def _meses_atras(n: int) -> list[tuple[int, int]]:
    """Retorna lista de (anio, mes) para los ultimos N meses, de mas viejo a mas nuevo."""
    from zoneinfo import ZoneInfo
    hoy = datetime.now(ZoneInfo("America/Argentina/Buenos_Aires")).date()
    result = []
    a, m = hoy.year, hoy.month
    for _ in range(n):
        result.append((a, m))
        m -= 1
        if m == 0:
            m = 12
            a -= 1
    return list(reversed(result))


@router.get("/evolucion")
def evolucion(
    meses: int = Query(6, ge=1, le=24, description="Cantidad de meses hacia atras"),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Evolucion mensual de conciliado vs pendiente para los ultimos N meses.

    Util para el LineChart de tendencia en la pantalla de Flujo de Caja.
    Cada entrada: {label, anio, mes, conciliado, pendiente, tasa_pct}
    """
    organizacion_id = _resolver_org(current_user, org_id)
    periodos = _meses_atras(meses)
    resultado = []
    for a, m in periodos:
        desde, hasta = _rango_mes(a, m)
        conc = _suma_planilla_rows(db, organizacion_id, desde, hasta, _STATUS_OK)
        pend = _suma_planilla_rows(db, organizacion_id, desde, hasta, _STATUS_PENDIENTE)
        todo = _suma_planilla_rows(db, organizacion_id, desde, hasta, None)
        tasa = round(conc["total"] / todo["total"] * 100, 1) if todo["total"] > 0 else 0.0
        resultado.append({
            "label": f"{m:02d}/{str(a)[-2:]}",
            "anio": a,
            "mes": m,
            "conciliado": round(conc["total"], 2),
            "pendiente": round(pend["total"], 2),
            "tasa_pct": tasa,
        })
    return {"organizacion_id": organizacion_id, "meses": resultado}


@router.get("/flujo-caja")
def flujo_caja(
    meses: int = Query(6, ge=1, le=24, description="Cantidad de meses hacia atras"),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Flujo de caja mensual: ingresos (banco), egresos (gastos + pagos) y neto.

    Ingresos  = suma de MovimientoBanco del mes (dinero que entro al banco).
    Egresos   = suma de Gasto + suma de Pago del mes (salidas operativas).
    Neto      = ingresos - egresos.
    """
    organizacion_id = _resolver_org(current_user, org_id)
    periodos = _meses_atras(meses)
    resultado = []
    for a, m in periodos:
        desde, hasta = _rango_mes(a, m)
        ingresos_q = db.query(
            func.coalesce(func.sum(MovimientoBanco.monto), 0.0)
        ).filter(
            MovimientoBanco.organizacion_id == organizacion_id,
            MovimientoBanco.fecha >= desde,
            MovimientoBanco.fecha <= hasta,
        ).scalar() or 0.0
        gastos_q = db.query(
            func.coalesce(func.sum(Gasto.monto), 0.0)
        ).filter(
            Gasto.organizacion_id == organizacion_id,
            Gasto.fecha >= desde,
            Gasto.fecha <= hasta,
        ).scalar() or 0.0
        pagos_q = db.query(
            func.coalesce(func.sum(Pago.monto), 0.0)
        ).filter(
            Pago.organizacion_id == organizacion_id,
            Pago.fecha >= desde,
            Pago.fecha <= hasta,
        ).scalar() or 0.0
        ingresos = ingresos_q or 0
        egresos = (gastos_q or 0) + (pagos_q or 0)
        resultado.append({
            "label": f"{m:02d}/{str(a)[-2:]}",
            "anio": a,
            "mes": m,
            "ingresos": round(ingresos, 2),
            "egresos": round(egresos, 2),
            "neto": round(ingresos - egresos, 2),
        })
    return {"organizacion_id": organizacion_id, "meses": resultado}


# ---------------------------------------------------------------------------
# Exports PDF
# ---------------------------------------------------------------------------
from fastapi.responses import Response  # noqa: E402
from app.services.pdf_export import estado_cuenta_pdf, cierre_mensual_pdf  # noqa: E402
from app.models.organizacion import Organizacion  # noqa: E402


def _slugify_filename(s: str) -> str:
    import re
    base = re.sub(r"[^a-zA-Z0-9_-]+", "_", (s or "reporte")).strip("_")
    return base[:60] or "reporte"


@router.get("/cliente/{cliente_id}/estado-cuenta.pdf")
def estado_cuenta_cliente_pdf(
    cliente_id: int,
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Devuelve el estado de cuenta del cliente en PDF."""
    data = estado_cuenta_cliente(cliente_id, desde, hasta, db, current_user)
    pdf_bytes = estado_cuenta_pdf(data, generado_por=current_user.full_name or current_user.email)
    nombre = _slugify_filename(data["cliente"]["nombre"])
    desde_iso = data["periodo"]["desde"]
    hasta_iso = data["periodo"]["hasta"]
    filename = f"estado_cuenta_{nombre}_{desde_iso}_{hasta_iso}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/cierre/{anio}/{mes}.pdf")
def cierre_mensual_pdf_endpoint(
    anio: int,
    mes: int,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Devuelve el cierre mensual en PDF (mismos KPIs que /analisis/dashboard?periodo=mes)."""
    if not (1 <= mes <= 12):
        raise HTTPException(status_code=400, detail="mes debe estar entre 1 y 12")
    data = dashboard(periodo="mes", anio=anio, mes=mes, org_id=org_id, db=db, current_user=current_user)
    organizacion_id = _resolver_org(current_user, org_id)
    org = db.query(Organizacion).filter(Organizacion.id == organizacion_id).first()
    org_nombre = org.nombre if org else None
    pdf_bytes = cierre_mensual_pdf(
        data, anio, mes, org_nombre=org_nombre,
        generado_por=current_user.full_name or current_user.email,
    )
    org_slug = _slugify_filename(org_nombre or "org")
    filename = f"cierre_{anio}_{mes:02d}_{org_slug}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/cierre/{anio}/{mes}/export-xlsx")
def export_cierre_mensual_xlsx_endpoint(
    anio: int,
    mes: int,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Excel de cierre mensual: todas las planillas del mes, hoja resumen + una por cliente."""
    from sqlalchemy.orm import selectinload, joinedload as _joinedload
    from app.services.excel_export import export_cierre_mensual_xlsx
    from app.models.cliente import Cliente as ClienteModel  # noqa

    if not (1 <= mes <= 12):
        raise HTTPException(status_code=400, detail="mes debe estar entre 1 y 12")
    desde, hasta = _rango_mes(anio, mes)
    organizacion_id = _resolver_org(current_user, org_id)

    planillas = (
        db.query(Planilla)
        .options(selectinload(Planilla.rows), _joinedload(Planilla.cliente))
        .filter(
            Planilla.organizacion_id == organizacion_id,
            Planilla.deleted_at.is_(None),
            func.date(Planilla.fecha_carga) >= desde,
            func.date(Planilla.fecha_carga) <= hasta,
        )
        .order_by(Planilla.cliente_id, Planilla.fecha_carga)
        .all()
    )

    xlsx = export_cierre_mensual_xlsx(planillas, anio, mes)
    MESES = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
             'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
    filename = f"cierre_{anio}_{mes:02d}_{MESES[mes].lower()}.xlsx"
    return Response(
        content=xlsx,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
