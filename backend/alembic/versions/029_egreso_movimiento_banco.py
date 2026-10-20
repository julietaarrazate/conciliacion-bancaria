"""Egreso vinculado a un movimiento del extracto (resolver pendientes)

Agrega `egresos.movimiento_banco_id`: el débito del extracto que ese pago o
gasto explica. Se completa al resolver un movimiento pendiente desde la pantalla
de Movimientos sin salir de la conciliación. No cambia asientos: el egreso se
contabiliza igual que si se cargara a mano en Pagos.

Aditivo y tolerante a reintentos (IF NOT EXISTS). Mismo DDL que el safety net
de `app/db_safety.py`.

Revision ID: 029
Revises: 028
Create Date: 2026-10-20
"""
from alembic import op

revision = '029'
down_revision = '028'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE egresos ADD COLUMN IF NOT EXISTS movimiento_banco_id INTEGER "
        "REFERENCES movimientos_banco(id) ON DELETE SET NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_egresos_movimiento_banco_id ON egresos (movimiento_banco_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_egresos_movimiento_banco_id")
    op.execute("ALTER TABLE egresos DROP COLUMN IF EXISTS movimiento_banco_id")
