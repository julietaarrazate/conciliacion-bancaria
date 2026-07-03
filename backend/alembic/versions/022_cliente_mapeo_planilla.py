"""Cliente.mapeo_planilla — perfil aprendido del formato de planilla del cliente

Agrega la columna `mapeo_planilla` (JSONB) a `clientes`. Guarda el mapeo de
columnas → esquema canónico que el pipeline de estandarización aprende cuando el
usuario corrige/confirma la detección desde el modal de preview
(services/planilla_mapper.py + POST /planillas/preview | /planillas/upload).

Aditivo y tolerante a reintentos (IF NOT EXISTS). No toca datos existentes.

Revision ID: 022
Revises: 021
Create Date: 2026-07-03
"""
from alembic import op

revision = '022'
down_revision = '021'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS mapeo_planilla JSONB")


def downgrade() -> None:
    op.execute("ALTER TABLE clientes DROP COLUMN IF EXISTS mapeo_planilla")
