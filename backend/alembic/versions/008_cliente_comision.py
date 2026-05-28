"""add porcentaje_comision to clientes

Revision ID: 008
Revises: 007
Create Date: 2026-05-28
"""
from alembic import op
import sqlalchemy as sa

revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'clientes',
        sa.Column('porcentaje_comision', sa.Numeric(5, 4), nullable=True)
    )


def downgrade():
    op.drop_column('clientes', 'porcentaje_comision')
