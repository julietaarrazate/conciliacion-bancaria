"""
Motor contable — Fase 2.
Genera asientos automáticos cuando ocurren operaciones en el sistema.
Siempre encapsulado en try/except: si falla, la operación principal NO se revierte.
Idempotente: nunca crea dos asientos para el mismo (modulo, referencia_id, org_id).
"""

import logging
from datetime import date
from decimal import Decimal
from typing import Optional
from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.contabilidad import PlanCuenta, ReglaContable, Asiento, AsientoDetalle
from app.services.tz import hoy_art

logger = logging.getLogger(__name__)


def _get_regla(db: Session, evento: str, org_id: int) -> Optional[ReglaContable]:
    return (
        db.query(ReglaContable)
        .filter(
            ReglaContable.evento == evento,
            ReglaContable.organizacion_id == org_id,
            ReglaContable.activo == True,
        )
        .first()
    )


def _ya_existe(db: Session, modulo: str, referencia_id: int, org_id: int) -> bool:
    return (
        db.query(Asiento)
        .filter(
            Asiento.modulo == modulo,
            Asiento.referencia_id == referencia_id,
            Asiento.organizacion_id == org_id,
        )
        .first()
    ) is not None


def _next_numero_asiento(db: Session, org_id: int) -> int:
    """Devuelve el próximo numero_asiento correlativo para la org."""
    max_num = db.query(func.max(Asiento.numero_asiento)).filter(
        Asiento.organizacion_id == org_id
    ).scalar()
    return (max_num or 0) + 1


def _monto(v) -> Decimal:
    try:
        return round(Decimal(str(v).replace(",", ".").replace("$", "").strip()), 2)
    except Exception:
        return Decimal("0")


def _crear_asiento(
    db: Session,
    regla: ReglaContable,
    fecha: date,
    descripcion: str,
    modulo: str,
    referencia_id: int,
    org_id: int,
    usuario_id: Optional[int],
    monto: Decimal,
) -> None:
    a = Asiento(
        fecha=fecha,
        descripcion=descripcion,
        modulo=modulo,
        referencia_id=referencia_id,
        organizacion_id=org_id,
        usuario_id=usuario_id,
        numero_asiento=_next_numero_asiento(db, org_id),
    )
    db.add(a)
    try:
        db.flush()
    except IntegrityError:
        # Otro request creó el asiento en paralelo (race con unique constraint).
        # Salir limpio: el asiento ya existe gracias al otro request.
        db.rollback()
        return
    db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=regla.cuenta_debe_id,  debe=monto, haber=Decimal("0")))
    db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=regla.cuenta_haber_id, debe=Decimal("0"),  haber=monto))


def registrar_extracto(
    db: Session,
    extracto_id: int,
    org_id: int,
    usuario_id: Optional[int],
    nombre_archivo: str,
    movimientos,
) -> None:
    """Asiento al subir un extracto bancario: Banco (D) / Pasivo Corriente (H)."""
    try:
        if _ya_existe(db, "extracto", extracto_id, org_id):
            return
        regla = _get_regla(db, "carga_extracto", org_id)
        if not regla:
            return
        total = sum(abs(_monto(m.monto)) for m in movimientos)
        if total <= 0:
            return
        hoy = hoy_art()
        _crear_asiento(
            db=db,
            regla=regla,
            fecha=hoy,
            descripcion=f"Extracto: {nombre_archivo}",
            modulo="extracto",
            referencia_id=extracto_id,
            org_id=org_id,
            usuario_id=usuario_id,
            monto=total,
        )
        db.commit()
    except Exception as ex:
        db.rollback()
        logger.warning("Error asiento extracto %s: %s", extracto_id, ex)


def _crear_asiento_multilinea(
    db: Session,
    fecha: date,
    descripcion: str,
    modulo: str,
    referencia_id: int,
    org_id: int,
    usuario_id: Optional[int],
    lineas: list,  # [(cuenta_id, debe, haber), ...]
) -> None:
    """Crea un asiento con N líneas de detalle. lineas = [(cuenta_id, debe, haber)].
    Red de seguridad: si las líneas no cuadran en partida doble (Σdebe ≠ Σhaber)
    NO se postea el asiento — evita corromper el balance silenciosamente."""
    total_debe  = sum(_monto(d) for _, d, _h in lineas)
    total_haber = sum(_monto(h) for _, _d, h in lineas)
    if abs(total_debe - total_haber) > Decimal("0.01"):
        logger.error(
            "Asiento %s ref %s NO balancea (debe=%s haber=%s) — no se postea",
            modulo, referencia_id, total_debe, total_haber,
        )
        return
    a = Asiento(
        fecha=fecha,
        descripcion=descripcion,
        modulo=modulo,
        referencia_id=referencia_id,
        organizacion_id=org_id,
        usuario_id=usuario_id,
        numero_asiento=_next_numero_asiento(db, org_id),
    )
    db.add(a)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return
    for cuenta_id, debe, haber in lineas:
        db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=cuenta_id, debe=debe, haber=haber))


def registrar_cheque(
    db: Session,
    cheque_id: int,
    org_id: int,
    usuario_id: Optional[int],
    titular: str,
    monto: Decimal,
    comision: Decimal,
    fecha: date,
) -> None:
    """Registro cheque (nueva regla contador):
       Cheques en cartera (1-1-2-1) D  /  Cheques depositados (2-1-3-1) H (neto)
                                        /  Comisiones cheques (3-1-3-0) H (comisión)
    Reemplaza el esquema anterior (cheque_carga / cheque_comision)."""
    try:
        if _ya_existe(db, "cheque_registro", cheque_id, org_id):
            return
        monto    = round(_monto(monto), 2)
        comision = round(_monto(comision), 2)
        if monto <= 0:
            return
        neto = monto - comision
        if neto <= 0:
            logger.warning("Cheque %s: valor neto <= 0, se omite asiento", cheque_id)
            return

        cartera    = _get_cuenta_por_codigo(db, "1-1-2-1", org_id)
        depositados = _get_cuenta_por_codigo(db, "2-1-3-1", org_id)
        comisiones = _get_cuenta_por_codigo(db, "3-1-3-0", org_id)
        if not cartera or not depositados or not comisiones:
            logger.warning("Cuentas cheque no encontradas org %s (1-1-2-1/2-1-3-1/3-1-3-0)", org_id)
            return

        lineas = [
            (cartera.id,    monto,    Decimal("0")),
            (depositados.id, Decimal("0"), neto),
        ]
        if comision > 0:
            lineas.append((comisiones.id, Decimal("0"), comision))

        _crear_asiento_multilinea(
            db=db, fecha=fecha,
            descripcion=f"Cheque {titular or ''} — registro",
            modulo="cheque_registro",
            referencia_id=cheque_id,
            org_id=org_id,
            usuario_id=usuario_id,
            lineas=lineas,
        )
        db.commit()
    except Exception as ex:
        db.rollback()
        logger.warning("Error asiento cheque registro %s: %s", cheque_id, ex)


