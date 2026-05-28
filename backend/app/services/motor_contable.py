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
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.contabilidad import PlanCuenta, ReglaContable, Asiento, AsientoDetalle

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
        hoy = date.today()
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
    """Carga cheque: Créditos (D) / Pasivo cliente (H). Comisión opcional."""
    try:
        if _ya_existe(db, "cheque_carga", cheque_id, org_id):
            return
        regla = _get_regla(db, "carga_cheque", org_id)
        if not regla or monto <= 0:
            return
        _crear_asiento(
            db=db, regla=regla,
            fecha=fecha,
            descripcion=f"Cheque {titular or ''} — carga",
            modulo="cheque_carga",
            referencia_id=cheque_id,
            org_id=org_id,
            usuario_id=usuario_id,
            monto=round(monto, 2),
        )
        if comision > 0:
            regla_com = _get_regla(db, "carga_cheque_comision", org_id)
            if regla_com:
                _crear_asiento(
                    db=db, regla=regla_com,
                    fecha=fecha,
                    descripcion=f"Cheque {titular or ''} — comisión",
                    modulo="cheque_comision",
                    referencia_id=cheque_id,
                    org_id=org_id,
                    usuario_id=usuario_id,
                    monto=round(comision, 2),
                )
        db.commit()
    except Exception as ex:
        db.rollback()
        logger.warning("Error asiento cheque carga %s: %s", cheque_id, ex)


def acreditar_cheque(
    db: Session,
    cheque_id: int,
    org_id: int,
    usuario_id: Optional[int],
    titular: str,
    monto: Decimal,
    fecha: date,
) -> None:
    """Acreditación cheque: Banco (D) / Créditos (H)."""
    try:
        if _ya_existe(db, "cheque_acred", cheque_id, org_id):
            return
        regla = _get_regla(db, "acred_rechazo_banco", org_id)
        if not regla or monto <= 0:
            return
        _crear_asiento(
            db=db, regla=regla,
            fecha=fecha,
            descripcion=f"Cheque {titular or ''} — acreditado",
            modulo="cheque_acred",
            referencia_id=cheque_id,
            org_id=org_id,
            usuario_id=usuario_id,
            monto=round(monto, 2),
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
    fecha: date,
) -> None:
    """Rechazo cheque: Pasivo cliente (D) / Créditos (H)."""
    try:
        if _ya_existe(db, "cheque_rechazo", cheque_id, org_id):
            return
        regla = _get_regla(db, "acred_rechazo_pasivo", org_id)
        if not regla or monto <= 0:
            return
        _crear_asiento(
            db=db, regla=regla,
            fecha=fecha,
            descripcion=f"Cheque {titular or ''} — rechazado",
            modulo="cheque_rechazo",
            referencia_id=cheque_id,
            org_id=org_id,
            usuario_id=usuario_id,
            monto=round(monto, 2),
        )
        db.commit()
    except Exception as ex:
        db.rollback()
        logger.warning("Error asiento cheque rechazo %s: %s", cheque_id, ex)


def registrar_op_pago(
    db: Session,
    op_id: int,
    org_id: int,
    usuario_id: Optional[int],
    beneficiario: str,
    cliente_nombre: str,
    monto: Decimal,
    fecha: date,
) -> None:
    """OP de caja: Gastos (D) / Efectivo (H)."""
    try:
        if _ya_existe(db, "caja_op", op_id, org_id):
            return
        regla = _get_regla(db, "asig_gasto_efectivo", org_id)
        if not regla or monto <= 0:
            return
        _crear_asiento(
            db=db, regla=regla,
            fecha=fecha,
            descripcion=f"OP: {beneficiario} ({cliente_nombre})",
            modulo="caja_op",
            referencia_id=op_id,
            org_id=org_id,
            usuario_id=usuario_id,
            monto=round(monto, 2),
        )
        db.commit()
    except Exception as ex:
        db.rollback()
        logger.warning("Error asiento op_pago %s: %s", op_id, ex)


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


def registrar_pago(
    db: Session,
    pago_id: int,
    org_id: int,
    usuario_id: Optional[int],
    concepto: str,
    cliente_nombre: str,
    monto: Decimal,
    medio: str,
    fecha: date,
) -> None:
    """Pago a cliente: Pasivo cliente (D) / Banco o Efectivo (H)."""
    try:
        if _ya_existe(db, "pago", pago_id, org_id):
            return
        evento = "pago_cliente_banco" if medio == "banco" else "pago_cliente_efectivo"
        regla = _get_regla(db, evento, org_id)
        if not regla or monto <= 0:
            return
        _crear_asiento(
            db=db, regla=regla,
            fecha=fecha,
            descripcion=f"Pago {cliente_nombre or concepto or ''} — {medio}",
            modulo="pago",
            referencia_id=pago_id,
            org_id=org_id,
            usuario_id=usuario_id,
            monto=round(monto, 2),
        )
        db.commit()
    except Exception as ex:
        db.rollback()
        logger.warning("Error asiento pago %s: %s", pago_id, ex)


