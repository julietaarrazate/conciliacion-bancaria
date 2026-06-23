"""Endpoints de analisis y reportes ejecutivos.

Tres bloques:
- Dashboard (KPIs del mes con comparativa al mes anterior)
- Aging de clientes (saldo pendiente por cliente, agrupado por antiguedad)
- Estado de cuenta por cliente (vista detallada de un cliente)

Todos los endpoints filtran por organizacion_id del usuario logueado
(org principal por default; superadmin puede pasar otro con ?org_id=N).

Este router solo se ocupa de la capa HTTP (rutas, query params, permisos,
cache de transporte); todo el calculo/agregacion vive en
`app.services.reportes_service`.
"""

import time
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.cliente import Cliente
from app.models.planilla import Planilla
from app.models.user import User
from app.services import reportes_service as svc

router = APIRouter(prefix="/analisis", tags=["analisis"])

# Cache en memoria por proceso — reduce queries en endpoints de alta frecuencia.
# TTL corto (60s) para no mostrar datos muy viejos durante operaciones activas.
_cache: dict[str, tuple[dict, float]] = {}
_TTL = 60.0


def _cache_get(key: str):
    entry = _cache.get(key)
    if entry and time.monotonic() < entry[1]:
        return entry[0]
    return None


def _cache_set(key: str, value: dict) -> dict:
    _cache[key] = (value, time.monotonic() + _TTL)
    return value


@router.get("/dashboard")
def dashboard(
    periodo: str = Query("mes", description="hoy | semana | mes | rango"),
    anio: Optional[int] = Query(None),
    mes: Optional[int] = Query(None, ge=1, le=12),
    desde: Optional[date] = Query(None, description="Solo cuando periodo=rango: fecha inicio YYYY-MM-DD"),
    hasta: Optional[date] = Query(None, description="Solo cuando periodo=rango: fecha fin YYYY-MM-DD"),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Dashboard ejecutivo: KPIs del periodo elegido con comparativa al anterior."""
    organizacion_id = svc.resolver_org(current_user, org_id)
    if periodo not in ("hoy", "semana", "mes", "rango"):
        periodo = "mes"

    cache_key = f"dashboard:{organizacion_id}:{periodo}:{anio}:{mes}:{desde}:{hasta}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    result = svc.calcular_dashboard(db, organizacion_id, periodo, anio, mes, desde, hasta)
    return _cache_set(cache_key, result)


@router.get("/alertas")
def alertas(
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Alertas operativas del día: cheques urgentes/vencidos, filas atrasadas, movimientos sin asignar."""
    organizacion_id = svc.resolver_org(current_user, org_id)

    cache_key = f"alertas:{organizacion_id}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    result = svc.calcular_alertas(db, organizacion_id)
    return _cache_set(cache_key, result)


@router.get("/clientes-aging")
def clientes_aging(
    org_id: Optional[int] = Query(None),
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Saldo pendiente por cliente, agrupado por antiguedad (aging)."""
    organizacion_id = svc.resolver_org(current_user, org_id)
    return svc.calcular_clientes_aging(db, organizacion_id, limit, offset)


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

    return svc.calcular_estado_cuenta_cliente(db, cliente, desde, hasta)


@router.get("/evolucion")
def evolucion(
    meses: int = Query(6, ge=1, le=24, description="Cantidad de meses hacia atras"),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Evolucion mensual de conciliado vs pendiente para los ultimos N meses."""
    organizacion_id = svc.resolver_org(current_user, org_id)
    return svc.calcular_evolucion(db, organizacion_id, meses)


@router.get("/flujo-caja")
def flujo_caja(
    meses: int = Query(6, ge=1, le=24, description="Cantidad de meses hacia atras"),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Flujo de caja mensual: ingresos (banco), egresos (gastos + pagos) y neto."""
    organizacion_id = svc.resolver_org(current_user, org_id)
    return svc.calcular_flujo_caja(db, organizacion_id, meses)


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
    organizacion_id = svc.resolver_org(current_user, org_id)
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
    desde, hasta = svc.rango_mes(anio, mes)
    organizacion_id = svc.resolver_org(current_user, org_id)

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