def acreditar_cheque(
    db: Session,
    cheque_id: int,
    org_id: int,
    usuario_id: Optional[int],
    titular: str,
    monto: Decimal,
    neto: Decimal,
    banco_cuenta_id: int,
    cliente_cuenta_id: int,
    fecha: date,
) -> None:
    """Acreditación cheque — 2 asientos (nueva regla contador):
    A1: Banco (D) / Cheques en cartera (H)  →  el dinero entra al banco
    A2: Cheques depositados (D) / Cliente (H) →  cancela pasivo tránsito y acredita al cliente"""
    try:
        monto = round(_monto(monto), 2)
        neto  = round(_monto(neto),  2)
        if monto <= 0:
            return

        cartera    = _get_cuenta_por_codigo(db, "1-1-2-1", org_id)
        depositados = _get_cuenta_por_codigo(db, "2-1-3-1", org_id)
        banco = db.query(PlanCuenta).filter(PlanCuenta.id == banco_cuenta_id).first()
        cliente_cuenta = db.query(PlanCuenta).filter(PlanCuenta.id == cliente_cuenta_id).first()

        if not cartera or not depositados or not banco or not cliente_cuenta:
            logger.warning("Cuentas acreditación cheque no encontradas org %s cheque %s", org_id, cheque_id)
            return

        # A1: Banco D / Cheques en cartera H
        if not _ya_existe(db, "cheque_acred_banco", cheque_id, org_id):
            _crear_asiento_directo(
                db=db, fecha=fecha,
                descripcion=f"Cheque {titular or ''} — acreditado banco",
                modulo="cheque_acred_banco",
                referencia_id=cheque_id,
                org_id=org_id,
                usuario_id=usuario_id,
                cuenta_debe_id=banco.id,
                cuenta_haber_id=cartera.id,
                monto=monto,
            )

        # A2: Cheques depositados D / Cliente H
        if not _ya_existe(db, "cheque_acred_cliente", cheque_id, org_id):
            _crear_asiento_directo(
                db=db, fecha=fecha,
                descripcion=f"Cheque {titular or ''} — acreditado cliente",
                modulo="cheque_acred_cliente",
                referencia_id=cheque_id,
                org_id=org_id,
                usuario_id=usuario_id,
                cuenta_debe_id=depositados.id,
                cuenta_haber_id=cliente_cuenta.id,
                monto=neto,
            )

        db.commit()
    except Exception as ex:
        db.rollback()
        logger.warning("Error asiento cheque acred %s: %s", cheque_id, ex)


def rechazar_cheque(
    db: Session,
    cheque_id: int,
    org_id: int,
    usuario_id: Optional[int],
    titular: str,
    monto: Decimal,
    gastos: Decimal,
    banco_cuenta_id: int,
    cliente_cuenta_id: int,
    fecha: date,
) -> None:
    """Rechazo cheque — 3 asientos (regla contador junio 2026):
    A1: Cliente (D) / Banco (H)                     →  reversión del cheque acreditado
    A2: Cliente (D) / Gastos de rechazos 3-2-2-1 (H) →  traslado de gastos al cliente
    A3: Gastos de rechazos 3-2-2-1 (D) / Banco (H)  →  débito bancario real"""
    try:
        monto  = round(_monto(monto),  2)
        gastos = round(_monto(gastos), 2)
        if monto <= 0:
            return

        banco          = db.query(PlanCuenta).filter(PlanCuenta.id == banco_cuenta_id).first()
        cliente_cuenta = db.query(PlanCuenta).filter(PlanCuenta.id == cliente_cuenta_id).first()
        gtos_rechazos  = _get_cuenta_por_codigo(db, "3-2-2-1", org_id)

        if not banco or not cliente_cuenta or not gtos_rechazos:
            logger.warning("Cuentas rechazo cheque no encontradas org %s cheque %s", org_id, cheque_id)
            return

        # A1: Cliente D / Banco H — reversión
        if not _ya_existe(db, "cheque_rechazo_banco", cheque_id, org_id):
            _crear_asiento_directo(
                db=db, fecha=fecha,
                descripcion=f"Cheque {titular or ''} — rechazo reversión",
                modulo="cheque_rechazo_banco",
                referencia_id=cheque_id,
                org_id=org_id, usuario_id=usuario_id,
                cuenta_debe_id=cliente_cuenta.id,
                cuenta_haber_id=banco.id,
                monto=monto,
            )

        # A2 y A3 solo si hay gastos
        if gastos > 0:
            # A2: Cliente D / Gastos de rechazos H — traslado al cliente
            if not _ya_existe(db, "cheque_rechazo_cliente", cheque_id, org_id):
                _crear_asiento_directo(
                    db=db, fecha=fecha,
                    descripcion=f"Cheque {titular or ''} — gastos rechazo a cliente",
                    modulo="cheque_rechazo_cliente",
                    referencia_id=cheque_id,
                    org_id=org_id, usuario_id=usuario_id,
                    cuenta_debe_id=cliente_cuenta.id,
                    cuenta_haber_id=gtos_rechazos.id,
                    monto=gastos,
                )
            # A3: Gastos de rechazos D / Banco H — débito bancario real
            if not _ya_existe(db, "cheque_rechazo_gasto", cheque_id, org_id):
                _crear_asiento_directo(
                    db=db, fecha=fecha,
                    descripcion=f"Cheque {titular or ''} — débito bancario rechazo",
                    modulo="cheque_rechazo_gasto",
                    referencia_id=cheque_id,
                    org_id=org_id, usuario_id=usuario_id,
                    cuenta_debe_id=gtos_rechazos.id,
                    cuenta_haber_id=banco.id,
                    monto=gastos,
                )

        db.commit()
    except Exception as ex:
        db.rollback()
        logger.warning("Error asiento cheque rechazo %s: %s", cheque_id, ex)


