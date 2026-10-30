"""conciliacion_grupos + conciliacion_grupo_items — conciliar N filas ↔ M movimientos

Un movimiento contra varias filas de la planilla (el cliente pagó varias filas
con una transferencia) o varias transferencias contra una fila. El caso 1:1
sigue en `planilla_rows.orden_movimiento_acreditado`, sin cambios. Ver
`app/models/conciliacion_grupo.py` y BUSINESS_RULES.md §1.10.

FKs con ON DELETE CASCADE: borrar un movimiento (extracto), una fila o una
planilla (purga de papelera) no puede fallar por un grupo que los referencia.

Aditivo e idempotente. Mismo DDL que el safety net de `app/db_safety.py`.

Revision ID: 039
Revises: 038
Create Date: 2026-10-30
"""
from alembic import op

revision = '039'
down_revision = '038'
branch_labels = None
depends_on = None

DDL = [
    "CREATE TABLE IF NOT EXISTS conciliacion_grupos ("
    "id SERIAL PRIMARY KEY, "
    "organizacion_id INTEGER NOT NULL REFERENCES organizaciones(id), "
    "planilla_id INTEGER NOT NULL REFERENCES planillas(id) ON DELETE CASCADE, "
    "estado VARCHAR(20) NOT NULL DEFAULT 'sugerido', "
    "origen VARCHAR(10) NOT NULL DEFAULT 'auto', "
    "total_filas NUMERIC(14,2) NOT NULL, "
    "total_movimientos NUMERIC(14,2) NOT NULL, "
    "diferencia NUMERIC(14,2) NOT NULL DEFAULT 0, "
    "ambiguo BOOLEAN NOT NULL DEFAULT FALSE, "
    "creado_por INTEGER REFERENCES users(id) ON DELETE SET NULL, "
    "created_at TIMESTAMP DEFAULT NOW(), "
    "confirmado_at TIMESTAMP)",
    "CREATE INDEX IF NOT EXISTS ix_conciliacion_grupos_organizacion_id ON conciliacion_grupos (organizacion_id)",
    "CREATE INDEX IF NOT EXISTS ix_conciliacion_grupos_planilla_id ON conciliacion_grupos (planilla_id)",
    "CREATE TABLE IF NOT EXISTS conciliacion_grupo_items ("
    "id SERIAL PRIMARY KEY, "
    "grupo_id INTEGER NOT NULL REFERENCES conciliacion_grupos(id) ON DELETE CASCADE, "
    "organizacion_id INTEGER NOT NULL REFERENCES organizaciones(id), "
    "planilla_row_id INTEGER REFERENCES planilla_rows(id) ON DELETE CASCADE, "
    "movimiento_id INTEGER REFERENCES movimientos_banco(id) ON DELETE CASCADE, "
    "monto NUMERIC(12,2) NOT NULL)",
    "CREATE INDEX IF NOT EXISTS ix_conciliacion_grupo_items_grupo_id ON conciliacion_grupo_items (grupo_id)",
    "CREATE INDEX IF NOT EXISTS ix_conciliacion_grupo_items_planilla_row_id ON conciliacion_grupo_items (planilla_row_id)",
    "CREATE INDEX IF NOT EXISTS ix_conciliacion_grupo_items_movimiento_id ON conciliacion_grupo_items (movimiento_id)",
]


def upgrade() -> None:
    for stmt in DDL:
        op.execute(stmt)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS conciliacion_grupo_items")
    op.execute("DROP TABLE IF EXISTS conciliacion_grupos")
