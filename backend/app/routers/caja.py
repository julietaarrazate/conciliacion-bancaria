import logging
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date, datetime

logger = logging.getLogger(__name__)

from app.database import get_db
from app.models.caja import ArqueoDiario, OrdenDePago, DENOMINACIONES, denominaciones_vacias
from app.models.cliente import Cliente
from app.models.user import User
from app.middleware.auth import get_current_user
from app.services.auditoria import registrar_log

router = APIRouter(prefix="/caja", tags=["caja"])


def _org_id(user: User) -> int:
    return user.organizacion_id or 1


# ── Arqueo del día ────────────────────────────────────────────────────────────

@router.get("/arqueo/hoy")
def get_arqueo_hoy(
    fecha_str: Optional[str] = Query(None, description="YYYY-MM-DD, default hoy"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtiene o crea el arqueo del día. Si es nuevo, arrastra el saldo del día anterior."""
    org_id = _org_id(current_user)
    fecha = date.fromisoformat(fecha_str) if fecha_str else date.today()

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

        # Descontar denominaciones usadas en las OPs del día anterior
        if anterior:
            for op in anterior.ordenes:
                if op.denominaciones_usadas:
                    for den, cant in op.denominaciones_usadas.items():
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
    org_id = _org_id(current_user)
    fecha_str = payload.get("fecha")
    fecha = date.fromisoformat(fecha_str) if fecha_str else date.today()

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
            from zoneinfo import ZoneInfo
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    org_id = _org_id(current_user)
    items = db.query(ArqueoDiario).filter(
        ArqueoDiario.organizacion_id == org_id
    ).order_by(ArqueoDiario.fecha.desc()).offset(skip).limit(limit).all()
    return [_arqueo_response(a) for a in items]


# ── Órdenes de Pago ───────────────────────────────────────────────────────────

@router.post("/op/registrar")
def registrar_op(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Registra una OP pagada. Automáticamente:
    - Crea OrdenDePago con foto del comprobante
    - Asocia al arqueo del día
    - Descuenta denominaciones del arqueo físico
    - Registra en AuditoriaLog
    """
    org_id = _org_id(current_user)

    cliente_id = payload.get("cliente_id")
    beneficiario = payload.get("beneficiario", "").strip()
    importe = Decimal(str(payload.get("importe", 0)))
    foto = payload.get("foto_base64")  # base64 de la foto del comprobante
    dens_usadas = payload.get("denominaciones", {})  # {"20000": 2, "10000": 1}
    notas = payload.get("notas")

    cliente_nombre_libre = payload.get("cliente_nombre", "").strip()

    if not beneficiario or importe <= 0:
        raise HTTPException(400, "beneficiario e importe son requeridos")

    # Resolver cliente: por ID, por nombre libre, o crear si no existe
    cliente = None
    if cliente_id:
        try:
            cliente = db.query(Cliente).filter(Cliente.id == int(cliente_id)).first()
        except Exception:
            pass
    if not cliente and cliente_nombre_libre:
        cliente = db.query(Cliente).filter(
            Cliente.nombre == cliente_nombre_libre,
            Cliente.organizacion_id == org_id
        ).first()
        if not cliente:
            cliente = Cliente(nombre=cliente_nombre_libre, organizacion_id=org_id)
            db.add(cliente)
            db.flush()
    if not cliente:
        raise HTTPException(400, "Especifica cliente_id o cliente_nombre")

    # Obtener o crear arqueo del día
    fecha = date.today()
    arqueo = db.query(ArqueoDiario).filter(
        ArqueoDiario.organizacion_id == org_id,
        ArqueoDiario.fecha == fecha
    ).first()
    if not arqueo:
        arqueo = ArqueoDiario(
            organizacion_id=org_id, fecha=fecha,
            saldo_inicial=0, pesos_agregados=0, ingresos=0,
            denominaciones=denominaciones_vacias(),
            creado_por=current_user.id
        )
        db.add(arqueo)
        db.flush()

    # Descontar denominaciones del arqueo físico
    if dens_usadas:
        dens_actuales = dict(arqueo.denominaciones or denominaciones_vacias())
        for den_str, cant in dens_usadas.items():
            cant = int(cant)
            actual = int(dens_actuales.get(str(den_str), 0))
            dens_actuales[str(den_str)] = max(0, actual - cant)
        arqueo.denominaciones = dens_actuales

    # Crear la OP — usar el ID del cliente resuelto, no el del payload
    op = OrdenDePago(
        organizacion_id=org_id,
        cliente_id=cliente.id,
        arqueo_id=arqueo.id,
        fecha=fecha,
        beneficiario=beneficiario,
        importe=importe,
        foto_comprobante=foto,
        denominaciones_usadas={str(k): int(v) for k, v in dens_usadas.items()} if dens_usadas else None,
        notas=notas,
        creado_por=current_user.id
    )
    db.add(op)
    db.commit()
    db.refresh(op)
    db.refresh(arqueo)

    registrar_log(db, current_user.id, "ordenes_de_pago", op.id, "INSERT", {
        "cliente": cliente.nombre,
        "beneficiario": beneficiario,
        "importe": importe
    })

    # Motor contable — asiento automático (fault-tolerant)
    try:
        from app.services.motor_contable import registrar_op_pago
        registrar_op_pago(
            db=db,
            op_id=op.id,
            org_id=org_id,
            usuario_id=current_user.id,
            beneficiario=beneficiario,
            cliente_nombre=cliente.nombre,
            monto=importe,
            fecha=fecha,
        )
    except Exception as _mc_ex:
        logger.warning("motor_contable op_pago: %s", _mc_ex)

    return {
        "ok": True,
        "op_id": op.id,
        "arqueo": _arqueo_response(arqueo)
    }


@router.get("/op/historial")
def historial_ops(
    cliente_id: Optional[int] = Query(None),
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    org_id = _org_id(current_user)
    q = db.query(OrdenDePago).filter(OrdenDePago.organizacion_id == org_id)
    if cliente_id:
        q = q.filter(OrdenDePago.cliente_id == cliente_id)
    if desde:
        q = q.filter(OrdenDePago.fecha >= desde)
    if hasta:
        q = q.filter(OrdenDePago.fecha <= hasta)
    ops = q.order_by(OrdenDePago.fecha.desc(), OrdenDePago.id.desc()).offset(skip).limit(limit).all()
    return [_op_response(op, con_foto=False) for op in ops]


@router.get("/op/{op_id}/comprobante")
def get_comprobante(
    op_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retorna la foto del comprobante firmado en base64."""
    q = db.query(OrdenDePago).filter(OrdenDePago.id == op_id)
    if not current_user.is_superadmin:
        q = q.filter(OrdenDePago.organizacion_id == current_user.organizacion_id)
    op = q.first()
    if not op:
        raise HTTPException(404, "OP no encontrada")
    return {"op_id": op_id, "foto_base64": op.foto_comprobante}


@router.post("/op/{op_id}/compartir")
def marcar_compartido(
    op_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    op = db.query(OrdenDePago).filter(OrdenDePago.id == op_id).first()
    if not op:
        raise HTTPException(404, "OP no encontrada")
    op.compartido_whatsapp = True
    db.commit()
    return {"ok": True, "op_id": op_id, "compartido": True}


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
        "ordenes": [_op_response(op, con_foto=False) for op in a.ordenes]
    }


def _op_response(op: OrdenDePago, con_foto: bool = False) -> dict:
    return {
        "id": op.id,
        "fecha": str(op.fecha),
        "cliente_id": op.cliente_id,
        "cliente_nombre": op.cliente.nombre if op.cliente else None,
        "beneficiario": op.beneficiario,
        "importe": op.importe,
        "denominaciones_usadas": op.denominaciones_usadas,
        "compartido_whatsapp": op.compartido_whatsapp,
        "notas": op.notas,
        "foto_base64": op.foto_comprobante if con_foto else None,
        "tiene_foto": bool(op.foto_comprobante),
        "created_at": op.created_at
    }


@router.get("/op/exportar-eft")
def exportar_eft(
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Exporta el historial EFT en Excel (formato identico a la planilla manual)."""
    import io
    from fastapi.responses import StreamingResponse
    from app.services.excel_export import export_eft_historial

    org_id = _org_id(current_user)
    q = db.query(OrdenDePago).filter(OrdenDePago.organizacion_id == org_id)
    if desde:
        q = q.filter(OrdenDePago.fecha >= desde)
    if hasta:
        q = q.filter(OrdenDePago.fecha <= hasta)
    ops = q.order_by(OrdenDePago.fecha.asc(), OrdenDePago.id.asc()).all()

    data = [{"fecha": op.fecha, "cliente_nombre": op.cliente.nombre if op.cliente else "—",
              "importe": op.importe} for op in ops]

    desde_str = str(desde) if desde else "inicio"
    hasta_str = str(hasta) if hasta else str(date.today())
    periodo = f"{desde_str}_{hasta_str}"

    xlsx = export_eft_historial(data, periodo)
    fname = f"pago_eft_{periodo}.xlsx"

    return StreamingResponse(
        io.BytesIO(xlsx),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'}
    )
