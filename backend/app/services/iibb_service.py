"""Servicio de proyección de Ingresos Brutos (IIBB) y Convenio Multilateral.

Calcula una PROYECCIÓN del impuesto a los Ingresos Brutos de un período (mes) a
partir de los ingresos contables reconocidos en ese período, aplicando las
alícuotas que la organización configura por jurisdicción.

Esto NO es una DDJJ oficial — es una herramienta de estimación interna. Los
coeficientes de distribución del Convenio Multilateral son un % editable por la
org (no se recalculan desde ingresos/gastos del ejercicio anterior).

Modos:
  - simple: ingreso_total × alícuota de la jurisdicción única.
  - convenio_multilateral: ingreso_total se reparte según el
    `coeficiente_distribucion` de cada jurisdicción activa y a cada porción se le
    aplica SU PROPIA alícuota. Si los coeficientes no suman 1.0 (100%), el cálculo
    NO se bloquea (es interno) pero se devuelve un warning explícito.

Criterio de ingreso (idéntico a iva_service.py / monotributo_service.py):
cuentas de tipo `resultado` cuyo código empieza con "3-1", sumando (haber - debe)
de sus líneas de asiento del período.

Todos los cálculos usan Decimal (las columnas Numeric ya devuelven Decimal).
"""

from __future__ import annotations

import calendar
import logging
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.contabilidad import Asiento, AsientoDetalle, PlanCuenta
from app.models.iibb import IIBBConfig, JurisdiccionIIBB, ProyeccionIIBB
from app.services.decimal_utils import to_decimal as _D
from app.services.tz import now_art

logger = logging.getLogger(__name__)

_DOS = Decimal("0.01")
_UNO = Decimal("1")
# Tolerancia para considerar que los coeficientes suman 100%.
_TOL_COEF = Decimal("0.0001")


class IIBBServiceError(Exception):
    """Error de negocio del servicio de IIBB (período inválido, módulo apagado,
    sin jurisdicción configurada, etc.)."""


def _rango_periodo(periodo: str) -> tuple[date, date]:
    """Convierte 'YYYY-MM' en (primer_dia, ultimo_dia) del mes."""
    try:
        anio_s, mes_s = periodo.split("-")
        anio, mes = int(anio_s), int(mes_s)
        if not (1 <= mes <= 12):
            raise ValueError
    except (ValueError, AttributeError):
        raise IIBBServiceError(f"Período inválido: {periodo!r}. Use formato 'YYYY-MM'.")
    ultimo = calendar.monthrange(anio, mes)[1]
    return date(anio, mes, 1), date(anio, mes, ultimo)


def calcular_ingreso_periodo(
    db: Session, organizacion_id: int, desde: date, hasta: date
) -> Decimal:
    """Suma los ingresos (haber - debe) de cuentas resultado "3-1*" en el rango."""
    filas = (
        db.query(AsientoDetalle.debe, AsientoDetalle.haber)
        .join(Asiento, AsientoDetalle.asiento_id == Asiento.id)
        .join(PlanCuenta, AsientoDetalle.cuenta_id == PlanCuenta.id)
        .filter(
            Asiento.organizacion_id == organizacion_id,
            Asiento.fecha >= desde,
            Asiento.fecha <= hasta,
            PlanCuenta.tipo == "resultado",
            PlanCuenta.codigo.startswith("3-1"),
        )
        .all()
    )
    total = Decimal("0")
    for debe, haber in filas:
        total += _D(haber) - _D(debe)
    return total.quantize(_DOS)


