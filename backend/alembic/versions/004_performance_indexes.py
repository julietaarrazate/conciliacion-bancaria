"""004_performance_indexes — índices para queries de analítica y conciliación

Tablas afectadas: movimientos_banco, planillas, planilla_rows, cheques, pagos, gastos, auditoria
"""

from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # movimientos_banco — la tabla más consultada en analytics
    op.create_index("idx_movbanco_org_fecha",     "movimientos_banco", ["organizacion_id", "fecha"],  if_not_exists=True)
    op.create_index("idx_movbanco_org",           "movimientos_banco", ["organizacion_id"],            if_not_exists=True)
    op.create_index("idx_movbanco_extracto",      "movimientos_banco", ["extracto_id"],               if_not_exists=True)

    # planillas — filtrada por org + deleted_at en casi todas las queries
    op.create_index("idx_planillas_org_deleted",  "planillas", ["organizacion_id", "deleted_at"],     if_not_exists=True)
    op.create_index("idx_planillas_org_cliente",  "planillas", ["organizacion_id", "cliente_id"],     if_not_exists=True)
    op.create_index("idx_planillas_cliente",      "planillas", ["cliente_id"],                        if_not_exists=True)

    # planilla_rows — join + filter por status es la query más frecuente del motor
    op.create_index("idx_planrows_planilla",      "planilla_rows", ["planilla_id"],                   if_not_exists=True)
    op.create_index("idx_planrows_status",        "planilla_rows", ["status"],                        if_not_exists=True)
    op.create_index("idx_planrows_planilla_status","planilla_rows", ["planilla_id", "status"],         if_not_exists=True)

    # cheques — alertas, aging, proximos a vencer
    op.create_index("idx_cheques_org_estado",     "cheques", ["organizacion_id", "estado"],           if_not_exists=True)
    op.create_index("idx_cheques_org_deposito",   "cheques", ["organizacion_id", "fecha_deposito"],   if_not_exists=True)

    # pagos y gastos — flujo de caja mensual
    op.create_index("idx_pagos_org_fecha",        "pagos",   ["organizacion_id", "fecha"],            if_not_exists=True)
    op.create_index("idx_gastos_org_fecha",       "gastos",  ["organizacion_id", "fecha"],            if_not_exists=True)

    # auditoria — listados por org
    op.create_index("idx_auditoria_org",          "auditoria", ["organizacion_id"],                   if_not_exists=True)
    op.create_index("idx_auditoria_org_fecha",    "auditoria", ["organizacion_id", "fecha"],          if_not_exists=True)


def downgrade() -> None:
    op.drop_index("idx_auditoria_org_fecha",     table_name="auditoria")
    op.drop_index("idx_auditoria_org",           table_name="auditoria")
    op.drop_index("idx_gastos_org_fecha",        table_name="gastos")
    op.drop_index("idx_pagos_org_fecha",         table_name="pagos")
    op.drop_index("idx_cheques_org_deposito",    table_name="cheques")
    op.drop_index("idx_cheques_org_estado",      table_name="cheques")
    op.drop_index("idx_planrows_planilla_status",table_name="planilla_rows")
    op.drop_index("idx_planrows_status",         table_name="planilla_rows")
    op.drop_index("idx_planrows_planilla",       table_name="planilla_rows")
    op.drop_index("idx_planillas_cliente",       table_name="planillas")
    op.drop_index("idx_planillas_org_cliente",   table_name="planillas")
    op.drop_index("idx_planillas_org_deleted",   table_name="planillas")
    op.drop_index("idx_movbanco_extracto",       table_name="movimientos_banco")
    op.drop_index("idx_movbanco_org",            table_name="movimientos_banco")
    op.drop_index("idx_movbanco_org_fecha",      table_name="movimientos_banco")