def _crear_asiento_directo(
    db: Session,
    fecha: date,
    descripcion: str,
    modulo: str,
    referencia_id: int,
    org_id: int,
    usuario_id: Optional[int],
    cuenta_debe_id: int,
    cuenta_haber_id: int,
    monto: Decimal,
) -> None:
    """Crea un asiento con cuentas explícitas (no por ReglaContable).
    Lo usa el módulo de egresos, que resuelve la cuenta del cliente dinámicamente."""
    a = Asiento(
        fecha=fecha,
        descripcion=descripcion,
        modulo=modulo,
        referencia_id=referencia_id,
        organizacion_id=org_id,
        usuario_id=usuario_id,
        numero_asiento=_next_numero_asiento(db, org_id),
    )
    db.add(a)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return
    db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=cuenta_debe_id,  debe=monto,          haber=Decimal("0")))
    db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=cuenta_haber_id, debe=Decimal("0"),   haber=monto))


def registrar_egreso(
    db: Session,
    egreso_id: int,
    org_id: int,
    usuario_id: Optional[int],
    tipo: str,
    forma_pago: str,
    monto: Decimal,
    fecha: date,
    beneficiario: str = "",
    concepto: str = "",
    cliente_id: Optional[int] = None,
    cliente_nombre: str = "",
) -> None:
    """Asiento del módulo unificado de Pagos (egresos). Una sola función para
    proveedor / gasto / pago_cliente, en banco o efectivo.

    Matriz de cuentas:
      tipo=pago_cliente → Debe: cuenta del cliente (2-1-2-X)
      tipo=proveedor/gasto → Debe: Gastos (3-2-0-0)
      forma_pago=banco    → Haber: Banco Macro (1-1-1-3-1, cuenta hoja)
      forma_pago=efectivo → Haber: Efectivo (1-1-1-2)
    """
    monto = round(_monto(monto), 2)
    try:
        if _ya_existe(db, "egreso", egreso_id, org_id):
            return
        if monto <= 0:
            return

        # Cuenta del Haber según forma de pago (siempre cuenta hoja)
        if forma_pago == "efectivo":
            cuenta_haber = _get_cuenta_por_codigo(db, "1-1-1-2", org_id)   # Efectivo
        else:
            cuenta_haber = _get_cuenta_por_codigo(db, "1-1-1-3-1", org_id) # Banco Macro (hoja)
        if not cuenta_haber:
            logger.warning("registrar_egreso: falta cuenta Haber (forma=%s, org=%s)", forma_pago, org_id)
            return

        # Cuenta del Debe según tipo
        if tipo == "pago_cliente" and cliente_id:
            cuenta_debe = _get_o_crear_cuenta_cliente(db, cliente_id, org_id)
        else:
            cuenta_debe = _get_cuenta_por_codigo(db, "3-2-0-0", org_id)    # Gastos
        if not cuenta_debe:
            logger.warning("registrar_egreso: falta cuenta Debe (tipo=%s, org=%s)", tipo, org_id)
            return

        etiqueta = beneficiario or cliente_nombre or concepto or "Egreso"
        _crear_asiento_directo(
            db=db,
            fecha=fecha,
            descripcion=f"Pago: {etiqueta} — {forma_pago}",
            modulo="egreso",
            referencia_id=egreso_id,
            org_id=org_id,
            usuario_id=usuario_id,
            cuenta_debe_id=cuenta_debe.id,
            cuenta_haber_id=cuenta_haber.id,
            monto=monto,
        )
        db.commit()
    except Exception as ex:
        db.rollback()
        logger.warning("Error asiento egreso %s: %s", egreso_id, ex)


def registrar_ingreso_efectivo(
    db: Session,
    arqueo_id: int,
    org_id: int,
    usuario_id: Optional[int],
    monto: Decimal,
    fecha: date,
) -> None:
    """Reposición de efectivo (banco → caja): Efectivo (D) / Banco (H).
    Upsert: si ya existe para este arqueo actualiza el monto."""
    try:
        if monto <= 0:
            return
        regla = _get_regla(db, "carga_efectivo", org_id)
        if not regla:
            return
        existente = (
            db.query(Asiento)
            .filter(
                Asiento.modulo == "caja_efectivo",
                Asiento.referencia_id == arqueo_id,
                Asiento.organizacion_id == org_id,
            )
            .first()
        )
        if existente:
            for linea in existente.lineas:
                if linea.cuenta_id == regla.cuenta_debe_id:
                    linea.debe  = monto
                    linea.haber = Decimal("0")
                else:
                    linea.haber = monto
                    linea.debe  = Decimal("0")
            existente.fecha = fecha
            db.commit()
        else:
            _crear_asiento(
                db=db, regla=regla,
                fecha=fecha,
                descripcion="Reposición efectivo desde banco",
                modulo="caja_efectivo",
                referencia_id=arqueo_id,
                org_id=org_id,
                usuario_id=usuario_id,
                monto=round(monto, 2),
            )
            db.commit()
    except Exception as ex:
        db.rollback()
        logger.warning("Error asiento ingreso_efectivo %s: %s", arqueo_id, ex)