def calcular_proyeccion_iibb(
    db: Session, organizacion_id: int, periodo: str
) -> dict:
    """Calcula la proyección de IIBB del período (solo lectura, no persiste).

    Requiere IIBBConfig con activo=True. Devuelve dict con ingreso_total,
    impuesto_total, el detalle por jurisdicción, el modo, la suma de coeficientes
    y un warning si en convenio_multilateral no suman 100%.

    Lanza IIBBServiceError si el módulo no está activo, el período es inválido o
    falta configuración (jurisdicción única en simple / jurisdicciones en CM).
    """
    config = (
        db.query(IIBBConfig)
        .filter(IIBBConfig.organizacion_id == organizacion_id)
        .first()
    )
    if config is None or not config.activo:
        raise IIBBServiceError(
            "El módulo de Ingresos Brutos no está activado para esta organización. "
            "Activalo en Config."
        )

    desde, hasta = _rango_periodo(periodo)
    ingreso_total = calcular_ingreso_periodo(db, organizacion_id, desde, hasta)

    modo = config.modo or "simple"
    detalle: list[dict] = []
    impuesto_total = Decimal("0")
    suma_coeficientes = Decimal("0")
    warning: str | None = None

    if modo == "simple":
        if not config.jurisdiccion_unica_id:
            raise IIBBServiceError(
                "El modo 'simple' requiere una jurisdicción única configurada. "
                "Elegila en Config."
            )
        jur = (
            db.query(JurisdiccionIIBB)
            .filter(
                JurisdiccionIIBB.id == config.jurisdiccion_unica_id,
                JurisdiccionIIBB.organizacion_id == organizacion_id,
            )
            .first()
        )
        if jur is None:
            raise IIBBServiceError(
                "La jurisdicción única configurada no existe. Revisá Config."
            )
        alicuota = _D(jur.alicuota)
        impuesto = (ingreso_total * alicuota).quantize(_DOS)
        impuesto_total = impuesto
        detalle.append({
            "jurisdiccion_id": jur.id,
            "nombre": jur.nombre,
            "coeficiente": float(_UNO),
            "ingreso_atribuido": float(ingreso_total),
            "alicuota": float(alicuota),
            "impuesto": float(impuesto),
        })
        suma_coeficientes = _UNO

    else:  # convenio_multilateral
        jurisdicciones = (
            db.query(JurisdiccionIIBB)
            .filter(
                JurisdiccionIIBB.organizacion_id == organizacion_id,
                JurisdiccionIIBB.activa == True,  # noqa: E712
            )
            .order_by(JurisdiccionIIBB.orden.asc(), JurisdiccionIIBB.id.asc())
            .all()
        )
        if not jurisdicciones:
            raise IIBBServiceError(
                "El modo 'convenio_multilateral' requiere al menos una jurisdicción "
                "activa configurada. Agregalas en Config."
            )
        for jur in jurisdicciones:
            coef = _D(jur.coeficiente_distribucion)
            alicuota = _D(jur.alicuota)
            suma_coeficientes += coef
            ingreso_atribuido = (ingreso_total * coef).quantize(_DOS)
            impuesto = (ingreso_atribuido * alicuota).quantize(_DOS)
            impuesto_total += impuesto
            detalle.append({
                "jurisdiccion_id": jur.id,
                "nombre": jur.nombre,
                "coeficiente": float(coef),
                "ingreso_atribuido": float(ingreso_atribuido),
                "alicuota": float(alicuota),
                "impuesto": float(impuesto),
            })

        if abs(suma_coeficientes - _UNO) > _TOL_COEF:
            pct = (suma_coeficientes * Decimal("100")).quantize(_DOS)
            warning = (
                f"Los coeficientes de distribución suman {pct}%, no 100%. "
                "Corregilos en Config para que la proyección sea correcta."
            )

    impuesto_total = impuesto_total.quantize(_DOS)

    return {
        "periodo": periodo,
        "modo": modo,
        "ingreso_total": ingreso_total,
        "impuesto_total": impuesto_total,
        "suma_coeficientes": suma_coeficientes.quantize(Decimal("0.0001")),
        "warning": warning,
        "detalle": detalle,
    }


def guardar_o_actualizar_proyeccion(
    db: Session, organizacion_id: int, periodo: str
) -> ProyeccionIIBB:
    """Upsert del snapshot de proyección de IIBB.

    Si ya existe y está en estado 'proyectado' → recalcula y actualiza.
    Si ya existe y está 'presentado' → NO lo pisa, devuelve el existente intacto."""
    calc = calcular_proyeccion_iibb(db, organizacion_id, periodo)

    existente = (
        db.query(ProyeccionIIBB)
        .filter(
            ProyeccionIIBB.organizacion_id == organizacion_id,
            ProyeccionIIBB.periodo == periodo,
        )
        .first()
    )

    if existente is not None and existente.estado == "presentado":
        return existente  # ya presentada — no se recalcula ni se pisa

    if existente is None:
        existente = ProyeccionIIBB(
            organizacion_id=organizacion_id,
            periodo=periodo,
            estado="proyectado",
        )
        db.add(existente)

    existente.ingreso_total = calc["ingreso_total"]
    existente.impuesto_total = calc["impuesto_total"]
    existente.detalle_por_jurisdiccion = calc["detalle"]
    db.commit()
    db.refresh(existente)
    return existente


def marcar_presentada(
    db: Session, organizacion_id: int, periodo: str
) -> ProyeccionIIBB:
    """Marca la proyección del período como presentada (DDJJ enviada).

    Debe existir la proyección (calcularse primero). Lanza IIBBServiceError si no."""
    p = (
        db.query(ProyeccionIIBB)
        .filter(
            ProyeccionIIBB.organizacion_id == organizacion_id,
            ProyeccionIIBB.periodo == periodo,
        )
        .first()
    )
    if p is None:
        raise IIBBServiceError(
            f"No existe una proyección para el período {periodo}. "
            "Calculá la proyección antes de marcarla como presentada."
        )
    p.estado = "presentado"
    p.fecha_presentacion = now_art()
    db.commit()
    db.refresh(p)
    return p


# ── Seed de jurisdicción ilustrativa ──────────────────────────────

def seed_iibb_jurisdiccion(db: Session, organizacion_id: int) -> int:
    """Siembra UNA jurisdicción ilustrativa (CABA, alícuota 0) si la org no tiene
    ninguna. Idempotente. Devuelve cuántas creó (0 o 1).

    NO se siembran alícuotas reales — cada jurisdicción tiene su propio régimen y
    cambian con frecuencia. El admin debe completar/verificar todo contra AGIP,
    ARBA o el organismo de cada provincia (ver nota en models/iibb.py)."""
    ya = (
        db.query(JurisdiccionIIBB)
        .filter(JurisdiccionIIBB.organizacion_id == organizacion_id)
        .count()
    )
    if ya > 0:
        return 0

    db.add(JurisdiccionIIBB(
        organizacion_id=organizacion_id,
        nombre="CABA (ejemplo — completar)",
        alicuota=Decimal("0"),
        coeficiente_distribucion=Decimal("0"),
        activa=True,
        orden=1,
    ))
    db.commit()
    logger.info("Jurisdicción IIBB ilustrativa sembrada para org %s", organizacion_id)
    return 1
