"""ExtractoBancario.archivado_at — archivar extractos (cierre de período)

Agrega la columna `archivado_at` (TIMESTAMP) a `extractos_bancarios`. Distinto del
soft delete: un extracto archivado sigue siendo consultable/exportable por id (todo
lo conciliado queda guardado), pero sale del listado por defecto y rechaza nuevos
UM. Permite cerrar el mes/período y arrancar un extracto nuevo del mismo banco sin
que el histórico se vuelva pesado.

Aditivo y tolerante a reintentos (IF NOT EXISTS). No toca datos existentes.

Revision ID: 025
Revises: 024
Create Date: 2026-07-04
"""
from alembic import op

revision = '025'
down_revision = '024'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE extractos_bancarios ADD COLUMN IF NOT EXISTS archivado_at TIMESTAMP")


def downgrade() -> None:
    op.execute("ALTER TABLE extractos_bancarios DROP COLUMN IF EXISTS archivado_at")
