"""Módulo unificado de Pagos (egresos).
Reemplaza Órdenes de Pago + Pagos + Gastos en un solo flujo:
  - tipo: proveedor | gasto | pago_cliente
  - forma_pago: banco | efectivo (efectivo descuenta del arqueo de caja)
  - foto del comprobante + compartir por WhatsApp
  - categorías editables por el usuario
"""
import logging
from datetime import date
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy import and_
from sqlalchemy.orm import Session, defer, joinedload
from slowapi import Limiter
from app.services.limites import ip_cliente

from app.database import get_db
from app.middleware.auth import get_current_user, require_permission, can_switch_org
from app.models.user import User
from app.models.cliente import Cliente
from app.models.egreso import Egreso, CategoriaEgreso, TIPOS_EGRESO, FORMAS_PAGO
from app.models.caja import ArqueoDiario, denominaciones_vacias
from app.services.auditoria import registrar_log
from app.services.proveedores import ProveedorInvalido, validar_para_egreso
from app.services.movimiento_egreso import (
    VinculoInvalido, buscar_movimiento, candidatos_para_movimiento, validar_vinculo,
)
from app.services.storage import upload_comprobante
from app.services.tz import hoy_art

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pagos", tags=["pagos"])
limiter = Limiter(key_func=ip_cliente)


def _org_id(user: User, org_id_param: Optional[int] = None) -> int:
    if can_switch_org(user, org_id_param) and org_id_param:
        return org_id_param
    return user.organizacion_id or 1


def _egreso_dict(e: Egreso, con_foto: bool = False, tiene_foto: Optional[bool] = None) -> dict:
    """`tiene_foto` precalculado en SQL (listado) evita cargar la foto base64 de cada
    egreso solo para saber si existe; si no viene, se deriva de la columna."""
    return {
        "id":               e.id,
        "organizacion_id":  e.organizacion_id,
        "tipo":             e.tipo,
        "categoria":        e.categoria,
        "forma_pago":       e.forma_pago,
        "monto":            e.monto,
        "fecha":            str(e.fecha) if e.fecha else None,
        "beneficiario":     e.beneficiario,
        "cliente_id":       e.cliente_id,
        "cliente_nombre":   e.cliente.nombre if e.cliente else None,
        "proveedor_id":     e.proveedor_id,
        "proveedor_nombre": e.proveedor.razon_social if e.proveedor else None,
        "concepto":         e.concepto,
        "referencia":       e.referencia,
        "compartido_whatsapp": e.compartido_whatsapp,
        "denominaciones_usadas": e.denominaciones_usadas,
        "tiene_foto":       bool(e.foto_comprobante) if tiene_foto is None else bool(tiene_foto),
        "foto_base64":      e.foto_comprobante if con_foto else None,
        "notas":            e.notas,
        "movimiento_banco_id": e.movimiento_banco_id,
        "created_at":       e.created_at,
    }


# ── Egresos ──────────────────────────────────────────────────────────

