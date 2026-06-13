"""add index asientos.numero_asiento

Revision ID: 011
Revises: 010
Create Date: 2026-06-13
"""
from alembic import op

revision = '011'
down_revision = '010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE INDEX IF NOT EXISTS idx_asientos_numero ON asientos(numero_asiento DESC)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_asientos_numero")