def registrar_planilla(
    db: Session,
    planilla_id: int,
    org_id: int,
    usuario_id: Optional[int],
    cliente_nombre: str,
    nombre_archivo: str,
    rows,
    fecha_acred: date,
    solo_pendientes: bool = False,
    comision_pct: Decimal = Decimal("0"),
) -> None:
    """Asiento al conciliar una planilla: Pasivo Corriente (D) / Cliente (H).
    Si comision_pct > 0 genera un segundo asiento de comisión.
    En re-conciliación (solo_pendientes), actualiza el monto si ya existe."""
    comision_pct = Decimal(str(comision_pct))
    try:
        regla = _get_regla(db, "carga_planilla", org_id)
        if not regla:
            return
        total = sum(_monto(r.monto) for r in rows if r.status == "ok")
        if total <= 0:
            return

        existente = (
            db.query(Asiento)
            .filter(
                Asiento.modulo == "planilla",
                Asiento.referencia_id == planilla_id,
                Asiento.organizacion_id == org_id,
            )
            .first()
        )

        if existente and solo_pendientes:
            for linea in existente.lineas:
                if linea.cuenta_id == regla.cuenta_debe_id:
                    linea.debe = total; linea.haber = Decimal("0")
                else:
                    linea.haber = total; linea.debe = Decimal("0")
            existente.fecha = fecha_acred
        elif not existente:
            _crear_asiento(
                db=db, regla=regla,
                fecha=fecha_acred,
                descripcion=f"{cliente_nombre} — {nombre_archivo}",
                modulo="planilla",
                referencia_id=planilla_id,
                org_id=org_id,
                usuario_id=usuario_id,
                monto=total,
            )

        # Comisión opcional
        if comision_pct > 0:
            comision_monto = round(total * comision_pct / 100, 2)
            if comision_monto > 0:
                regla_com = _get_regla(db, "carga_planilla_comision", org_id)
                if regla_com:
                    existente_com = (
                        db.query(Asiento)
                        .filter(
                            Asiento.modulo == "planilla_comision",
                            Asiento.referencia_id == planilla_id,
                            Asiento.organizacion_id == org_id,
                        )
                        .first()
                    )
                    if existente_com and solo_pendientes:
                        for linea in existente_com.lineas:
                            if linea.cuenta_id == regla_com.cuenta_debe_id:
                                linea.debe = comision_monto; linea.haber = Decimal("0")
                            else:
                                linea.haber = comision_monto; linea.debe = Decimal("0")
                        existente_com.fecha = fecha_acred
                    elif not existente_com:
                        _crear_asiento(
                            db=db, regla=regla_com,
                            fecha=fecha_acred,
                            descripcion=f"{cliente_nombre} — comisión {comision_pct}%",
                            modulo="planilla_comision",
                            referencia_id=planilla_id,
                            org_id=org_id,
                            usuario_id=usuario_id,
                            monto=comision_monto,
                        )

        db.commit()
    except Exception as ex:
        db.rollback()
        logger.warning("Error asiento planilla %s: %s", planilla_id, ex)


# ─── UM: importación y reclasificación ──────────────────────────────────────

def _get_cuenta_por_codigo(db: Session, codigo: str, org_id: int) -> Optional[PlanCuenta]:
    return (
        db.query(PlanCuenta)
        .filter(PlanCuenta.codigo == codigo, PlanCuenta.organizacion_id == org_id, PlanCuenta.activo == True)
        .first()
    )


def _get_o_crear_cuenta_cliente(db: Session, cliente_id: int, org_id: int, reusar_huecos: bool = False) -> Optional[PlanCuenta]:
    """Resuelve la cuenta contable del Cliente EXISTENTE (vínculo 1:1).
    1. Si el cliente ya tiene cuenta_contable_id → la reutiliza.
    2. Si existe una cuenta bajo 2-1-2-0 con el mismo nombre → la adopta y la vincula.
    3. Si no existe ninguna → crea la cuenta y la vincula al cliente.
       - reusar_huecos=False (default): usa el próximo código (max+1).
       - reusar_huecos=True: usa el primer código libre en la secuencia (rellena
         huecos dejados por cuentas borradas, ej. una 2-1-2-8 eliminada).
    Nunca crea entidades Cliente; solo la cuenta contable asociada al cliente que ya está en el sistema."""
    from sqlalchemy import func as _func
    from app.models.cliente import Cliente

    cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()
    if not cliente:
        return None

    # 1. Cuenta ya vinculada
    if cliente.cuenta_contable_id:
        cuenta = db.query(PlanCuenta).filter(PlanCuenta.id == cliente.cuenta_contable_id).first()
        if cuenta:
            return cuenta

    padre = _get_cuenta_por_codigo(db, "2-1-2-0", org_id)
    if not padre:
        return None

    nombre_norm = (cliente.nombre or "").strip().title()

    # 2. Adoptar cuenta existente por nombre (ej. Green/Tucu/Alojando del seed)
    cuenta = (
        db.query(PlanCuenta)
        .filter(
            PlanCuenta.parent_id == padre.id,
            PlanCuenta.organizacion_id == org_id,
            _func.lower(PlanCuenta.nombre) == nombre_norm.lower(),
        )
        .first()
    )
    if cuenta:
        cliente.cuenta_contable_id = cuenta.id
        db.flush()
        return cuenta

    # 3. Crear cuenta nueva y vincularla al cliente
    hijos = db.query(PlanCuenta).filter(PlanCuenta.parent_id == padre.id, PlanCuenta.organizacion_id == org_id).all()
    usados = set()
    for hijo in hijos:
        try:
            usados.add(int(hijo.codigo.rsplit("-", 1)[-1]))
        except (ValueError, IndexError):
            pass
    if reusar_huecos:
        # primer entero >=1 que no esté usado (rellena el hueco más bajo)
        n = 1
        while n in usados:
            n += 1
        nuevo_n = n
    else:
        nuevo_n = (max(usados) if usados else 0) + 1
    nuevo_codigo = f"2-1-2-{nuevo_n}"
    nueva = PlanCuenta(
        codigo=nuevo_codigo, nombre=nombre_norm, tipo="pasivo",
        parent_id=padre.id, nivel=(padre.nivel or 3) + 1,
        activo=True, organizacion_id=org_id,
    )
    db.add(nueva)
    db.flush()
    cliente.cuenta_contable_id = nueva.id
    db.flush()
    logger.info("Cuenta cliente creada: %s %s (cliente_id=%s, org %s)", nuevo_codigo, nombre_norm, cliente_id, org_id)
    return nueva


