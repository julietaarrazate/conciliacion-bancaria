"""Total de retención de Ganancias 4ta en el período de liquidación de sueldos

Agrega:
  - liquidaciones_sueldo.total_retencion_ganancias

Lo necesita el asiento contable agrupado de sueldos para tener la contrapartida
de la retención de Ganancias (cuenta 2-1-6-0). Sin esta columna el total de
retención del período no se persistía y el asiento descuadraba al activar Ganancias.

Tolerante a reintentos: ADD COLUMN IF NOT EXISTS.

Revision ID: 018
Revises: 017
Create Date: 2026-06-24
"""
from alembic import op

revision = '018'
down_revision = '017'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE liquidaciones_sueldo ADD COLUMN IF NOT EXISTS "
        "total_retencion_ganancias NUMERIC(12,2) NOT NULL DEFAULT 0"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE liquidaciones_sueldo DROP COLUMN IF EXISTS total_retencion_ganancias"
    )
