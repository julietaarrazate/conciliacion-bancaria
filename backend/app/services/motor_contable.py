"""
Motor contable — Fase 2.
Genera asientos automáticos cuando ocurren operaciones en el sistema.
Siempre encapsulado en try/except: si falla, la operación principal NO se revierte.
Idempotente: nunca crea dos asientos para el mismo (modulo, referencia_id, org_id).
"""

from datetime import date
from typing import Optional
from sqlalchemy.orm import Session

from app.models.contabilidad import PlanCuenta, ReglaContable, Asiento, AsientoDetalle


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


def _monto(v) -> float:
    try:
        return round(float(str(v).replace(",", ".").replace("$", "").strip()), 2)
    except Exception:
        return 0.0


def _crear_asiento(
    db: Session,
    regla: ReglaContable,
    fecha: date,
    descripcion: str,
    modulo: str,
    referencia_id: int,
    org_id: int,
    usuario_id: Optional[int],
    monto: float,
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
    db.flush()
    db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=regla.cuenta_debe_id,  debe=monto, haber=0.0))
    db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=regla.cuenta_haber_id, debe=0.0,  haber=monto))


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
        print(f"[motor_contable] Warning extracto {extracto_id}: {ex}")


def registrar_cheque(
    db: Session,
    cheque_id: int,
    org_id: int,
    usuario_id: Optional[int],
    titular: str,
    monto: float,
    comision: float,
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
        print(f"[motor_contable] Warning cheque carga {cheque_id}: {ex}")


def acreditar_cheque(
    db: Session,
    cheque_id: int,
    org_id: int,
    usuario_id: Optional[int],
    titular: str,
    monto: float,
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
        print(f"[motor_contable] Warning cheque acred {cheque_id}: {ex}")


def rechazar_cheque(
    db: Session,
    cheque_id: int,
    org_id: int,
    usuario_id: Optional[int],
    titular: str,
    monto: float,
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
        print(f"[motor_contable] Warning cheque rechazo {cheque_id}: {ex}")


def registrar_op_pago(
    db: Session,
    op_id: int,
    org_id: int,
    usuario_id: Optional[int],
    beneficiario: str,
    cliente_nombre: str,
    monto: float,
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
        print(f"[motor_contable] Warning op_pago {op_id}: {ex}")


def registrar_ingreso_efectivo(
    db: Session,
    arqueo_id: int,
    org_id: int,
    usuario_id: Optional[int],
    monto: float,
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
                    linea.haber = 0.0
                else:
                    linea.haber = monto
                    linea.debe  = 0.0
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
        print(f"[motor_contable] Warning ingreso_efectivo arqueo {arqueo_id}: {ex}")


def registrar_pago(
    db: Session,
    pago_id: int,
    org_id: int,
    usuario_id: Optional[int],
    concepto: str,
    cliente_nombre: str,
    monto: float,
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
        print(f"[motor_contable] Warning pago {pago_id}: {ex}")


def registrar_gasto(
    db: Session,
    gasto_id: int,
    org_id: int,
    usuario_id: Optional[int],
    concepto: str,
    monto: float,
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
        print(f"[motor_contable] Warning gasto {gasto_id}: {ex}")


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
    comision_pct: float = 0.0,
) -> None:
    """Asiento al conciliar una planilla: Pasivo Corriente (D) / Cliente (H).
    Si comision_pct > 0 genera un segundo asiento de comisión.
    En re-conciliación (solo_pendientes), actualiza el monto si ya existe."""
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
                    linea.debe = total; linea.haber = 0.0
                else:
                    linea.haber = total; linea.debe = 0.0
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
                                linea.debe = comision_monto; linea.haber = 0.0
                            else:
                                linea.haber = comision_monto; linea.debe = 0.0
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
        print(f"[motor_contable] Warning planilla {planilla_id}: {ex}")