def registrar_um_import(
    db: Session,
    extracto_id: int,
    org_id: int,
    usuario_id: Optional[int],
    movimientos_nuevos,
    modo: str = "agrupado",
) -> None:
    """Asiento al importar UM: Banco Macro (D) / No identificado (H).
    modo='agrupado' → un asiento por lote (suma total).
    modo='individual' → un asiento por movimiento."""
    try:
        if not movimientos_nuevos:
            return
        banco_macro = _get_cuenta_por_codigo(db, "1-1-1-3-1", org_id)
        no_id = _get_cuenta_por_codigo(db, "2-1-1-1", org_id)
        if not banco_macro or not no_id:
            logger.warning("Cuentas UM no encontradas org %s (1-1-1-3-1 / 2-1-1-1)", org_id)
            return
        if modo == "individual":
            for mov in movimientos_nuevos:
                if _ya_existe(db, "um_mov", mov.id, org_id):
                    continue
                monto = _monto(mov.monto)
                monto_abs = abs(monto)
                if monto_abs <= 0:
                    continue
                fecha_mov = mov.fecha if isinstance(mov.fecha, date) else hoy_art()
                a = Asiento(
                    fecha=fecha_mov,
                    descripcion=f"UM: {mov.titular or 'Sin titular'}",
                    modulo="um_mov",
                    referencia_id=mov.id,
                    organizacion_id=org_id,
                    usuario_id=usuario_id,
                )
                db.add(a)
                db.flush()
                if monto >= 0:
                    # Ingreso: Banco Debe / No Identificado Haber
                    db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=banco_macro.id, debe=monto_abs, haber=Decimal("0")))
                    db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=no_id.id, debe=Decimal("0"), haber=monto_abs))
                else:
                    # Egreso: No Identificado Debe / Banco Haber
                    db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=no_id.id, debe=monto_abs, haber=Decimal("0")))
                    db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=banco_macro.id, debe=Decimal("0"), haber=monto_abs))
        else:
            primer_mov = movimientos_nuevos[0]
            if _ya_existe(db, "um_lote", primer_mov.id, org_id):
                return
            total_pos = sum(max(_monto(m.monto), Decimal("0")) for m in movimientos_nuevos)
            total_neg = sum(abs(min(_monto(m.monto), Decimal("0"))) for m in movimientos_nuevos)
            if total_pos <= 0 and total_neg <= 0:
                return
            fecha_ref = primer_mov.fecha if isinstance(primer_mov.fecha, date) else hoy_art()
            lote = primer_mov.um_lote or 1
            a = Asiento(
                fecha=fecha_ref,
                descripcion=f"UM lote {lote} — {len(movimientos_nuevos)} movimientos (extracto #{extracto_id})",
                modulo="um_lote",
                referencia_id=primer_mov.id,
                organizacion_id=org_id,
                usuario_id=usuario_id,
            )
            db.add(a)
            db.flush()
            if total_pos > 0:
                # Ingresos: Banco Debe / No Identificado Haber
                db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=banco_macro.id, debe=total_pos, haber=Decimal("0")))
                db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=no_id.id, debe=Decimal("0"), haber=total_pos))
            if total_neg > 0:
                # Egresos: No Identificado Debe / Banco Haber
                db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=no_id.id, debe=total_neg, haber=Decimal("0")))
                db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=banco_macro.id, debe=Decimal("0"), haber=total_neg))
        db.commit()
    except Exception as ex:
        db.rollback()
        logger.warning("Error asiento UM import %s: %s", extracto_id, ex)


def registrar_reclasificacion_um(
    db: Session,
    planilla_row_id: int,
    org_id: int,
    usuario_id: Optional[int],
    cliente_id: int,
    cliente_nombre: str,
    monto,
    fecha: date,
) -> None:
    """Asiento de reclasificación al conciliar un movimiento UM: No identificado (D) / Cliente X (H).
    La cuenta del cliente existente se resuelve/crea/vincula vía _get_o_crear_cuenta_cliente."""
    try:
        if _ya_existe(db, "um_reclass", planilla_row_id, org_id):
            return
        no_id = _get_cuenta_por_codigo(db, "2-1-1-1", org_id)
        cuenta_cliente = _get_o_crear_cuenta_cliente(db, cliente_id, org_id) if cliente_id else None
        if not no_id or not cuenta_cliente:
            logger.warning("Cuentas reclasificación no encontradas org %s (cliente_id=%s)", org_id, cliente_id)
            return
        monto_d = abs(_monto(monto))
        if monto_d <= 0:
            return
        fecha_asiento = fecha if isinstance(fecha, date) else hoy_art()
        a = Asiento(
            fecha=fecha_asiento,
            descripcion=f"Reclasif. UM → {cliente_nombre}",
            modulo="um_reclass",
            referencia_id=planilla_row_id,
            organizacion_id=org_id,
            usuario_id=usuario_id,
        )
        db.add(a)
        db.flush()
        db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=no_id.id, debe=monto_d, haber=Decimal("0")))
        db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=cuenta_cliente.id, debe=Decimal("0"), haber=monto_d))
        db.commit()
    except Exception as ex:
        db.rollback()
        logger.warning("Error asiento reclasif. row %s: %s", planilla_row_id, ex)


def registrar_reclasificacion_planilla(
    db: Session,
    planilla_id: int,
    org_id: int,
    usuario_id: Optional[int],
    cliente_id: int,
    cliente_nombre: str,
    total_monto: Decimal,
    fecha: date,
    nombre_archivo: str = "",
) -> None:
    """Asiento agrupado por planilla: No identificado (D) / Cliente X (H).
    Un solo asiento por planilla con el total conciliado (en lugar de uno por fila).
    Upsert: si ya existe un asiento previo para esta planilla, actualiza el monto
    (para re-conciliaciones que acreditan filas adicionales en una segunda pasada)."""
    try:
        total_monto = abs(round(_monto(total_monto), 2))
        if total_monto <= 0:
            return
        no_id = _get_cuenta_por_codigo(db, "2-1-1-1", org_id)
        cuenta_cliente = _get_o_crear_cuenta_cliente(db, cliente_id, org_id) if cliente_id else None
        if not no_id or not cuenta_cliente:
            logger.warning("Cuentas reclasificación planilla no encontradas org %s (cliente_id=%s)", org_id, cliente_id)
            return
        fecha_asiento = fecha if isinstance(fecha, date) else hoy_art()
        desc = f"TT {cliente_nombre}"
        if nombre_archivo:
            desc += f" — {nombre_archivo}"

        existente = (
            db.query(Asiento)
            .filter(
                Asiento.modulo == "um_reclass_planilla",
                Asiento.referencia_id == planilla_id,
                Asiento.organizacion_id == org_id,
            )
            .first()
        )
        if existente:
            for linea in existente.lineas:
                if linea.cuenta_id == no_id.id:
                    linea.debe = total_monto
                    linea.haber = Decimal("0")
                else:
                    linea.haber = total_monto
                    linea.debe = Decimal("0")
            existente.fecha = fecha_asiento
        else:
            a = Asiento(
                fecha=fecha_asiento,
                descripcion=desc,
                modulo="um_reclass_planilla",
                referencia_id=planilla_id,
                organizacion_id=org_id,
                usuario_id=usuario_id,
                numero_asiento=_next_numero_asiento(db, org_id),
            )
            db.add(a)
            db.flush()
            db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=no_id.id,            debe=total_monto,    haber=Decimal("0")))
            db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=cuenta_cliente.id,   debe=Decimal("0"),   haber=total_monto))
        db.commit()
    except Exception as ex:
        db.rollback()
        logger.warning("Error asiento reclasif. planilla %s: %s", planilla_id, ex)