@router.get("")
def listar_egresos(
    tipo: Optional[str] = Query(None),
    forma_pago: Optional[str] = Query(None),
    cliente_id: Optional[int] = Query(None),
    categoria: Optional[str] = Query(None),
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
    skip: int = 0,
    limit: int = 100,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    oid = _org_id(current_user, org_id)
    q = db.query(Egreso).filter(Egreso.organizacion_id == oid)
    if tipo:
        q = q.filter(Egreso.tipo == tipo)
    if forma_pago:
        q = q.filter(Egreso.forma_pago == forma_pago)
    if cliente_id:
        q = q.filter(Egreso.cliente_id == cliente_id)
    if categoria:
        q = q.filter(Egreso.categoria == categoria)
    if desde:
        q = q.filter(Egreso.fecha >= desde)
    if hasta:
        q = q.filter(Egreso.fecha <= hasta)
    total = q.count()
    # cliente/proveedor en el mismo SELECT (antes: 1 query lazy por egreso → N+1).
    # La foto (base64 de cientos de KB sin R2) no se trae: solo si existe, en SQL.
    tiene_foto = and_(Egreso.foto_comprobante.isnot(None), Egreso.foto_comprobante != "")
    items = (
        q.with_entities(Egreso, tiene_foto)
        .options(joinedload(Egreso.cliente), joinedload(Egreso.proveedor), defer(Egreso.foto_comprobante))
        .order_by(Egreso.fecha.desc(), Egreso.id.desc()).offset(skip).limit(limit).all()
    )
    return {"total": total, "items": [_egreso_dict(e, tiene_foto=tf) for e, tf in items]}


@router.post("")
@limiter.limit("30/minute")
def crear_egreso(
    request: Request,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("reconcile")),
):
    """Crea un egreso. Si forma_pago=efectivo, descuenta del arqueo del día y
    lo asocia. Genera el asiento contable automático (fault-tolerant)."""
    oid = _org_id(current_user, payload.get("org_id"))

    tipo       = (payload.get("tipo") or "gasto").strip()
    forma_pago = (payload.get("forma_pago") or "banco").strip()
    if tipo not in TIPOS_EGRESO:
        raise HTTPException(400, f"tipo inválido: {tipo}")
    if forma_pago not in FORMAS_PAGO:
        raise HTTPException(400, f"forma_pago inválida: {forma_pago}")

    try:
        monto = Decimal(str(payload.get("monto", 0)))
    except Exception:
        raise HTTPException(400, "monto inválido")
    if monto <= 0:
        raise HTTPException(400, "El monto debe ser mayor a 0")

    fecha_str = payload.get("fecha")
    fecha = date.fromisoformat(fecha_str) if fecha_str else hoy_art()

    beneficiario = (payload.get("beneficiario") or "").strip() or None
    concepto     = (payload.get("concepto") or "").strip() or None
    categoria    = (payload.get("categoria") or "").strip() or None
    referencia   = (payload.get("referencia") or "").strip() or None
    notas        = payload.get("notas")
    dens_usadas  = payload.get("denominaciones") or {}

    # Resolver cliente (obligatorio si tipo=pago_cliente, opcional si no)
    cliente = None
    cliente_id = payload.get("cliente_id")
    cliente_nombre_libre = (payload.get("cliente_nombre") or "").strip()
    if cliente_id:
        try:
            cliente = db.query(Cliente).filter(
                Cliente.id == int(cliente_id), Cliente.organizacion_id == oid,
            ).first()
        except Exception:
            pass
    if not cliente and cliente_nombre_libre:
        nombre_norm = cliente_nombre_libre[:1].upper() + cliente_nombre_libre[1:]
        cliente = db.query(Cliente).filter(
            Cliente.nombre.ilike(nombre_norm),
            Cliente.organizacion_id == oid,
        ).first()
    if tipo == "pago_cliente" and not cliente:
        raise HTTPException(400, "Un pago a cliente requiere cliente_id o cliente_nombre")

    # Proveedor propio de la ficha (nunca en una OP por cuenta de un cliente)
    try:
        proveedor = validar_para_egreso(db, oid, tipo, payload.get("proveedor_id"))
    except ProveedorInvalido as ex:
        raise HTTPException(400, str(ex))
    if proveedor and not beneficiario:
        beneficiario = proveedor.razon_social

    # Resolver un pendiente del extracto: el egreso explica ese débito
    movimiento = None
    if payload.get("movimiento_banco_id") is not None:
        try:
            movimiento = validar_vinculo(db, payload["movimiento_banco_id"], oid, monto, forma_pago)
        except VinculoInvalido as ex:
            raise HTTPException(400, str(ex))

    # Foto del comprobante (S3/R2 con fallback base64)
    foto = upload_comprobante(payload.get("foto_base64"), prefix=f"egreso/{oid}")

    # Si es efectivo, engancha al arqueo del día y descuenta denominaciones
    arqueo = None
    if forma_pago == "efectivo":
        arqueo = db.query(ArqueoDiario).filter(
            ArqueoDiario.organizacion_id == oid,
            ArqueoDiario.fecha == fecha,
        ).first()
        if not arqueo:
            arqueo = ArqueoDiario(
                organizacion_id=oid, fecha=fecha,
                saldo_inicial=0, pesos_agregados=0, ingresos=0,
                denominaciones=denominaciones_vacias(),
                creado_por=current_user.id,
            )
            db.add(arqueo)
            db.flush()
        if dens_usadas:
            dens = dict(arqueo.denominaciones or denominaciones_vacias())
            for den_str, cant in dens_usadas.items():
                actual = int(dens.get(str(den_str), 0))
                dens[str(den_str)] = max(0, actual - int(cant))
            arqueo.denominaciones = dens

    egreso = Egreso(
        organizacion_id=oid,
        tipo=tipo,
        categoria=categoria,
        forma_pago=forma_pago,
        monto=monto,
        fecha=fecha,
        beneficiario=beneficiario,
        cliente_id=cliente.id if cliente else None,
        proveedor_id=proveedor.id if proveedor else None,
        concepto=concepto,
        referencia=referencia,
        foto_comprobante=foto,
        arqueo_id=arqueo.id if arqueo else None,
        denominaciones_usadas={str(k): int(v) for k, v in dens_usadas.items()} if (forma_pago == "efectivo" and dens_usadas) else None,
        notas=notas,
        movimiento_banco_id=movimiento.id if movimiento else None,
        usuario_id=current_user.id,
    )
    db.add(egreso)
    try:
        db.commit()
    except IntegrityError:
        # Dos "Resolver" simultáneos del mismo movimiento: el índice único frena el segundo
        db.rollback()
        if movimiento is not None:
            raise HTTPException(400, "El movimiento ya está explicado por otro pago")
        raise
    db.refresh(egreso)

    registrar_log(db, current_user.id, "egresos", egreso.id, "INSERT", {
        "tipo": tipo, "forma_pago": forma_pago,
        "beneficiario": beneficiario or (cliente.nombre if cliente else None),
        "monto": monto,
        "movimiento_banco_id": egreso.movimiento_banco_id,
    })

    # Motor contable — asiento automático (fault-tolerant: el egreso ya se
    # guardó arriba; un fallo aquí no debe bloquear el pago, pero se reporta
    # para que no quede silencioso)
    contabilidad_ok = True
    try:
        from app.services.motor_contable import registrar_egreso as _reg_egreso
        _reg_egreso(
            db=db, egreso_id=egreso.id, org_id=oid, usuario_id=current_user.id,
            tipo=tipo, forma_pago=forma_pago, monto=monto, fecha=fecha,
            beneficiario=beneficiario or "", concepto=concepto or "",
            cliente_id=cliente.id if cliente else None,
            cliente_nombre=cliente.nombre if cliente else "",
        )
    except Exception as _mc_ex:
        logger.error("motor_contable egreso falló (egreso %s): %s", egreso.id, _mc_ex)
        contabilidad_ok = False

    return {"ok": True, "egreso": _egreso_dict(egreso), "contabilidad_ok": contabilidad_ok}


