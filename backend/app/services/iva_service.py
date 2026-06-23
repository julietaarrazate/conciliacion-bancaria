"""Servicio de proyección de IVA y DDJJ.

Calcula una PROYECCIÓN del IVA de un período a partir de los asientos contables
cruzados con la `tasa_iva` configurada en cada cuenta del plan.

Cuadra no emite facturas, así que el Débito Fiscal NO es un dato real
contabilizado: es una proyección sobre lo que el sistema reconoce como ingreso
gravado (cuentas de tipo `resultado` de ingreso con `tasa_iva` seteada, mirando
el HABER de sus líneas). El Crédito Fiscal combina:
  - proyectado: gastos gravados (cuentas con `tasa_iva` que reciben DEBE) × tasa.
  - real: lo ya contabilizado en la cuenta 1-1-2-4 IVA Crédito Fiscal (DEBE),
    p. ej. de las liquidaciones de tarjetas.

Saldo = débito_fiscal − crédito_fiscal. Positivo = a pagar a ARCA;
negativo = saldo a favor.

Todos los cálculos usan Decimal (las columnas Numeric ya devuelven Decimal).
"""

from __future__ import annotations

import calendar
import logging
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.contabilidad import Asiento, AsientoDetalle, PlanCuenta
from app.models.proyeccion_iva import ProyeccionIva
from app.services.tz import now_art

logger = logging.getLogger(__name__)

# Cuenta hoja donde se contabiliza el IVA crédito fiscal REAL (liquidaciones, etc.)
_CTA_IVA_CREDITO_REAL = "1-1-2-4"

_DOS = Decimal("0.01")


class IvaServiceError(Exception):
    """Error de negocio del servicio de IVA (período inexistente, etc.)."""


def _rango_periodo(periodo: str) -> tuple[date, date]:
    """Convierte 'YYYY-MM' en (primer_dia, ultimo_dia) del mes."""
    try:
        anio_s, mes_s = periodo.split("-")
        anio, mes = int(anio_s), int(mes_s)
        if not (1 <= mes <= 12):
            raise ValueError
    except (ValueError, AttributeError):
        raise IvaServiceError(f"Período inválido: {periodo!r}. Use formato 'YYYY-MM'.")
    ultimo = calendar.monthrange(anio, mes)[1]
    return date(anio, mes, 1), date(anio, mes, ultimo)


def _D(v) -> Decimal:
    if v is None:
        return Decimal("0")
    if isinstance(v, Decimal):
        return v
    return Decimal(str(v))


