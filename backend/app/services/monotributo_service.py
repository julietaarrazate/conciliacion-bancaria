"""Servicio de Control Semestral del Monotributo.

Herramienta de control/alerta INTERNA: proyecta los ingresos de los últimos 12
meses de la organización (a partir de los asientos contables ya registrados) y
los compara contra las escalas de categorías del Monotributo de ARCA. NO presenta
ninguna declaración oficial — sirve para que el estudio anticipe si un cliente (o
la propia organización) necesita recategorizarse antes de la fecha límite de ARCA.

Recategorización: cada semestre (cortes 30/jun y 31/dic) se comparan los ingresos
brutos de los ÚLTIMOS 12 MESES terminados en la fecha de corte contra los topes de
cada categoría:
  - S1 → corte 30/jun/YYYY → ventana [1/jul/(YYYY-1), 30/jun/YYYY]
  - S2 → corte 31/dic/YYYY → ventana [1/ene/YYYY, 31/dic/YYYY]

Ingresos: mismo criterio "es_ingreso" que iva_service.py — cuentas de tipo
`resultado` cuyo código empieza con "3-1", sumando (haber - debe) de sus líneas.

Todos los cálculos usan Decimal (las columnas Numeric ya devuelven Decimal).
"""

from __future__ import annotations

import calendar
import logging
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.contabilidad import Asiento, AsientoDetalle, PlanCuenta
from app.models.monotributo import (
    CategoriaMonotributo, MonotributoConfig, ControlMonotributo,
)
from app.services.tz import now_art

logger = logging.getLogger(__name__)

_DOS = Decimal("0.01")


class MonotributoServiceError(Exception):
    """Error de negocio del servicio de Monotributo (período inválido, módulo
    apagado, sin categorías configuradas, etc.)."""


def _D(v) -> Decimal:
    if v is None:
        return Decimal("0")
    if isinstance(v, Decimal):
        return v
    return Decimal(str(v))


def _rango_periodo(periodo: str) -> tuple[date, date]:
    """Convierte 'YYYY-S1'/'YYYY-S2' en (desde, fecha_corte) de la ventana de los
    ÚLTIMOS 12 MESES terminados en el corte del semestre.

    - "YYYY-S1" → corte 30/jun/YYYY → ventana [1/jul/(YYYY-1), 30/jun/YYYY]
    - "YYYY-S2" → corte 31/dic/YYYY → ventana [1/ene/YYYY, 31/dic/YYYY]

    Lanza MonotributoServiceError si el formato es inválido.
    """
    try:
        anio_s, sem = periodo.split("-")
        anio = int(anio_s)
        sem = sem.upper()
        if sem not in ("S1", "S2"):
            raise ValueError
    except (ValueError, AttributeError):
        raise MonotributoServiceError(
            f"Período inválido: {periodo!r}. Use formato 'YYYY-S1' o 'YYYY-S2'."
        )

    if sem == "S1":
        fecha_corte = date(anio, 6, 30)
        desde = date(anio - 1, 7, 1)
    else:  # S2
        fecha_corte = date(anio, 12, 31)
        desde = date(anio, 1, 1)
    return desde, fecha_corte