@router.get("/candidatos-movimiento/{movimiento_id}")
def candidatos_movimiento(
    movimiento_id: int,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("reconcile")),
):
    """Pagos ya cargados que podrían explicar un débito del extracto (mismo
    importe, banco, sin vincular, fecha cercana). Para vincularlos en vez de
    crear uno nuevo y duplicar el pago."""
    oid = _org_id(current_user, org_id)
    mov = buscar_movimiento(db, movimiento_id, oid)
    if not mov:
        raise HTTPException(404, "Movimiento no encontrado")
    out = []
    for e in candidatos_para_movimiento(db, mov, oid):
        d = _egreso_dict(e)
        d["dias_diferencia"] = abs((e.fecha - mov.fecha).days) if (e.fecha and mov.fecha) else None
        out.append(d)
    return out


@router.post("/{egreso_id}/vincular-movimiento")
def vincular_movimiento(
    egreso_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("reconcile")),
):
    """Vincula un pago ya cargado al débito del extracto que lo explica.
    Solo guarda el vínculo: no reversa ni rehace el asiento (a diferencia del PATCH)."""
    q = db.query(Egreso).filter(Egreso.id == egreso_id)
    if not current_user.is_superadmin:
        q = q.filter(Egreso.organizacion_id == (current_user.organizacion_id or 1))
    e = q.first()
    if not e:
        raise HTTPException(404, "Egreso no encontrado")
    if payload.get("movimiento_banco_id") is None:
        raise HTTPException(400, "Falta movimiento_banco_id")
    try:
        mov = validar_vinculo(db, payload["movimiento_banco_id"], e.organizacion_id,
                              e.monto, e.forma_pago, egreso_id=e.id)
    except VinculoInvalido as ex:
        raise HTTPException(400, str(ex))
    e.movimiento_banco_id = mov.id
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(400, "El movimiento ya está explicado por otro pago")
    registrar_log(db, current_user.id, "egresos", e.id, "UPDATE", {"movimiento_banco_id": mov.id})
    return {"ok": True, "egreso": _egreso_dict(e)}