def registrar_liquidacion_aprobacion(
    db: Session,
    liquidacion_id: int,
    detalle_id: int,
    org_id: int,
    usuario_id: Optional[int],
    cliente_id: int,
    cliente_nombre: str,
    monto_conciliado: Decimal,
    monto_neto: Decimal,
    monto_comision: Decimal,
    fecha: date,
) -> None:
    """Asiento al aprobar una liquidación, por cada detalle (cliente):
    Cliente (2-1-2-X) D monto_conciliado / Banco Macro (1-1-1-3-1) H monto_neto
    + Comisiones ganadas (3-1-1-0) H monto_comision (si > 0).
    Cancela la deuda con el cliente y reconoce la comisión como ingreso."""
    try:
        if _ya_existe(db, "liquidacion_aprobacion", detalle_id, org_id):
            return
        monto_conciliado = round(_monto(monto_conciliado), 2)
        monto_neto       = round(_monto(monto_neto), 2)
        monto_comision   = round(_monto(monto_comision), 2)
        if monto_conciliado <= 0:
            return
        cuenta_cliente = _get_o_crear_cuenta_cliente(db, cliente_id, org_id) if cliente_id else None
        banco          = _get_cuenta_por_codigo(db, "1-1-1-3-1", org_id)
        comisiones     = _get_cuenta_por_codigo(db, "3-1-1-0", org_id)
        # Exigir la cuenta de comisiones cuando hay comisión: sin ella el asiento
        # quedaría desbalanceado (Cliente D conciliado / Banco H neto, con neto < conciliado).
        if not cuenta_cliente or not banco or (monto_comision > 0 and not comisiones):
            logger.warning("Cuentas liquidación incompletas org %s (cliente_id=%s) — no se postea", org_id, cliente_id)
            return
        lineas = [
            (cuenta_cliente.id, monto_conciliado, Decimal("0")),
            (banco.id,          Decimal("0"),     monto_neto),
        ]
        if monto_comision > 0:
            lineas.append((comisiones.id, Decimal("0"), monto_comision))
        _crear_asiento_multilinea(
            db=db,
            fecha=fecha if isinstance(fecha, date) else hoy_art(),
            descripcion=f"Liquidación #{liquidacion_id} — {cliente_nombre}",
            modulo="liquidacion_aprobacion",
            referencia_id=detalle_id,
            org_id=org_id,
            usuario_id=usuario_id,
            lineas=lineas,
        )
        db.commit()
    except Exception as ex:
        db.rollback()
        logger.warning("Error asiento liquidacion aprobacion detalle %s: %s", detalle_id, ex)


def registrar_liquidacion_sueldos(
    db: Session,
    liquidacion_id: int,
    org_id: int,
    usuario_id: Optional[int],
    periodo: str,
    total_bruto: Decimal,
    total_aportes: Decimal,
    total_contribuciones: Decimal,
    total_neto: Decimal,
    total_retencion_ganancias: Decimal = Decimal("0"),
) -> None:
    """Asiento agrupado al aprobar una liquidación de sueldos del período:
        Sueldos y cargas sociales (3-2-4-0, gasto) D       por bruto + contribuciones
        Sueldos a pagar (2-1-4-0) H                        por el neto a pagar al empleado
        Cargas sociales a pagar (2-1-5-0) H                por aportes + contribuciones
        Retención de Ganancias a depositar (2-1-6-0) H     por la retención de 4ta (si > 0)
    La retención de Ganancias que se le descuenta al empleado es un pasivo del
    empleador (la retiene para depositarla a ARCA): por eso va al Haber. Sin esta
    contrapartida el asiento descuadraba al activar Ganancias (porque el neto ya
    viene con la retención restada) y la red de partida doble no lo posteaba.
    Partida doble: D = bruto+contrib ; H = neto + aportes + contrib + ganancias
                   = (bruto−aportes−ganancias) + aportes + contrib + ganancias
                   = bruto + contrib = D ✓.
    Idempotente por (modulo, referencia_id=liquidacion_id, org)."""
    try:
        if _ya_existe(db, "sueldos_liquidacion", liquidacion_id, org_id):
            return
        bruto   = round(_monto(total_bruto), 2)
        aportes = round(_monto(total_aportes), 2)
        contrib = round(_monto(total_contribuciones), 2)
        neto    = round(_monto(total_neto), 2)
        ret     = round(_monto(total_retencion_ganancias), 2)
        if bruto <= 0:
            return
        gasto       = _get_cuenta_por_codigo(db, "3-2-4-0", org_id)
        sueldos_pag = _get_cuenta_por_codigo(db, "2-1-4-0", org_id)
        cargas_pag  = _get_cuenta_por_codigo(db, "2-1-5-0", org_id)
        if not gasto or not sueldos_pag or not cargas_pag:
            logger.warning(
                "Cuentas sueldos no encontradas org %s (3-2-4-0/2-1-4-0/2-1-5-0)", org_id
            )
            return
        debe_total = (bruto + contrib)
        cargas = (aportes + contrib)
        lineas = [
            (gasto.id,       debe_total,   Decimal("0")),
            (sueldos_pag.id, Decimal("0"), neto),
            (cargas_pag.id,  Decimal("0"), cargas),
        ]
        if ret > 0:
            ret_pag = _get_cuenta_por_codigo(db, "2-1-6-0", org_id)
            if ret_pag:
                lineas.append((ret_pag.id, Decimal("0"), ret))
            else:
                # Defensivo: PLAN_PATCH crea 2-1-6-0 en cada arranque, así que en
                # producción siempre existe. Si faltara, no agregamos la línea para
                # no romper el alta — pero el asiento descuadraría, así que avisamos.
                logger.warning(
                    "Cuenta 2-1-6-0 (Retención de Ganancias) no encontrada org %s — "
                    "asiento de sueldos sin contrapartida de retención", org_id
                )
        _crear_asiento_multilinea(
            db=db,
            fecha=hoy_art(),
            descripcion=f"Liquidación de sueldos {periodo}",
            modulo="sueldos_liquidacion",
            referencia_id=liquidacion_id,
            org_id=org_id,
            usuario_id=usuario_id,
            lineas=lineas,
        )
        db.commit()
    except Exception as ex:
        db.rollback()
        logger.warning("Error asiento liquidacion sueldos %s: %s", liquidacion_id, ex)