def calcular_ingresos_12m(
    db: Session, organizacion_id: int, desde: date, hasta: date
) -> tuple[Decimal, list[dict]]:
    """Suma los ingresos (haber - debe) de cuentas resultado "3-1*" en la ventana,
    agrupados por mes para el detalle.

    Devuelve (total: Decimal, detalle_mensual: [{"mes": "YYYY-MM", "ingresos": float}]).
    """
    filas = (
        db.query(
            Asiento.fecha,
            AsientoDetalle.debe,
            AsientoDetalle.haber,
        )
        .join(AsientoDetalle, AsientoDetalle.asiento_id == Asiento.id)
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
    por_mes: dict[str, Decimal] = {}
    for fecha, debe, haber in filas:
        monto = _D(haber) - _D(debe)
        total += monto
        mes_key = f"{fecha.year:04d}-{fecha.month:02d}"
        por_mes[mes_key] = por_mes.get(mes_key, Decimal("0")) + monto

    total = total.quantize(_DOS)
    detalle = [
        {"mes": mes, "ingresos": float(por_mes[mes].quantize(_DOS))}
        for mes in sorted(por_mes.keys())
    ]
    return total, detalle


def evaluar_categoria(
    db: Session, organizacion_id: int, tipo_actividad: str, ingresos_12m: Decimal
) -> tuple[str | None, Decimal, bool]:
    """Evalúa qué categoría corresponde a un nivel de ingresos.

    Devuelve (categoria_sugerida, limite_de_esa_categoria, excede):
      - categoria_sugerida = la de menor `orden` cuyo limite_anual >= ingresos_12m.
      - si los ingresos superan el límite de TODAS las categorías → se devuelve la
        más alta y excede=True (superó el tope del régimen).

    Lanza MonotributoServiceError si la org no tiene categorías de ese tipo.
    """
    cats = (
        db.query(CategoriaMonotributo)
        .filter(
            CategoriaMonotributo.organizacion_id == organizacion_id,
            CategoriaMonotributo.tipo_actividad == tipo_actividad,
        )
        .order_by(CategoriaMonotributo.orden.asc())
        .all()
    )
    if not cats:
        raise MonotributoServiceError(
            f"No hay categorías de Monotributo configuradas para la actividad "
            f"'{tipo_actividad}'. Configurálas en la pestaña Config."
        )

    ingresos = _D(ingresos_12m)
    for c in cats:
        if ingresos <= _D(c.limite_anual):
            return c.categoria, _D(c.limite_anual), False

    # Supera el límite de todas las categorías → la más alta, excede.
    ultima = cats[-1]
    return ultima.categoria, _D(ultima.limite_anual), True


def _limite_de_categoria(
    db: Session, organizacion_id: int, tipo_actividad: str, categoria: str | None
) -> Decimal:
    """Límite anual de una categoría puntual (0 si no se encuentra / sin categoría)."""
    if not categoria:
        return Decimal("0")
    c = (
        db.query(CategoriaMonotributo)
        .filter(
            CategoriaMonotributo.organizacion_id == organizacion_id,
            CategoriaMonotributo.tipo_actividad == tipo_actividad,
            CategoriaMonotributo.categoria == categoria,
        )
        .first()
    )
    return _D(c.limite_anual) if c else Decimal("0")


def calcular_control_semestral(
    db: Session, organizacion_id: int, periodo: str
) -> dict:
    """Calcula el control semestral del período (solo lectura, no persiste).

    Requiere que exista MonotributoConfig con activo=True. Lanza
    MonotributoServiceError si el módulo no está activo o el período es inválido.
    """
    config = (
        db.query(MonotributoConfig)
        .filter(MonotributoConfig.organizacion_id == organizacion_id)
        .first()
    )
    if config is None or not config.activo:
        raise MonotributoServiceError(
            "El módulo de Monotributo no está activado para esta organización. "
            "Activalo en Config."
        )

    desde, fecha_corte = _rango_periodo(periodo)
    tipo_actividad = config.tipo_actividad or "servicios"

    ingresos_12m, detalle = calcular_ingresos_12m(db, organizacion_id, desde, fecha_corte)
    categoria_sugerida, _limite_sug, excede = evaluar_categoria(
        db, organizacion_id, tipo_actividad, ingresos_12m
    )

    limite_actual = _limite_de_categoria(
        db, organizacion_id, tipo_actividad, config.categoria_actual
    )
    if limite_actual > 0:
        porcentaje_uso = (ingresos_12m / limite_actual * Decimal("100")).quantize(_DOS)
    else:
        porcentaje_uso = Decimal("0")

    return {
        "periodo": periodo,
        "fecha_corte": fecha_corte,
        "ingresos_12m": ingresos_12m,
        "categoria_actual": config.categoria_actual,
        "limite_categoria_actual": limite_actual,
        "porcentaje_uso": porcentaje_uso,
        "categoria_sugerida": categoria_sugerida,
        "excede": excede,
        "detalle": detalle,
    }


def guardar_o_actualizar_control(
    db: Session, organizacion_id: int, periodo: str
) -> ControlMonotributo:
    """Upsert del snapshot del control semestral.

    Si ya existe y está en estado 'pendiente' → recalcula y actualiza.
    Si ya existe y está 'revisado' → NO lo pisa, devuelve el existente intacto."""
    calc = calcular_control_semestral(db, organizacion_id, periodo)

    existente = (
        db.query(ControlMonotributo)
        .filter(
            ControlMonotributo.organizacion_id == organizacion_id,
            ControlMonotributo.periodo == periodo,
        )
        .first()
    )

    if existente is not None and existente.estado == "revisado":
        return existente  # ya revisado — no se recalcula ni se pisa

    if existente is None:
        existente = ControlMonotributo(
            organizacion_id=organizacion_id,
            periodo=periodo,
            estado="pendiente",
        )
        db.add(existente)

    existente.fecha_corte = calc["fecha_corte"]
    existente.ingresos_12m = calc["ingresos_12m"]
    existente.categoria_actual = calc["categoria_actual"]
    existente.limite_categoria_actual = calc["limite_categoria_actual"]
    existente.porcentaje_uso = calc["porcentaje_uso"]
    existente.categoria_sugerida = calc["categoria_sugerida"]
    existente.excede = calc["excede"]
    existente.detalle = calc["detalle"]
    db.commit()
    db.refresh(existente)
    return existente


def marcar_revisado(
    db: Session, organizacion_id: int, periodo: str
) -> ControlMonotributo:
    """Marca el control del período como revisado.

    Debe existir el control (calcularse primero). Lanza MonotributoServiceError si no."""
    c = (
        db.query(ControlMonotributo)
        .filter(
            ControlMonotributo.organizacion_id == organizacion_id,
            ControlMonotributo.periodo == periodo,
        )
        .first()
    )
    if c is None:
        raise MonotributoServiceError(
            f"No existe un control para el período {periodo}. "
            "Calculá el control antes de marcarlo como revisado."
        )
    c.estado = "revisado"
    c.fecha_revision = now_art()
    db.commit()
    db.refresh(c)
    return c


# ── Seed de categorías default ─────────────────────────────────────

# Escala vigente de ARCA desde 1/feb/2026 (actualización semestral por IPC
# acumulado del 2° semestre 2025, ~14,29%), válida hasta la próxima
# actualización de julio/agosto 2026. El límite de ingresos anuales por
# categoría es el MISMO para servicios y venta de bienes (lo que difiere
# entre actividades es la cuota mensual a pagar, no la escala de ingresos —
# este módulo no calcula esa cuota, solo controla el límite de facturación).
# Servicios: categorías A..H. Bienes (venta de cosas muebles): A..K.
#
# ⚠️ Estos valores vencen con la próxima actualización semestral (RG ARCA).
# Verificar y, si cambiaron, corregir vía PUT /monotributo/categorias/{id}
# o re-sembrar — son completamente editables, no están hardcodeados en lógica.
# Fuente: arca.gob.ar/monotributo/categorias.asp (consultado jun/2026).
#
# (categoria, limite_anual_vigente)
_LIMITES_VIGENTES = [
    ("A", "10277988.13"),
    ("B", "15058447.71"),
    ("C", "21113696.52"),
    ("D", "26212853.42"),
    ("E", "30833964.37"),
    ("F", "38642048.36"),
    ("G", "46211109.37"),
    ("H", "70113407.33"),
    ("I", "78479211.62"),
    ("J", "89872640.30"),
    ("K", "108357084.05"),
]
_CATS_SERVICIOS = [c for c in _LIMITES_VIGENTES if c[0] <= "H"]
_CATS_BIENES = _LIMITES_VIGENTES


def seed_monotributo_categorias(db: Session, organizacion_id: int) -> int:
    """Siembra las categorías default (servicios A-H, bienes A-K) si la org no
    tiene ninguna fila en categorias_monotributo. Idempotente.

    Usa la escala vigente — ver nota en `_LIMITES_VIGENTES`. Devuelve cuántas creó."""
    ya = (
        db.query(CategoriaMonotributo)
        .filter(CategoriaMonotributo.organizacion_id == organizacion_id)
        .count()
    )
    if ya > 0:
        return 0

    creadas = 0
    for tipo_actividad, escala in (("servicios", _CATS_SERVICIOS), ("bienes", _CATS_BIENES)):
        for i, (categoria, limite) in enumerate(escala, start=1):
            db.add(CategoriaMonotributo(
                organizacion_id=organizacion_id,
                categoria=categoria,
                tipo_actividad=tipo_actividad,
                limite_anual=Decimal(limite),
                orden=i,
            ))
            creadas += 1
    db.commit()
    logger.info("Categorías Monotributo sembradas para org %s (%d)", organizacion_id, creadas)
    return creadas