@router.get("/{egreso_id}/comprobante")
def get_comprobante(
    egreso_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(Egreso).filter(Egreso.id == egreso_id)
    if not current_user.is_superadmin:
        q = q.filter(Egreso.organizacion_id == (current_user.organizacion_id or 1))
    e = q.first()
    if not e:
        raise HTTPException(404, "Egreso no encontrado")
    return {"egreso_id": egreso_id, "foto_base64": e.foto_comprobante}


@router.post("/{egreso_id}/compartir")
def marcar_compartido(
    egreso_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("reconcile")),
):
    e = db.query(Egreso).filter(Egreso.id == egreso_id).first()
    if not e:
        raise HTTPException(404, "Egreso no encontrado")
    if not current_user.is_superadmin and e.organizacion_id != (current_user.organizacion_id or 1):
        raise HTTPException(403, "No autorizado")
    e.compartido_whatsapp = True
    db.commit()
    return {"ok": True, "egreso_id": egreso_id, "compartido": True}


@router.patch("/{egreso_id}")
def editar_egreso(
    egreso_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("reconcile")),
):
    """Edita campos básicos de un egreso (monto, fecha, beneficiario, concepto,
    referencia, categoria, forma_pago, foto_base64 — null para quitarla).
    Reversa el asiento original y genera uno nuevo con los valores corregidos."""
    q = db.query(Egreso).filter(Egreso.id == egreso_id)
    if not current_user.is_superadmin:
        q = q.filter(Egreso.organizacion_id == (current_user.organizacion_id or 1))
    e = q.first()
    if not e:
        raise HTTPException(404, "Egreso no encontrado")

    # Campos editables
    if "monto" in payload:
        try:
            nuevo_monto = Decimal(str(payload["monto"]))
        except Exception:
            raise HTTPException(400, "monto inválido")
        if nuevo_monto <= 0:
            raise HTTPException(400, "El monto debe ser mayor a 0")
        e.monto = nuevo_monto
    if "fecha" in payload and payload["fecha"]:
        try:
            e.fecha = date.fromisoformat(payload["fecha"])
        except Exception:
            raise HTTPException(400, "fecha inválida")
    if "beneficiario" in payload:
        e.beneficiario = (payload["beneficiario"] or "").strip() or None
    if "concepto" in payload:
        e.concepto = (payload["concepto"] or "").strip() or None
    if "referencia" in payload:
        e.referencia = (payload["referencia"] or "").strip() or None
    if "categoria" in payload:
        e.categoria = (payload["categoria"] or "").strip() or None
    if "proveedor_id" in payload:
        try:
            prov = validar_para_egreso(db, e.organizacion_id, e.tipo, payload["proveedor_id"])
        except ProveedorInvalido as ex:
            db.rollback()
            raise HTTPException(400, str(ex))
        e.proveedor_id = prov.id if prov else None
    if "foto_base64" in payload:
        nueva_foto = payload.get("foto_base64")
        e.foto_comprobante = upload_comprobante(nueva_foto, prefix=f"egreso/{e.organizacion_id}") if nueva_foto else None

    # Forma de pago (ej: se cargó "banco" y en realidad fue "efectivo"). Mismo
    # criterio que crear/eliminar: reponer denominaciones del arqueo viejo (si
    # había) y, si la nueva forma es efectivo, engancharlo al arqueo del día
    # (creándolo si no existe) para que cuente en "pagos_dia"/caja_restante.
    if "forma_pago" in payload or "denominaciones" in payload:
        nueva_forma_pago = (payload.get("forma_pago") or e.forma_pago).strip()
        if nueva_forma_pago not in FORMAS_PAGO:
            raise HTTPException(400, f"forma_pago inválida: {nueva_forma_pago}")

        if e.arqueo_id and e.denominaciones_usadas:
            arqueo_viejo = db.query(ArqueoDiario).filter(ArqueoDiario.id == e.arqueo_id).first()
            if arqueo_viejo:
                dens = dict(arqueo_viejo.denominaciones or denominaciones_vacias())
                for den_str, cant in e.denominaciones_usadas.items():
                    dens[str(den_str)] = int(dens.get(str(den_str), 0)) + int(cant)
                arqueo_viejo.denominaciones = dens
        e.arqueo_id = None
        e.denominaciones_usadas = None

        if nueva_forma_pago == "efectivo":
            dens_usadas = payload.get("denominaciones") or {}
            arqueo = db.query(ArqueoDiario).filter(
                ArqueoDiario.organizacion_id == e.organizacion_id,
                ArqueoDiario.fecha == e.fecha,
            ).first()
            if not arqueo:
                arqueo = ArqueoDiario(
                    organizacion_id=e.organizacion_id, fecha=e.fecha,
                    saldo_inicial=0, pesos_agregados=0, ingresos=0,
                    denominaciones=denominaciones_vacias(),
                    creado_por=current_user.id,
                )
                db.add(arqueo)
                db.flush()
            if dens_usadas:
                dens = dict(arqueo.denominaciones or denominaciones_vacias())
                for den_str, cant in dens_usadas.items():
                    actual = int(dens.get(str(den_str), 0))
                    dens[str(den_str)] = max(0, actual - int(cant))
                arqueo.denominaciones = dens
            e.arqueo_id = arqueo.id
            e.denominaciones_usadas = {str(k): int(v) for k, v in dens_usadas.items()} if dens_usadas else None

        e.forma_pago = nueva_forma_pago

    # Vínculo con el movimiento del extracto: null lo desvincula, un id lo
    # vincula. Si queda vinculado, el monto y la forma de pago tienen que seguir
    # coincidiendo con el movimiento (también al editar solo el monto).
    if "movimiento_banco_id" in payload:
        nuevo_mov = payload.get("movimiento_banco_id")
        e.movimiento_banco_id = None if nuevo_mov is None else nuevo_mov
    if e.movimiento_banco_id is not None:
        try:
            mov = validar_vinculo(db, e.movimiento_banco_id, e.organizacion_id,
                                  e.monto, e.forma_pago, egreso_id=e.id)
        except VinculoInvalido as ex:
            db.rollback()
            raise HTTPException(400, str(ex))
        e.movimiento_banco_id = mov.id

    # Reversar asiento anterior y crear uno nuevo con los valores corregidos
    try:
        from app.services.motor_contable import reversar_asientos, registrar_egreso as _reg_egreso
        reversar_asientos(
            db=db, modulo="egreso", referencia_id=e.id,
            org_id=e.organizacion_id, usuario_id=current_user.id,
            motivo="Edición de egreso",
        )
        cliente_nombre = e.cliente.nombre if e.cliente else ""
        _reg_egreso(
            db=db, egreso_id=e.id, org_id=e.organizacion_id, usuario_id=current_user.id,
            tipo=e.tipo, forma_pago=e.forma_pago, monto=e.monto, fecha=e.fecha,
            beneficiario=e.beneficiario or "",
            concepto=e.concepto or "",
            cliente_id=e.cliente_id,
            cliente_nombre=cliente_nombre,
        )
    except Exception as ex:
        logger.warning("asiento egreso edit %s: %s", e.id, ex)

    registrar_log(db, current_user.id, "egresos", e.id, "UPDATE", {
        "monto": str(e.monto), "fecha": str(e.fecha), "beneficiario": e.beneficiario,
        "forma_pago": e.forma_pago, "movimiento_banco_id": e.movimiento_banco_id,
    })
    db.commit()
    return {"ok": True, "egreso": _egreso_dict(e)}


