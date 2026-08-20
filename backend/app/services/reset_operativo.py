"""Reset de datos OPERATIVOS por organización.

Deja el sistema listo para empezar a cargar de cero (extractos, planillas,
conciliaciones, cheques, contabilidad, liquidaciones…) CONSERVANDO los maestros
y la configuración de cada organización.

CONSERVA (maestros / config):
    organizaciones, users, clientes, plan_cuentas, reglas_contables, portadores,
    categorias_egreso, empleados, y toda la config impositiva/nómina
    (categorias_monotributo, monotributo_config, jurisdicciones_iibb, iibb_config,
    convenios_colectivos, categorias_convenio, config_sueldos, escala_ganancias,
    arca_config).

BORRA (transaccional / operativo):
    extractos_bancarios + movimientos_banco, planillas + planilla_rows,
    asientos + asiento_detalle, cheques, egresos, arqueos_diarios,
    liquidaciones (+ detalles + cierres_periodo), liquidaciones_sueldo (+ detalles),
    comprobantes_iva + liquidaciones_iva, comprobantes_arca, liquidaciones_tarjeta,
    proyecciones_iva, proyecciones_iibb, controles_monotributo, patrones_aprendidos,
    y — opcionalmente — el log de auditoría.
    También limpia las tablas legacy (ordenes_de_pago, pagos, gastos) si existen.

Nota contable: los saldos de cuenta corriente NO se guardan en ninguna columna;
se calculan sumando debe − haber de `asiento_detalle`. Al vaciar los asientos,
todos los saldos vuelven a cero sin tocar la ESTRUCTURA del plan de cuentas ni
el vínculo `clientes.cuenta_contable_id`.

El borrado corre en una sola transacción (o la commitea el caller). En `dry_run`
no borra nada: sólo reporta cuántas filas caerían por tabla.
"""
from __future__ import annotations

from typing import Sequence

from sqlalchemy import inspect as sa_inspect, text
from sqlalchemy.orm import Session

from app.models.arca import ComprobanteArca
from app.models.auditoria import AuditoriaLog
from app.models.caja import ArqueoDiario
from app.models.cheque import Cheque
from app.models.contabilidad import Asiento, AsientoDetalle
from app.models.egreso import Egreso
from app.models.extracto import ExtractoBancario, MovimientoBanco
from app.models.iibb import ProyeccionIIBB
from app.models.iva_liquidacion import ComprobanteIva, LiquidacionIva
from app.models.liquidacion import CierrePeriodo, Liquidacion, LiquidacionDetalle
from app.models.liquidacion_tarjeta import LiquidacionTarjeta
from app.models.monotributo import ControlMonotributo
from app.models.patron_aprendido import PatronAprendido
from app.models.planilla import Planilla, PlanillaRow
from app.models.proyeccion_iva import ProyeccionIva
from app.models.sueldos import DetalleLiquidacionEmpleado, LiquidacionSueldoPeriodo
from app.models.user import User

# Tablas legacy sin modelo ORM (reemplazadas por el módulo unificado Egreso).
# Se limpian con SQL crudo sólo si la tabla existe.
_LEGACY_TABLES = ("ordenes_de_pago", "pagos", "gastos")


def _norm_orgs(org_ids: int | Sequence[int]) -> list[int]:
    if isinstance(org_ids, int):
        return [org_ids]
    orgs = [int(o) for o in org_ids]
    if not orgs:
        raise ValueError("reset_datos_operativos requiere al menos un organizacion_id")
    return orgs


