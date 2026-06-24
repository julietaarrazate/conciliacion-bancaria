"""Servicio de liquidación interna de sueldos + proyección del F931.

Calcula la liquidación de un período (mes) para todos los empleados activos de
la organización: sueldo bruto (+ SAC proporcional), aportes del empleado,
contribuciones del empleador y sueldo neto. Los totales agregados son la base
del F931 (total remuneraciones, total aportes, total contribuciones).

Esto NO sustituye un sistema de liquidación de sueldos homologado ni reemplaza
el SUSS/AFIP — es una herramienta de gestión interna del estudio.

SAC (aguinaldo) — SIMPLIFICACIÓN DOCUMENTADA:
  El SAC legal se devenga semestralmente (la mejor remuneración del semestre / 2,
  proporcional a los meses trabajados). Aquí se usa una aproximación mensual:
  sac_proporcional = sueldo_bruto_base / 12. Esto provisiona el aguinaldo mes a
  mes (un doceavo del bruto cada mes), que es la práctica contable habitual para
  estimar el costo laboral mensual. NO es el cálculo legal exacto del recibo de
  junio/diciembre — es una provisión interna. El SAC integra la base imponible de
  aportes/contribuciones (se calcula sobre bruto = sueldo + sac_proporcional).

Todos los cálculos usan Decimal (las columnas Numeric ya devuelven Decimal).
"""

from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.sueldos import (
    ConfigSueldos,
    Empleado,
    CategoriaConvenio,
    EscalaGanancias,
    LiquidacionSueldoPeriodo,
    DetalleLiquidacionEmpleado,
)
from app.services.decimal_utils import to_decimal as _D
from app.services.tz import now_art

logger = logging.getLogger(__name__)

_DOS = Decimal("0.01")
_DOCE = Decimal("12")

# Valores de referencia 2024 (esquema nacional de seguridad social, ley 27.541).
# Se siembran como DEFAULT EDITABLE — verificar vigencia con el contador/AFIP.
# ART = 0 obligatorio (varía 100% por la póliza contratada por cada empleador).
ALICUOTAS_REFERENCIA = {
    # Aportes del empleado (se descuentan del bruto)
    "aporte_jubilacion": Decimal("0.1100"),   # 11%
    "aporte_inssjp": Decimal("0.0300"),       # 3% (PAMI)
    "aporte_obra_social": Decimal("0.0300"),  # 3%
    # Contribuciones del empleador (las paga la empresa)
    "contrib_jubilacion": Decimal("0.1062"),
    "contrib_inssjp": Decimal("0.0150"),
    "contrib_obra_social": Decimal("0.0600"),
    "contrib_asig_fam": Decimal("0.0444"),
    "contrib_fondo_desempleo": Decimal("0.0089"),
    "alicuota_art": Decimal("0"),             # SIEMPRE 0 por default
}


class SueldosServiceError(Exception):
    """Error de negocio del servicio de sueldos (módulo apagado, período
    inválido, liquidación inmutable, etc.)."""


def _validar_periodo(periodo: str) -> None:
    try:
        anio_s, mes_s = periodo.split("-")
        anio, mes = int(anio_s), int(mes_s)
        if not (1 <= mes <= 12) or anio < 1900:
            raise ValueError
    except (ValueError, AttributeError):
        raise SueldosServiceError(
            f"Período inválido: {periodo!r}. Use formato 'YYYY-MM'."
        )


def get_o_crear_config(db: Session, organizacion_id: int) -> ConfigSueldos:
    """Devuelve la config de sueldos de la org; la crea (apagada, con alícuotas
    de referencia) si no existe. Idempotente."""
    cfg = (
        db.query(ConfigSueldos)
        .filter(ConfigSueldos.organizacion_id == organizacion_id)
        .first()
    )
    if cfg is None:
        cfg = ConfigSueldos(
            organizacion_id=organizacion_id,
            activo=False,
            **ALICUOTAS_REFERENCIA,
        )
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


def seed_config_sueldos(db: Session, organizacion_id: int) -> int:
    """Siembra una ConfigSueldos apagada (con alícuotas de referencia) si la org
    no tiene ninguna. Idempotente. Devuelve cuántas creó (0 o 1)."""
    ya = (
        db.query(ConfigSueldos)
        .filter(ConfigSueldos.organizacion_id == organizacion_id)
        .count()
    )
    if ya > 0:
        return 0
    db.add(ConfigSueldos(
        organizacion_id=organizacion_id,
        activo=False,
        **ALICUOTAS_REFERENCIA,
    ))
    db.commit()
    logger.info("ConfigSueldos sembrada (apagada) para org %s", organizacion_id)
    return 1