def registrar_cc_inicial(
    db: Session,
    planilla_row_id: int,
    org_id: int,
    usuario_id: Optional[int],
    cliente_id: int,
    cliente_nombre: str,
    monto,
    fecha: date,
    nombre_archivo: str = "",
) -> bool:
    """Backfill histórico de cuenta corriente: acreditación ya conciliada →
    Banco Macro (D) / Cliente X (H). Asiento neto y balanceado para reconstruir
    las cuentas corrientes desde datos cargados antes de que existiera el motor.
    Idempotente: no crea si la fila ya tiene asiento del flujo normal (um_reclass)
    ni un cc_inicial previo. Devuelve True si creó el asiento."""
    try:
        if _ya_existe(db, "um_reclass", planilla_row_id, org_id):
            return False
        if _ya_existe(db, "cc_inicial", planilla_row_id, org_id):
            return False
        banco = _get_cuenta_por_codigo(db, "1-1-1-3-1", org_id)
        cuenta_cliente = _get_o_crear_cuenta_cliente(db, cliente_id, org_id) if cliente_id else None
        if not banco or not cuenta_cliente:
            return False
        monto_d = abs(_monto(monto))
        if monto_d <= 0:
            return False
        fecha_asiento = fecha if isinstance(fecha, date) else hoy_art()
        desc = f"Acreditación histórica — {cliente_nombre}"
        if nombre_archivo:
            desc += f" ({nombre_archivo})"
        a = Asiento(
            fecha=fecha_asiento,
            descripcion=desc,
            modulo="cc_inicial",
            referencia_id=planilla_row_id,
            organizacion_id=org_id,
            usuario_id=usuario_id,
        )
        db.add(a)
        db.flush()
        db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=banco.id, debe=monto_d, haber=Decimal("0")))
        db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=cuenta_cliente.id, debe=Decimal("0"), haber=monto_d))
        db.commit()
        return True
    except Exception as ex:
        db.rollback()
        logger.warning("Error cc_inicial row %s: %s", planilla_row_id, ex)
        return False


# ─── Reversión contable ──────────────────────────────────────────────────────

def reversar_asientos(
    db: Session,
    modulo: str,
    referencia_id: int,
    org_id: int,
    usuario_id: Optional[int],
    motivo: str = "Reverso por baja del registro origen",
) -> int:
    """Crea asientos de reverso (debe↔haber invertidos) para los asientos del
    modulo+referencia dados. NO borra los originales — la trazabilidad queda
    completa en el libro: el asiento original más su reverso.

    Idempotente: si ya existe un reverso para el mismo origen, no crea otro.
    Devuelve la cantidad de reversos creados.
    """
    try:
        originales = (
            db.query(Asiento)
            .filter(
                Asiento.modulo == modulo,
                Asiento.referencia_id == referencia_id,
                Asiento.organizacion_id == org_id,
            )
            .all()
        )
        if not originales:
            return 0

        modulo_reverso = f"{modulo}_reverso"
        creados = 0
        for orig in originales:
            # Idempotencia: no duplicar si ya hay un reverso para este asiento
            ya_reversado = (
                db.query(Asiento)
                .filter(
                    Asiento.modulo == modulo_reverso,
                    Asiento.referencia_id == orig.id,
                    Asiento.organizacion_id == org_id,
                )
                .first()
            )
            if ya_reversado:
                continue

            reverso = Asiento(
                fecha=hoy_art(),
                descripcion=f"REVERSO #{orig.id}: {orig.descripcion or ''} — {motivo}",
                modulo=modulo_reverso,
                referencia_id=orig.id,
                organizacion_id=org_id,
                usuario_id=usuario_id,
                numero_asiento=_next_numero_asiento(db, org_id),
            )
            db.add(reverso)
            db.flush()

            # Invertir cada línea del original (debe ↔ haber)
            for linea in orig.lineas:
                db.add(AsientoDetalle(
                    asiento_id=reverso.id,
                    cuenta_id=linea.cuenta_id,
                    debe=linea.haber,
                    haber=linea.debe,
                ))
            creados += 1

        if creados:
            db.commit()
        return creados
    except Exception as ex:
        db.rollback()
        logger.warning("Error reversando %s/%s: %s", modulo, referencia_id, ex)
        return 0


def registrar_ajuste_manual(
    db: Session,
    org_id: int,
    usuario_id: int,
    cuenta_debe_id: int,
    cuenta_haber_id: int,
    monto: Decimal,
    fecha: date,
    descripcion: str,
) -> int:
    """Crea un asiento de ajuste manual. Retorna el ID del asiento creado.
    NO es idempotente — cada llamada crea un asiento nuevo.
    """
    a = Asiento(
        fecha=fecha,
        descripcion=descripcion,
        modulo="ajuste_manual",
        referencia_id=None,
        organizacion_id=org_id,
        usuario_id=usuario_id,
        numero_asiento=_next_numero_asiento(db, org_id),
    )
    db.add(a)
    db.flush()
    db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=cuenta_debe_id, debe=monto, haber=Decimal("0")))
    db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=cuenta_haber_id, debe=Decimal("0"), haber=monto))
    return a.id


# ─── Liquidaciones de tarjetas de crédito (Visa / Mastercard / Amex) ──────────

# Cuenta de aranceles por marca de tarjeta.
_ARANCEL_CUENTA_POR_MARCA = {
    "visa":       "3-2-3-1",
    "mastercard": "3-2-3-2",
    "amex":       "3-2-3-3",
}