def calcular_proyeccion_iva(db: Session, organizacion_id: int, periodo: str) -> dict:
    """Calcula la proyección de IVA del período (solo lectura, no persiste).

    Devuelve dict con débito/crédito fiscal proyectado + crédito fiscal real,
    saldo, y el desglose por cuenta."""
    desde, hasta = _rango_periodo(periodo)

    # Líneas de asiento del período de cuentas con tasa_iva configurada.
    filas = (
        db.query(
            AsientoDetalle.cuenta_id,
            PlanCuenta.codigo,
            PlanCuenta.nombre,
            PlanCuenta.tipo,
            PlanCuenta.tasa_iva,
            AsientoDetalle.debe,
            AsientoDetalle.haber,
        )
        .join(Asiento, AsientoDetalle.asiento_id == Asiento.id)
        .join(PlanCuenta, AsientoDetalle.cuenta_id == PlanCuenta.id)
        .filter(
            Asiento.organizacion_id == organizacion_id,
            Asiento.fecha >= desde,
            Asiento.fecha <= hasta,
            PlanCuenta.tasa_iva.isnot(None),
        )
        .all()
    )

    # Agregación por cuenta: base imponible (debe vs haber) + IVA.
    # Ingresos (tipo resultado): el HABER es la venta gravada → débito fiscal.
    # Resto (gasto / otras con tasa que reciben DEBE): el DEBE es compra gravada → crédito.
    por_cuenta: dict[int, dict] = {}
    debito_fiscal = Decimal("0")
    credito_proyectado = Decimal("0")

    for cuenta_id, codigo, nombre, tipo, tasa_iva, debe, haber in filas:
        tasa = _D(tasa_iva)
        debe_d = _D(debe)
        haber_d = _D(haber)
        es_ingreso = (tipo == "resultado" and codigo.startswith("3-1"))

        if es_ingreso:
            base = haber_d - debe_d  # neto del ingreso reconocido en el período
            iva = (base * tasa).quantize(_DOS)
            debito_fiscal += iva
        else:
            base = debe_d - haber_d  # neto del gasto/compra gravada
            iva = (base * tasa).quantize(_DOS)
            credito_proyectado += iva

        if cuenta_id not in por_cuenta:
            por_cuenta[cuenta_id] = {
                "cuenta_id": cuenta_id,
                "codigo": codigo,
                "nombre": nombre,
                "tipo": "ingreso" if es_ingreso else "gasto",
                "tasa_iva": tasa,
                "base_imponible": Decimal("0"),
                "iva": Decimal("0"),
            }
        por_cuenta[cuenta_id]["base_imponible"] += base
        por_cuenta[cuenta_id]["iva"] += iva

    # Crédito fiscal REAL ya contabilizado en 1-1-2-4 (DEBE − HABER) del período.
    credito_real = Decimal("0")
    cta_real = (
        db.query(PlanCuenta)
        .filter(
            PlanCuenta.codigo == _CTA_IVA_CREDITO_REAL,
            PlanCuenta.organizacion_id == organizacion_id,
        )
        .first()
    )
    if cta_real is not None:
        reales = (
            db.query(AsientoDetalle.debe, AsientoDetalle.haber)
            .join(Asiento, AsientoDetalle.asiento_id == Asiento.id)
            .filter(
                Asiento.organizacion_id == organizacion_id,
                Asiento.fecha >= desde,
                Asiento.fecha <= hasta,
                AsientoDetalle.cuenta_id == cta_real.id,
            )
            .all()
        )
        for debe, haber in reales:
            credito_real += _D(debe) - _D(haber)
        credito_real = credito_real.quantize(_DOS)

    debito_fiscal = debito_fiscal.quantize(_DOS)
    credito_proyectado = credito_proyectado.quantize(_DOS)
    credito_fiscal = (credito_proyectado + credito_real).quantize(_DOS)
    saldo = (debito_fiscal - credito_fiscal).quantize(_DOS)

    detalle = [
        {
            "cuenta_id": d["cuenta_id"],
            "codigo": d["codigo"],
            "nombre": d["nombre"],
            "tipo": d["tipo"],
            "tasa_iva": float(d["tasa_iva"]),
            "base_imponible": float(d["base_imponible"].quantize(_DOS)),
            "iva": float(d["iva"].quantize(_DOS)),
        }
        for d in sorted(por_cuenta.values(), key=lambda x: x["codigo"])
    ]

    return {
        "periodo": periodo,
        "debito_fiscal": debito_fiscal,
        "credito_fiscal": credito_fiscal,
        "credito_fiscal_real": credito_real,
        "credito_fiscal_proyectado": credito_proyectado,
        "saldo": saldo,
        "detalle": detalle,
    }


def guardar_o_actualizar_proyeccion(
    db: Session, organizacion_id: int, periodo: str
) -> ProyeccionIva:
    """Upsert del snapshot de proyección.

    Si ya existe y está en estado 'proyectado' → recalcula y actualiza.
    Si ya existe y está 'presentado' → NO lo pisa, devuelve el existente intacto."""
    calc = calcular_proyeccion_iva(db, organizacion_id, periodo)

    existente = (
        db.query(ProyeccionIva)
        .filter(
            ProyeccionIva.organizacion_id == organizacion_id,
            ProyeccionIva.periodo == periodo,
        )
        .first()
    )

    if existente is not None and existente.estado == "presentado":
        return existente  # ya presentada — no se recalcula ni se pisa

    if existente is None:
        existente = ProyeccionIva(
            organizacion_id=organizacion_id,
            periodo=periodo,
            estado="proyectado",
        )
        db.add(existente)

    existente.debito_fiscal = calc["debito_fiscal"]
    existente.credito_fiscal = calc["credito_fiscal"]
    existente.saldo = calc["saldo"]
    existente.detalle = calc["detalle"]
    db.commit()
    db.refresh(existente)
    return existente


def marcar_presentada(db: Session, organizacion_id: int, periodo: str) -> ProyeccionIva:
    """Marca la proyección del período como presentada (DDJJ enviada a ARCA).

    Debe existir la proyección (calcularse primero). Lanza IvaServiceError si no."""
    p = (
        db.query(ProyeccionIva)
        .filter(
            ProyeccionIva.organizacion_id == organizacion_id,
            ProyeccionIva.periodo == periodo,
        )
        .first()
    )
    if p is None:
        raise IvaServiceError(
            f"No existe una proyección para el período {periodo}. "
            "Calculá la proyección antes de marcarla como presentada."
        )
    p.estado = "presentado"
    p.fecha_presentacion = now_art()
    db.commit()
    db.refresh(p)
    return p
