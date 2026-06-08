"""010_performance_indexes_2 — índices faltantes en clientes y plan_cuentas

Tablas afectadas: clientes, plan_cuentas, users
"""

from alembic import op

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # clientes — organizacion_id se usa como filtro en ~10 queries (cheques, liquidaciones,
    # contabilidad, análisis) pero no tenía índice standalone
    op.create_index("idx_clientes_org", "clientes", ["organizacion_id"], if_not_exists=True)

    # plan_cuentas — parent_id se usa en queries recursivas del árbol contable sin índice
    op.create_index("idx_plan_cuentas_parent", "plan_cuentas", ["parent_id"], if_not_exists=True)
    op.create_index("idx_plan_cuentas_org", "plan_cuentas", ["organizacion_id"], if_not_exists=True)

    # users — organizacion_id se usa en filtros de listado de usuarios
    op.create_index("idx_users_org", "users", ["organizacion_id"], if_not_exists=True)


def downgrade() -> None:
    op.drop_index("idx_clientes_org", table_name="clientes", if_exists=True)
    op.drop_index("idx_plan_cuentas_parent", table_name="plan_cuentas", if_exists=True)
    op.drop_index("idx_plan_cuentas_org", table_name="plan_cuentas", if_exists=True)
    op.drop_index("idx_users_org", table_name="users", if_exists=True)
