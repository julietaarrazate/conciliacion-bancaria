"""drop tablas obsoletas: ordenes_de_pago, pagos, gastos

Revision ID: 009
Revises: 008
Create Date: 2026-05-30
"""
from alembic import op

revision = '009'
down_revision = '008'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("DROP TABLE IF EXISTS ordenes_de_pago CASCADE")
    op.execute("DROP TABLE IF EXISTS pagos CASCADE")
    op.execute("DROP TABLE IF EXISTS gastos CASCADE")


def downgrade():
    # No se recrean — estas tablas fueron reemplazadas por 'egresos'
    pass