@router.delete("/{egreso_id}")
@limiter.limit("30/minute")
def eliminar_egreso(
    request: Request,
    egreso_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("delete_records")),
):
    """Elimina un egreso. Reversa el asiento, repone denominaciones al arqueo
    (si era efectivo) y registra la baja en auditoría."""
    q = db.query(Egreso).filter(Egreso.id == egreso_id)
    if not current_user.is_superadmin:
        q = q.filter(Egreso.organizacion_id == (current_user.organizacion_id or 1))
    e = q.first()
    if not e:
        raise HTTPException(404, "Egreso no encontrado")

    org_id = e.organizacion_id

    # Reverso contable (deja original + reverso)
    try:
        from app.services.motor_contable import reversar_asientos
        reversar_asientos(
            db=db, modulo="egreso", referencia_id=e.id,
            org_id=org_id, usuario_id=current_user.id,
            motivo="Baja de egreso",
        )
    except Exception as ex:
        logger.warning("reversar_asientos egreso %s: %s", e.id, ex)

    # Reponer denominaciones físicas al arqueo (si era efectivo)
    arqueo = None
    if e.arqueo_id and e.denominaciones_usadas:
        arqueo = db.query(ArqueoDiario).filter(ArqueoDiario.id == e.arqueo_id).first()
        if arqueo:
            dens = dict(arqueo.denominaciones or denominaciones_vacias())
            for den_str, cant in e.denominaciones_usadas.items():
                dens[str(den_str)] = int(dens.get(str(den_str), 0)) + int(cant)
            arqueo.denominaciones = dens

    registrar_log(db, current_user.id, "egresos", e.id, "DELETE", {
        "tipo": e.tipo, "beneficiario": e.beneficiario, "monto": e.monto,
    })

    db.delete(e)
    db.commit()
    return {"ok": True, "egreso_id": egreso_id}