def reset_datos_operativos(
    db: Session,
    org_ids: int | Sequence[int],
    *,
    incluir_auditoria: bool = True,
    dry_run: bool = False,
) -> dict[str, int]:
    """Borra los datos operativos de las organizaciones indicadas.

    Args:
        db: sesión de SQLAlchemy.
        org_ids: un id o lista de ids de organización a limpiar.
        incluir_auditoria: si True, también borra el log de auditoría de esas orgs.
        dry_run: si True, no borra nada; sólo cuenta las filas afectadas.

    Returns:
        dict `nombre_tabla -> filas afectadas` (o que se afectarían, en dry_run).
        Sólo incluye tablas con conteo > 0.

    NO commitea: el caller decide `db.commit()` / `db.rollback()`.
    """
    orgs = _norm_orgs(org_ids)

    # Subconsultas de scoping para tablas hijas (sin organizacion_id propio).
    asientos_de_org = db.query(Asiento.id).filter(Asiento.organizacion_id.in_(orgs))
    planillas_de_org = db.query(Planilla.id).filter(Planilla.organizacion_id.in_(orgs))
    extractos_de_org = db.query(ExtractoBancario.id).filter(
        ExtractoBancario.organizacion_id.in_(orgs)
    )
    liquid_de_org = db.query(Liquidacion.id).filter(Liquidacion.organizacion_id.in_(orgs))
    liquid_sueldo_de_org = db.query(LiquidacionSueldoPeriodo.id).filter(
        LiquidacionSueldoPeriodo.organizacion_id.in_(orgs)
    )
    users_de_org = db.query(User.id).filter(User.organizacion_id.in_(orgs))

    # (etiqueta, query filtrada) en orden seguro de FKs: hijos antes que padres.
    plan: list[tuple[str, object]] = [
        ("asiento_detalle", db.query(AsientoDetalle).filter(
            AsientoDetalle.asiento_id.in_(asientos_de_org))),
        ("comprobantes_arca", db.query(ComprobanteArca).filter(
            ComprobanteArca.organizacion_id.in_(orgs))),
        ("liquidaciones_tarjeta", db.query(LiquidacionTarjeta).filter(
            LiquidacionTarjeta.organizacion_id.in_(orgs))),
        ("planilla_rows", db.query(PlanillaRow).filter(
            PlanillaRow.planilla_id.in_(planillas_de_org))),
        ("detalles_liquidacion_sueldo", db.query(DetalleLiquidacionEmpleado).filter(
            DetalleLiquidacionEmpleado.liquidacion_periodo_id.in_(liquid_sueldo_de_org))),
        ("liquidacion_detalles", db.query(LiquidacionDetalle).filter(
            LiquidacionDetalle.liquidacion_id.in_(liquid_de_org))),
        ("cierres_periodo", db.query(CierrePeriodo).filter(
            CierrePeriodo.organizacion_id.in_(orgs))),
        ("egresos", db.query(Egreso).filter(Egreso.organizacion_id.in_(orgs))),
        ("cheques", db.query(Cheque).filter(Cheque.organizacion_id.in_(orgs))),
        ("arqueos_diarios", db.query(ArqueoDiario).filter(
            ArqueoDiario.organizacion_id.in_(orgs))),
        ("liquidaciones", db.query(Liquidacion).filter(
            Liquidacion.organizacion_id.in_(orgs))),
        ("liquidaciones_sueldo", db.query(LiquidacionSueldoPeriodo).filter(
            LiquidacionSueldoPeriodo.organizacion_id.in_(orgs))),
        ("planillas", db.query(Planilla).filter(Planilla.organizacion_id.in_(orgs))),
        ("movimientos_banco", db.query(MovimientoBanco).filter(
            MovimientoBanco.extracto_id.in_(extractos_de_org))),
        ("extractos_bancarios", db.query(ExtractoBancario).filter(
            ExtractoBancario.organizacion_id.in_(orgs))),
        ("asientos", db.query(Asiento).filter(Asiento.organizacion_id.in_(orgs))),
        ("comprobantes_iva", db.query(ComprobanteIva).filter(
            ComprobanteIva.organizacion_id.in_(orgs))),
        ("liquidaciones_iva", db.query(LiquidacionIva).filter(
            LiquidacionIva.organizacion_id.in_(orgs))),
        ("proyecciones_iva", db.query(ProyeccionIva).filter(
            ProyeccionIva.organizacion_id.in_(orgs))),
        ("proyecciones_iibb", db.query(ProyeccionIIBB).filter(
            ProyeccionIIBB.organizacion_id.in_(orgs))),
        ("controles_monotributo", db.query(ControlMonotributo).filter(
            ControlMonotributo.organizacion_id.in_(orgs))),
        ("patrones_aprendidos", db.query(PatronAprendido).filter(
            PatronAprendido.organizacion_id.in_(orgs))),
    ]

    if incluir_auditoria:
        plan.append(("auditoria", db.query(AuditoriaLog).filter(
            AuditoriaLog.usuario_id.in_(users_de_org))))

    resultado: dict[str, int] = {}

    # `no_autoflush` evita que, entre delete y delete, un autoflush recorra las
    # relaciones de los maestros conservados (p.ej. Cliente.planillas) y re-inserte
    # las filas recién borradas por cascade "save-update".
    with db.no_autoflush:
        for label, query in plan:
            if dry_run:
                n = query.count()
            else:
                n = query.delete(synchronize_session=False)
            if n:
                resultado[label] = n

        # Tablas legacy (sin modelo ORM). Se limpian con SQL crudo, saltando de
        # forma segura las que no existan en este entorno (p.ej. el SQLite de los
        # tests) — se chequea existencia con el inspector para NO disparar
        # excepciones que aborten la transacción con los borrados ya aplicados.
        # Inspector sobre la CONEXIÓN de la sesión (no sobre el engine): así
        # comparte la misma transacción y no dispara un rollback que revierta
        # los borrados ORM ya emitidos.
        inspector = sa_inspect(db.connection())
        existing = set(inspector.get_table_names())
        # ANY(:orgs) es sintaxis Postgres; las tablas legacy sólo viven en prod (PG).
        for tabla in _LEGACY_TABLES:
            if tabla not in existing:
                continue
            if dry_run:
                n = db.execute(
                    text(f"SELECT count(*) FROM {tabla} WHERE organizacion_id = ANY(:orgs)"),
                    {"orgs": orgs},
                ).scalar() or 0
            else:
                res = db.execute(
                    text(f"DELETE FROM {tabla} WHERE organizacion_id = ANY(:orgs)"),
                    {"orgs": orgs},
                )
                n = res.rowcount or 0
            if n:
                resultado[tabla] = n

    if not dry_run:
        # Detacha todo lo que quedó en la sesión: el DELETE ya está emitido en la
        # transacción, y así el commit del caller no re-inserta nada por cascade.
        db.expunge_all()

    return resultado
