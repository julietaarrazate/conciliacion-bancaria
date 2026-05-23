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
) -> None:
    """Asiento al conciliar una planilla: Pasivo Corriente (D) / Cliente (H).
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
            # Actualizar lineas existentes con el nuevo total
            for linea in existente.lineas:
                if linea.debe > 0:
                    linea.debe = total
                if linea.haber > 0:
                    linea.haber = total
            existente.fecha = fecha_acred
            db.commit()
            return

        if existente:
            return  # primera conciliación ya registrada, no duplicar

        _crear_asiento(
            db=db,
            regla=regla,
            fecha=fecha_acred,
            descripcion=f"{cliente_nombre} — {nombre_archivo}",
            modulo="planilla",
            referencia_id=planilla_id,
            org_id=org_id,
            usuario_id=usuario_id,
            monto=total,
        )
        db.commit()
    except Exception as ex:
        db.rollback()
        print(f"[motor_contable] Warning planilla {planilla_id}: {ex}")
