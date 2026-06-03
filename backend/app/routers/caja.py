import logging
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date, datetime

logger = logging.getLogger(__name__)

from app.database import get_db
from app.models.caja import ArqueoDiario, DENOMINACIONES, denominaciones_vacias
from app.models.user import User
from app.middleware.auth import get_current_user, can_switch_org
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
    """Obtiene o crea el arqueo del día. Si es nuevo, arrastra el saldo del día anterior."""
    org_id = _org_id(current_user, org_id)
    fecha = date.fromisoformat(fecha_str) if fecha_str else hoy_art()

    arqueo = db.query(ArqueoDiario).filter(
        ArqueoDiario.organizacion_id == org_id,
        ArqueoDiario.fecha == fecha
    ).first()

    if not arqueo:
        # Arrastrar saldo del día anterior
        anterior = db.query(ArqueoDiario).filter(
            ArqueoDiario.organizacion_id == org_id,
            ArqueoDiario.fecha < fecha
        ).order_by(ArqueoDiario.fecha.desc()).first()

        saldo_inicial = anterior.caja_restante if anterior else 0
        dens_iniciales = anterior.denominaciones.copy() if anterior and anterior.denominaciones else denominaciones_vacias()

        # Descontar denominaciones usadas en los egresos en efectivo del día anterior
        if anterior:
            for eg in anterior.egresos:
                if eg.denominaciones_usadas:
                    for den, cant in eg.denominaciones_usadas.items():
                        dens_iniciales[den] = max(0, int(dens_iniciales.get(den, 0)) - int(cant))

        arqueo = ArqueoDiario(
            organizacion_id=org_id,
            fecha=fecha,
            saldo_inicial=round(saldo_inicial, 2),
            pesos_agregados=0,
            ingresos=0,
            denominaciones=dens_iniciales,
            creado_por=current_user.id
        )
        db.add(arqueo)
        db.commit()
        db.refresh(arqueo)

    return _arqueo_response(arqueo)


@router.put("/arqueo/hoy")
def update_arqueo(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Actualiza saldo inicial, pesos agregados, ingresos o denominaciones físicas del día."""
    org_id = _org_id(current_user, payload.get("org_id"))
    fecha_str = payload.get("fecha")
    fecha = date.fromisoformat(fecha_str) if fecha_str else hoy_art()

    arqueo = db.query(ArqueoDiario).filter(
        ArqueoDiario.organizacion_id == org_id,
        ArqueoDiario.fecha == fecha
    ).first()
    if not arqueo:
        raise HTTPException(404, "Arqueo no encontrado. Llamar GET /caja/arqueo/hoy primero.")

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
            logger.warning("motor_contable ingreso_efectivo: %s", _mc_ex)

    return _arqueo_response(arqueo)


@router.get("/arqueo/historial")
def historial_arqueos(
    skip: int = 0,
    limit: int = 30,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    org_id = _org_id(current_user, org_id)
    items = db.query(ArqueoDiario).filter(
        ArqueoDiario.organizacion_id == org_id
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