def _basico_empleado(db: Session, empleado: Empleado) -> Decimal:
    """Sueldo básico del empleado: su override si lo tiene, sino el de su
    categoría de convenio, sino 0."""
    if empleado.sueldo_basico is not None and _D(empleado.sueldo_basico) > 0:
        return _D(empleado.sueldo_basico)
    if empleado.categoria_id:
        cat = (
            db.query(CategoriaConvenio)
            .filter(CategoriaConvenio.id == empleado.categoria_id)
            .first()
        )
        if cat is not None:
            return _D(cat.sueldo_basico)
    return Decimal("0")


def _tasas_aporte(cfg: ConfigSueldos) -> Decimal:
    """Suma de alícuotas de APORTE del empleado."""
    return (
        _D(cfg.aporte_jubilacion)
        + _D(cfg.aporte_inssjp)
        + _D(cfg.aporte_obra_social)
    )


def _tasas_contribucion(cfg: ConfigSueldos) -> Decimal:
    """Suma de alícuotas de CONTRIBUCIÓN del empleador (incluye ART)."""
    return (
        _D(cfg.contrib_jubilacion)
        + _D(cfg.contrib_inssjp)
        + _D(cfg.contrib_obra_social)
        + _D(cfg.contrib_asig_fam)
        + _D(cfg.contrib_fondo_desempleo)
        + _D(cfg.alicuota_art)
    )


def _escala_ganancias(db: Session, organizacion_id: int) -> list[EscalaGanancias]:
    return (
        db.query(EscalaGanancias)
        .filter(EscalaGanancias.organizacion_id == organizacion_id)
        .order_by(EscalaGanancias.tramo_desde.asc())
        .all()
    )


def calcular_ganancias_4ta(
    bruto_mensual: Decimal,
    escala: list[EscalaGanancias],
    minimo_no_imponible: Decimal,
    deduccion_especial: Decimal,
    ganancias_activo: bool,
) -> Decimal:
    """Proyecta la retención mensual de Ganancias 4ta categoría.

    SIMPLIFICACIÓN DOCUMENTADA (mismo criterio que el SAC proporcional del
    módulo): la ganancia neta sujeta a impuesto se estima ANUALIZANDO el bruto
    mensual (×12) — una proyección simple que asume un sueldo estable todo el
    año. NO reproduce el cálculo legal exacto (que acumula remuneraciones reales
    mes a mes, con deducciones acumuladas y retenciones de meses previos) — es
    una herramienta de estimación interna, no una liquidación oficial de AFIP/ARCA.

    Fórmula:
      ganancia_neta_anual = bruto_mensual × 12 − minimo_no_imponible × 12
                             − deduccion_especial × 12
      Si ganancia_neta_anual <= 0 → retención = 0.
      Se busca el tramo de la escala donde tramo_desde <= ganancia_neta_anual
      (y ganancia_neta_anual < tramo_hasta, o tramo_hasta es NULL = último tramo).
      retencion_anual = monto_fijo + alicuota × (ganancia_neta_anual − tramo_desde)
      retencion_mensual = retencion_anual / 12

    Si ganancias_activo=False devuelve 0 SIN calcular nada — no rompe orgs que
    no activaron este cálculo. Si está activo pero la escala está vacía, también
    devuelve 0 (no hay tramos contra los que calcular) — el admin debe cargar la
    escala vigente de ARCA antes de que esto retenga algo.
    """
    if not ganancias_activo:
        return Decimal("0")
    if not escala:
        return Decimal("0")

    bruto_mensual = _D(bruto_mensual)
    minimo_no_imponible = _D(minimo_no_imponible)
    deduccion_especial = _D(deduccion_especial)

    ganancia_neta_anual = (
        bruto_mensual * _DOCE
        - minimo_no_imponible * _DOCE
        - deduccion_especial * _DOCE
    )
    if ganancia_neta_anual <= 0:
        return Decimal("0").quantize(_DOS)

    tramo_aplicable = None
    for tramo in escala:
        desde = _D(tramo.tramo_desde)
        hasta = _D(tramo.tramo_hasta) if tramo.tramo_hasta is not None else None
        if ganancia_neta_anual >= desde and (hasta is None or ganancia_neta_anual < hasta):
            tramo_aplicable = tramo
            break
    if tramo_aplicable is None:
        # ganancia_neta_anual por debajo del primer tramo_desde: sin retención.
        return Decimal("0").quantize(_DOS)

    excedente = ganancia_neta_anual - _D(tramo_aplicable.tramo_desde)
    retencion_anual = _D(tramo_aplicable.monto_fijo) + _D(tramo_aplicable.alicuota) * excedente
    retencion_mensual = (retencion_anual / _DOCE).quantize(_DOS)
    return max(retencion_mensual, Decimal("0"))


