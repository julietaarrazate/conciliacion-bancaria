import logging
from decimal import Decimal
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, selectinload
from typing import Optional
from datetime import date

logger = logging.getLogger(__name__)

from app.database import get_db
from app.models.caja import ArqueoDiario, DENOMINACIONES, denominaciones_vacias
from app.models.egreso import Egreso
from app.models.user import User
from app.middleware.auth import get_current_user, require_permission, can_switch_org
from app.services.arqueo import armar_arqueo_del_dia, buscar_arqueo, obtener_o_crear_arqueo
from app.services.tz import hoy_art

router = APIRouter(prefix="/caja", tags=["caja"])


def _org_id(user: User, org_id_param: Optional[int] = None) -> int:
    if can_switch_org(user, org_id_param) and org_id_param:
        return org_id_param
    return user.organizacion_id or 1


# ── Arqueo del día ────────────────────────────────────────────────────────────

@router.get("/arqueo/hoy")
def get_arqueo_hoy(
    fecha_str: Optional[str] = Query(None, description="YYYY-MM-DD, default hoy"),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Arqueo del día. Si todavía no existe NO se crea (un GET no escribe): devuelve el
    borrador con el saldo arrastrado del día anterior, con `id: null` y `guardado: false`.
    Se crea recién al guardar algo con `PUT /caja/arqueo/hoy` (o con un pago en efectivo)."""
    org_id = _org_id(current_user, org_id)
    fecha = date.fromisoformat(fecha_str) if fecha_str else hoy_art()

    arqueo = buscar_arqueo(db, org_id, fecha)
    if arqueo:
        return _arqueo_response(arqueo)
    borrador = armar_arqueo_del_dia(db, org_id, fecha, current_user.id)
    resp = _arqueo_response(borrador)
    resp["guardado"] = False
    return resp


@router.put("/arqueo/hoy")
def update_arqueo(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage_finance"))
):
    """Actualiza saldo inicial, pesos agregados, ingresos o denominaciones físicas del día.
    Si el arqueo del día todavía no existe, lo crea (el GET solo muestra el borrador)."""
    org_id = _org_id(current_user, payload.get("org_id"))
    fecha_str = payload.get("fecha")
    fecha = date.fromisoformat(fecha_str) if fecha_str else hoy_art()

    # Si el arqueo del día todavía no existe, se crea acá (con el saldo arrastrado del
    # día anterior): el GET ya no lo crea.
    arqueo = obtener_o_crear_arqueo(db, org_id, fecha, current_user.id)

    if "saldo_inicial" in payload:
        arqueo.saldo_inicial = Decimal(str(payload["saldo_inicial"]))
    if "pesos_agregados" in payload:
        arqueo.pesos_agregados = Decimal(str(payload["pesos_agregados"]))
    if "ingresos" in payload:
        arqueo.ingresos = Decimal(str(payload["ingresos"]))
    if "denominaciones" in payload:
        # Validar que solo tenga denominaciones conocidas
        dens = {str(d): int(payload["denominaciones"].get(str(d), 0)) for d in DENOMINACIONES}
        arqueo.denominaciones = dens
    if "notas" in payload:
        arqueo.notas = payload["notas"]

    pesos_nuevos = Decimal(str(payload.get("pesos_agregados", arqueo.pesos_agregados or 0)))
    db.commit()
    db.refresh(arqueo)

    # Motor contable — reposición de efectivo cuando se registran pesos_agregados
    # (fault-tolerant: el arqueo ya se guardó arriba; un fallo aquí no debe
    # bloquear la operación de caja, pero se reporta para que no quede silencioso)
    contabilidad_ok = True
    if "pesos_agregados" in payload and pesos_nuevos > 0:
        try:
            from app.services.motor_contable import registrar_ingreso_efectivo
            registrar_ingreso_efectivo(
                db=db,
                arqueo_id=arqueo.id,
                org_id=org_id,
                usuario_id=current_user.id,
                monto=pesos_nuevos,
                fecha=arqueo.fecha,
            )
        except Exception as _mc_ex:
            logger.error("motor_contable ingreso_efectivo falló (arqueo %s): %s", arqueo.id, _mc_ex)
            contabilidad_ok = False

    resp = _arqueo_response(arqueo)
    resp["contabilidad_ok"] = contabilidad_ok
    return resp


@router.get("/arqueo/historial")
def historial_arqueos(
    skip: int = 0,
    limit: int = 30,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    org_id = _org_id(current_user, org_id)
    # Egresos de todos los arqueos (y su cliente) en 2 queries en vez de 1-2 por arqueo.
    items = db.query(ArqueoDiario).filter(
        ArqueoDiario.organizacion_id == org_id
    ).options(
        selectinload(ArqueoDiario.egresos).joinedload(Egreso.cliente)
    ).order_by(ArqueoDiario.fecha.desc()).offset(skip).limit(limit).all()
    return [_arqueo_response(a) for a in items]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _arqueo_response(a: ArqueoDiario) -> dict:
    return {
        "id": a.id,
        "fecha": str(a.fecha),
        "saldo_inicial": a.saldo_inicial,
        "pesos_agregados": a.pesos_agregados or 0,
        "ingresos": a.ingresos or 0,
        "pagos_dia": a.pagos_dia,
        "caja_restante": a.caja_restante,
        "total_arqueo_fisico": a.total_arqueo_fisico,
        "cruce": round(a.cruce, 2),
        "denominaciones": a.denominaciones or denominaciones_vacias(),
        "cerrado": a.cerrado,
        "notas": a.notas,
        "egresos": [_egreso_min(eg) for eg in a.egresos],
        "guardado": True,
    }


def _egreso_min(eg) -> dict:
    """Resumen mínimo de un egreso en efectivo para mostrarlo en el arqueo."""
    return {
        "id": eg.id,
        "fecha": str(eg.fecha) if eg.fecha else None,
        "tipo": eg.tipo,
        "beneficiario": eg.beneficiario or (eg.cliente.nombre if eg.cliente else None),
        "cliente_nombre": eg.cliente.nombre if eg.cliente else None,
        "monto": eg.monto,
        "denominaciones_usadas": eg.denominaciones_usadas,
        "tiene_foto": bool(eg.foto_comprobante),
    }