def registrar_liquidacion_tarjeta(
    db: Session,
    liquidacion_id: int,
    org_id: int,
    usuario_id: Optional[int],
    marca: str,
    monto_bruto: Decimal,
    aranceles: Decimal,
    iva_df: Decimal,
    percepciones_iibb: Decimal,
    retenciones: Decimal,
    neto: Decimal,
    fecha: date,
    descripcion: str = "",
) -> Optional[int]:
    """Asiento mensual agrupado de liquidación de tarjeta (módulo `tarjeta_liq`).

        Banco Macro (1-1-1-3-1)               D: neto
        Aranceles tarjeta (3-2-3-X por marca) D: aranceles
        IVA Crédito Fiscal (1-1-2-4)          D: iva_df
        Percepciones IIBB (1-1-2-5)           D: percepciones_iibb
        Retenciones de impuestos (1-1-2-6)    D: retenciones
            Ingresos por tarjetas (3-1-4-0)   H: monto_bruto

    Devuelve el ID del asiento creado (o None si no se pudo crear). Idempotente:
    no crea un segundo asiento para la misma (tarjeta_liq, liquidacion_id, org)."""
    try:
        if _ya_existe(db, "tarjeta_liq", liquidacion_id, org_id):
            existente = (
                db.query(Asiento)
                .filter(
                    Asiento.modulo == "tarjeta_liq",
                    Asiento.referencia_id == liquidacion_id,
                    Asiento.organizacion_id == org_id,
                )
                .first()
            )
            return existente.id if existente else None

        monto_bruto       = round(_monto(monto_bruto), 2)
        aranceles         = round(_monto(aranceles), 2)
        iva_df            = round(_monto(iva_df), 2)
        percepciones_iibb = round(_monto(percepciones_iibb), 2)
        retenciones       = round(_monto(retenciones), 2)
        neto              = round(_monto(neto), 2)

        banco         = _get_cuenta_por_codigo(db, "1-1-1-3-1", org_id)
        ingresos      = _get_cuenta_por_codigo(db, "3-1-4-0", org_id)
        cta_iva       = _get_cuenta_por_codigo(db, "1-1-2-4", org_id)
        cta_iibb      = _get_cuenta_por_codigo(db, "1-1-2-5", org_id)
        cta_ret       = _get_cuenta_por_codigo(db, "1-1-2-6", org_id)
        cod_arancel   = _ARANCEL_CUENTA_POR_MARCA.get(str(marca).lower(), "3-2-3-0")
        cta_arancel   = _get_cuenta_por_codigo(db, cod_arancel, org_id)

        if not (banco and ingresos and cta_iva and cta_iibb and cta_ret and cta_arancel):
            logger.warning(
                "Cuentas tarjeta incompletas org %s liq %s — no se postea", org_id, liquidacion_id
            )
            return None

        lineas = [(banco.id, neto, Decimal("0"))]
        if aranceles > 0:
            lineas.append((cta_arancel.id, aranceles, Decimal("0")))
        if iva_df > 0:
            lineas.append((cta_iva.id, iva_df, Decimal("0")))
        if percepciones_iibb > 0:
            lineas.append((cta_iibb.id, percepciones_iibb, Decimal("0")))
        if retenciones > 0:
            lineas.append((cta_ret.id, retenciones, Decimal("0")))
        lineas.append((ingresos.id, Decimal("0"), monto_bruto))

        a = Asiento(
            fecha=fecha if isinstance(fecha, date) else hoy_art(),
            descripcion=descripcion or f"Liquidación tarjeta {str(marca).capitalize()}",
            modulo="tarjeta_liq",
            referencia_id=liquidacion_id,
            organizacion_id=org_id,
            usuario_id=usuario_id,
            numero_asiento=_next_numero_asiento(db, org_id),
        )
        # Red de seguridad: rechazar si no cuadra en partida doble
        total_debe  = sum(d for _c, d, _h in lineas)
        total_haber = sum(h for _c, _d, h in lineas)
        if abs(total_debe - total_haber) > Decimal("0.01"):
            logger.error(
                "Asiento tarjeta_liq liq %s NO balancea (debe=%s haber=%s) — no se postea",
                liquidacion_id, total_debe, total_haber,
            )
            return None
        db.add(a)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            return None
        for cuenta_id, debe, haber in lineas:
            db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=cuenta_id, debe=debe, haber=haber))
        db.commit()
        return a.id
    except Exception as ex:
        db.rollback()
        logger.warning("Error asiento tarjeta_liq %s: %s", liquidacion_id, ex)
        return None


def registrar_factura_arca(
    db: Session,
    comprobante_id: int,
    org_id: int,
    usuario_id: Optional[int],
    cliente_id: Optional[int],
    cliente_nombre: str,
    importe_neto: Decimal,
    importe_iva: Decimal,
    importe_total: Decimal,
    fecha: date,
) -> Optional[int]:
    """Asiento al obtener el CAE de una factura ARCA:
    Cliente (2-1-2-X) D total  /  Ventas (3-1-5-0) H neto + IVA Débito Fiscal (2-2-1-0) H iva.
    Sin cliente vinculado no se postea (no hay contra-cuenta D) — el comprobante con CAE
    sigue siendo válido igual, solo queda sin reflejo en el Libro Diario."""
    try:
        if _ya_existe(db, "arca_factura", comprobante_id, org_id):
            return None
        importe_neto  = round(_monto(importe_neto), 2)
        importe_iva   = round(_monto(importe_iva), 2)
        importe_total = round(_monto(importe_total), 2)
        if importe_total <= 0 or not cliente_id:
            return None

        cuenta_cliente = _get_o_crear_cuenta_cliente(db, cliente_id, org_id)
        ventas         = _get_cuenta_por_codigo(db, "3-1-5-0", org_id)
        iva_df         = _get_cuenta_por_codigo(db, "2-2-1-0", org_id)
        if not cuenta_cliente or not ventas or (importe_iva > 0 and not iva_df):
            logger.warning("Cuentas factura ARCA incompletas org %s (cliente_id=%s) — no se postea", org_id, cliente_id)
            return None

        lineas = [
            (cuenta_cliente.id, importe_total, Decimal("0")),
            (ventas.id,         Decimal("0"),  importe_neto),
        ]
        if importe_iva > 0:
            lineas.append((iva_df.id, Decimal("0"), importe_iva))

        a = Asiento(
            fecha=fecha if isinstance(fecha, date) else hoy_art(),
            descripcion=f"Factura ARCA — {cliente_nombre or ''}",
            modulo="arca_factura",
            referencia_id=comprobante_id,
            organizacion_id=org_id,
            usuario_id=usuario_id,
            numero_asiento=_next_numero_asiento(db, org_id),
        )
        total_debe  = sum(d for _c, d, _h in lineas)
        total_haber = sum(h for _c, _d, h in lineas)
        if abs(total_debe - total_haber) > Decimal("0.01"):
            logger.error(
                "Asiento arca_factura comprobante %s NO balancea (debe=%s haber=%s) — no se postea",
                comprobante_id, total_debe, total_haber,
            )
            return None
        db.add(a)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            return None
        for cuenta_id, debe, haber in lineas:
            db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=cuenta_id, debe=debe, haber=haber))
        db.commit()
        return a.id
    except Exception as ex:
        db.rollback()
        logger.warning("Error asiento arca_factura %s: %s", comprobante_id, ex)
        return None