@router.get("/exportar")
def exportar_egresos(
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Exporta los egresos del período en Excel (formato EFT)."""
    import io
    from fastapi.responses import StreamingResponse
    from app.services.excel_export import export_eft_historial

    oid = _org_id(current_user, org_id)
    q = db.query(Egreso).filter(Egreso.organizacion_id == oid)
    if desde:
        q = q.filter(Egreso.fecha >= desde)
    if hasta:
        q = q.filter(Egreso.fecha <= hasta)
    egresos = q.order_by(Egreso.fecha.asc(), Egreso.id.asc()).all()

    data = [{
        "fecha": e.fecha,
        "cliente_nombre": (e.cliente.nombre if e.cliente else None) or e.beneficiario or "—",
        "importe": e.monto,
    } for e in egresos]

    desde_str = str(desde) if desde else "inicio"
    hasta_str = str(hasta) if hasta else str(hoy_art())
    periodo = f"{desde_str}_{hasta_str}"

    xlsx = export_eft_historial(data, periodo)
    fname = f"egresos_{periodo}.xlsx"
    return StreamingResponse(
        io.BytesIO(xlsx),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


# ── Categorías editables ──────────────────────────────────────────────

@router.get("/categorias")
def listar_categorias(
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    oid = _org_id(current_user, org_id)
    cats = (
        db.query(CategoriaEgreso)
        .filter(CategoriaEgreso.organizacion_id == oid, CategoriaEgreso.activo == True)
        .order_by(CategoriaEgreso.nombre.asc())
        .all()
    )
    return [{"id": c.id, "nombre": c.nombre} for c in cats]


@router.post("/categorias")
def crear_categoria(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("reconcile")),
):
    oid = _org_id(current_user, payload.get("org_id"))
    nombre = (payload.get("nombre") or "").strip()
    if not nombre:
        raise HTTPException(400, "El nombre es obligatorio")
    nombre = nombre[:1].upper() + nombre[1:]
    existe = (
        db.query(CategoriaEgreso)
        .filter(CategoriaEgreso.organizacion_id == oid,
                CategoriaEgreso.nombre.ilike(nombre))
        .first()
    )
    if existe:
        if not existe.activo:
            existe.activo = True
            db.commit()
        return {"id": existe.id, "nombre": existe.nombre}
    cat = CategoriaEgreso(organizacion_id=oid, nombre=nombre, activo=True)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return {"id": cat.id, "nombre": cat.nombre}


@router.delete("/categorias/{cat_id}")
def eliminar_categoria(
    cat_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("reconcile")),
):
    q = db.query(CategoriaEgreso).filter(CategoriaEgreso.id == cat_id)
    if not current_user.is_superadmin:
        q = q.filter(CategoriaEgreso.organizacion_id == (current_user.organizacion_id or 1))
    cat = q.first()
    if not cat:
        raise HTTPException(404, "Categoría no encontrada")
    cat.activo = False   # soft delete: no rompe egresos que la referencian por nombre
    db.commit()
    return {"ok": True, "cat_id": cat_id}