def calcular_liquidacion_periodo(
    db: Session, organizacion_id: int, periodo: str
) -> dict:
    """Calcula la liquidación del período (solo lectura, no persiste).

    Para cada empleado activo (no soft-deleted) de la org:
      bruto = sueldo_basico (override o de la categoría) + SAC proporcional (bruto_base/12)
      aportes      = bruto × Σ alícuotas de aporte (empleado)
      contribuciones = bruto × Σ alícuotas de contribución (empleador + ART)
      neto         = bruto − aportes

    Devuelve dict con el detalle por empleado + totales agregados (base del F931).
    Lanza SueldosServiceError si el módulo no está activo o el período es inválido.
    """
    _validar_periodo(periodo)

    cfg = (
        db.query(ConfigSueldos)
        .filter(ConfigSueldos.organizacion_id == organizacion_id)
        .first()
    )
    if cfg is None or not cfg.activo:
        raise SueldosServiceError(
            "El módulo de Sueldos no está activado para esta organización. "
            "Activalo en Config."
        )

    empleados = (
        db.query(Empleado)
        .filter(
            Empleado.organizacion_id == organizacion_id,
            Empleado.activo == True,        # noqa: E712
            Empleado.deleted_at.is_(None),
        )
        .order_by(Empleado.nombre.asc(), Empleado.id.asc())
        .all()
    )

    tasa_aporte = _tasas_aporte(cfg)
    tasa_contrib = _tasas_contribucion(cfg)
    escala_gan = _escala_ganancias(db, organizacion_id) if cfg.ganancias_activo else []

    detalle: list[dict] = []
    total_bruto = Decimal("0")
    total_aportes = Decimal("0")
    total_contribuciones = Decimal("0")
    total_neto = Decimal("0")
    total_retencion_ganancias = Decimal("0")

    for emp in empleados:
        basico = _basico_empleado(db, emp).quantize(_DOS)
        # SAC proporcional: provisión mensual = básico / 12 (ver doc del módulo).
        sac = (basico / _DOCE).quantize(_DOS)
        bruto = (basico + sac).quantize(_DOS)
        aportes = (bruto * tasa_aporte).quantize(_DOS)
        contribuciones = (bruto * tasa_contrib).quantize(_DOS)
        retencion_ganancias = calcular_ganancias_4ta(
            bruto, escala_gan, _D(cfg.minimo_no_imponible), _D(cfg.deduccion_especial),
            cfg.ganancias_activo,
        )
        neto = (bruto - aportes - retencion_ganancias).quantize(_DOS)

        total_bruto += bruto
        total_aportes += aportes
        total_contribuciones += contribuciones
        total_neto += neto
        total_retencion_ganancias += retencion_ganancias

        desglose = {
            "sueldo_basico": float(basico),
            "sac_proporcional": float(sac),
            "aportes": {
                "jubilacion": float((bruto * _D(cfg.aporte_jubilacion)).quantize(_DOS)),
                "inssjp": float((bruto * _D(cfg.aporte_inssjp)).quantize(_DOS)),
                "obra_social": float((bruto * _D(cfg.aporte_obra_social)).quantize(_DOS)),
            },
            "contribuciones": {
                "jubilacion": float((bruto * _D(cfg.contrib_jubilacion)).quantize(_DOS)),
                "inssjp": float((bruto * _D(cfg.contrib_inssjp)).quantize(_DOS)),
                "obra_social": float((bruto * _D(cfg.contrib_obra_social)).quantize(_DOS)),
                "asig_fam": float((bruto * _D(cfg.contrib_asig_fam)).quantize(_DOS)),
                "fondo_desempleo": float((bruto * _D(cfg.contrib_fondo_desempleo)).quantize(_DOS)),
                "art": float((bruto * _D(cfg.alicuota_art)).quantize(_DOS)),
            },
            "retencion_ganancias": float(retencion_ganancias),
        }

        detalle.append({
            "empleado_id": emp.id,
            "nombre": emp.nombre,
            "cuil": emp.cuil,
            "sueldo_bruto": bruto,
            "sac_proporcional": sac,
            "total_aportes": aportes,
            "total_contribuciones": contribuciones,
            "retencion_ganancias": retencion_ganancias,
            "sueldo_neto": neto,
            "detalle_json": desglose,
        })

    return {
        "periodo": periodo,
        "cantidad_empleados": len(empleados),
        "total_bruto": total_bruto.quantize(_DOS),
        "total_aportes": total_aportes.quantize(_DOS),
        "total_contribuciones": total_contribuciones.quantize(_DOS),
        "total_retencion_ganancias": total_retencion_ganancias.quantize(_DOS),
        "total_neto": total_neto.quantize(_DOS),
        # base del F931
        "f931": {
            "total_remuneraciones": float(total_bruto.quantize(_DOS)),
            "total_aportes": float(total_aportes.quantize(_DOS)),
            "total_contribuciones": float(total_contribuciones.quantize(_DOS)),
        },
        "detalle": detalle,
    }