def registrar_gasto(
    db: Session,
    gasto_id: int,
    org_id: int,
    usuario_id: Optional[int],
    concepto: str,
    monto: Decimal,
    medio: str,
    fecha: date,
) -> None:
    """Gasto operativo: Gastos (D) / Banco o Efectivo (H)."""
    try:
        if _ya_existe(db, "gasto", gasto_id, org_id):
            return
        evento = "asig_gasto_banco" if medio == "banco" else "asig_gasto_efectivo"
        regla = _get_regla(db, evento, org_id)
        if not regla or monto <= 0:
            return
        _crear_asiento(
            db=db, regla=regla,
            fecha=fecha,
            descripcion=f"Gasto: {concepto or ''}",
            modulo="gasto",
            referencia_id=gasto_id,
            org_id=org_id,
            usuario_id=usuario_id,
            monto=round(monto, 2),
        )
        db.commit()
    except Exception as ex:
        db.rollback()
        logger.warning("Error asiento gasto %s: %s", gasto_id, ex)


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


def _get_o_crear_cuenta_cliente(db: Session, cliente_nombre: str, org_id: int) -> Optional[PlanCuenta]:
    """Busca la cuenta del cliente bajo 2-1-2-0. Si no existe la crea con el próximo código."""
    from sqlalchemy import func as _func
    padre = _get_cuenta_por_codigo(db, "2-1-2-0", org_id)
    if not padre:
        return None
    nombre_norm = cliente_nombre.strip().title()
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
        return cuenta
    hijos = db.query(PlanCuenta).filter(PlanCuenta.parent_id == padre.id, PlanCuenta.organizacion_id == org_id).all()
    max_n = 0
    for hijo in hijos:
        try:
            max_n = max(max_n, int(hijo.codigo.rsplit("-", 1)[-1]))
        except (ValueError, IndexError):
            pass
    nuevo_codigo = f"2-1-2-{max_n + 1}"
    nueva = PlanCuenta(
        codigo=nuevo_codigo, nombre=nombre_norm, tipo="pasivo",
        parent_id=padre.id, nivel=(padre.nivel or 3) + 1,
        activo=True, organizacion_id=org_id,
    )
    db.add(nueva)
    db.flush()
    logger.info("Cuenta cliente creada: %s %s (org %s)", nuevo_codigo, nombre_norm, org_id)
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
                monto = abs(_monto(mov.monto))
                if monto <= 0:
                    continue
                fecha_mov = mov.fecha if isinstance(mov.fecha, date) else date.today()
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
                db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=banco_macro.id, debe=monto, haber=Decimal("0")))
                db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=no_id.id, debe=Decimal("0"), haber=monto))
        else:
            primer_mov = movimientos_nuevos[0]
            if _ya_existe(db, "um_lote", primer_mov.id, org_id):
                return
            total = sum(abs(_monto(m.monto)) for m in movimientos_nuevos)
            if total <= 0:
                return
            fecha_ref = primer_mov.fecha if isinstance(primer_mov.fecha, date) else date.today()
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
            db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=banco_macro.id, debe=total, haber=Decimal("0")))
            db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=no_id.id, debe=Decimal("0"), haber=total))
        db.commit()
    except Exception as ex:
        db.rollback()
        logger.warning("Error asiento UM import %s: %s", extracto_id, ex)


def registrar_reclasificacion_um(
    db: Session,
    planilla_row_id: int,
    org_id: int,
    usuario_id: Optional[int],
    cliente_nombre: str,
    monto,
    fecha: date,
) -> None:
    """Asiento de reclasificación al conciliar un movimiento UM: No identificado (D) / Cliente X (H).
    La cuenta del cliente se crea automáticamente si no existe."""
    try:
        if _ya_existe(db, "um_reclass", planilla_row_id, org_id):
            return
        no_id = _get_cuenta_por_codigo(db, "2-1-1-1", org_id)
        cuenta_cliente = _get_o_crear_cuenta_cliente(db, cliente_nombre, org_id)
        if not no_id or not cuenta_cliente:
            logger.warning("Cuentas reclasificación no encontradas org %s", org_id)
            return
        monto_d = abs(_monto(monto))
        if monto_d <= 0:
            return
        fecha_asiento = fecha if isinstance(fecha, date) else date.today()
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
                fecha=date.today(),
                descripcion=f"REVERSO #{orig.id}: {orig.descripcion or ''} — {motivo}",
                modulo=modulo_reverso,
                referencia_id=orig.id,
                organizacion_id=org_id,
                usuario_id=usuario_id,
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
