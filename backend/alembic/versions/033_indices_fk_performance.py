"""Índices de performance sobre FKs sin índice usadas en filtros y joins

- `planilla_rows.orden_movimiento_acreditado` (FK a movimientos_banco): se filtra al
  editar/borrar un movimiento, en la papelera y en el detalle de planilla filtrado por
  movimiento; en PostgreSQL además la usa el chequeo de FK al borrar movimientos.
- `egresos.arqueo_id` (FK a arqueos_diarios): egresos de cada arqueo (caja del día e
  historial de arqueos).

Medido con `python3 -m scripts.perf.indices` (SQLite, 60k filas / 20k filas): de SCAN
de la tabla entera a SEARCH por índice (1,8 ms → 0,002 ms y 0,9 ms → 0,05 ms por
consulta).

Aditivo e idempotente (IF NOT EXISTS). Mismo DDL que el safety net de
`app/db_safety.py`; mismos nombres que genera `index=True` en los modelos.

Revision ID: 033
Revises: 032
Create Date: 2026-10-22
"""
from alembic import op

revision = '033'
down_revision = '032'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_planilla_rows_orden_movimiento_acreditado "
        "ON planilla_rows (orden_movimiento_acreditado)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_egresos_arqueo_id ON egresos (arqueo_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_egresos_arqueo_id")
    op.execute("DROP INDEX IF EXISTS ix_planilla_rows_orden_movimiento_acreditado")