def guardar_o_actualizar_liquidacion(
    db: Session, organizacion_id: int, periodo: str
) -> LiquidacionSueldoPeriodo:
    """Upsert del snapshot de liquidación del período.

    Si ya existe en estado 'borrador' o 'aprobado' → recalcula y reemplaza los
    detalles. Si está 'presentado' → NO lo pisa, devuelve el existente intacto."""
    calc = calcular_liquidacion_periodo(db, organizacion_id, periodo)

    existente = (
        db.query(LiquidacionSueldoPeriodo)
        .filter(
            LiquidacionSueldoPeriodo.organizacion_id == organizacion_id,
            LiquidacionSueldoPeriodo.periodo == periodo,
        )
        .first()
    )

    if existente is not None and existente.estado == "presentado":
        return existente  # inmutable

    if existente is None:
        existente = LiquidacionSueldoPeriodo(
            organizacion_id=organizacion_id,
            periodo=periodo,
            estado="borrador",
        )
        db.add(existente)
        db.flush()
    else:
        # limpiar detalles previos para reemplazarlos
        db.query(DetalleLiquidacionEmpleado).filter(
            DetalleLiquidacionEmpleado.liquidacion_periodo_id == existente.id
        ).delete(synchronize_session=False)

    existente.total_bruto = calc["total_bruto"]
    existente.total_aportes = calc["total_aportes"]
    existente.total_contribuciones = calc["total_contribuciones"]
    existente.total_neto = calc["total_neto"]

    for d in calc["detalle"]:
        db.add(DetalleLiquidacionEmpleado(
            liquidacion_periodo_id=existente.id,
            empleado_id=d["empleado_id"],
            sueldo_bruto=d["sueldo_bruto"],
            sac_proporcional=d["sac_proporcional"],
            total_aportes=d["total_aportes"],
            total_contribuciones=d["total_contribuciones"],
            sueldo_neto=d["sueldo_neto"],
            retencion_ganancias=d["retencion_ganancias"],
            detalle_json=d["detalle_json"],
        ))

    db.commit()
    db.refresh(existente)
    return existente


def aprobar_liquidacion(
    db: Session, organizacion_id: int, liquidacion_id: int, usuario_id: int | None
) -> LiquidacionSueldoPeriodo:
    """Aprueba una liquidación borrador y genera el asiento contable agrupado.

    Solo desde estado 'borrador'. Lanza SueldosServiceError si no existe, está en
    otro estado, o pertenece a otra org."""
    liq = (
        db.query(LiquidacionSueldoPeriodo)
        .filter(
            LiquidacionSueldoPeriodo.id == liquidacion_id,
            LiquidacionSueldoPeriodo.organizacion_id == organizacion_id,
        )
        .first()
    )
    if liq is None:
        raise SueldosServiceError("Liquidación no encontrada.")
    if liq.estado != "borrador":
        raise SueldosServiceError(
            f"Solo se puede aprobar una liquidación en borrador (estado actual: {liq.estado})."
        )

    liq.estado = "aprobado"
    liq.fecha_aprobacion = now_art()
    db.commit()
    db.refresh(liq)

    # Asiento contable agrupado (no revierte la aprobación si falla — try interno)
    from app.services.motor_contable import registrar_liquidacion_sueldos
    registrar_liquidacion_sueldos(
        db=db,
        liquidacion_id=liq.id,
        org_id=organizacion_id,
        usuario_id=usuario_id,
        periodo=liq.periodo,
        total_bruto=_D(liq.total_bruto),
        total_aportes=_D(liq.total_aportes),
        total_contribuciones=_D(liq.total_contribuciones),
        total_neto=_D(liq.total_neto),
    )
    db.refresh(liq)
    return liq


def marcar_presentada(
    db: Session, organizacion_id: int, liquidacion_id: int
) -> LiquidacionSueldoPeriodo:
    """Marca la liquidación como presentada (F931 enviado). La deja inmutable.

    Debe estar aprobada. Lanza SueldosServiceError si no existe o está en
    estado incompatible."""
    liq = (
        db.query(LiquidacionSueldoPeriodo)
        .filter(
            LiquidacionSueldoPeriodo.id == liquidacion_id,
            LiquidacionSueldoPeriodo.organizacion_id == organizacion_id,
        )
        .first()
    )
    if liq is None:
        raise SueldosServiceError("Liquidación no encontrada.")
    if liq.estado not in ("aprobado", "presentado"):
        raise SueldosServiceError(
            "Solo se puede marcar como presentada una liquidación aprobada."
        )
    liq.estado = "presentado"
    liq.fecha_presentacion = now_art()
    db.commit()
    db.refresh(liq)
    return liq
