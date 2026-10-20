"""Tanda de importación de "Mis Comprobantes" (deshacer una importación)

Agrega `comprobantes_iva.lote_importacion`: el uuid de la importación del Excel
de ARCA que trajo el comprobante. Permite deshacer una tanda entera. Los
comprobantes cargados antes quedan con NULL.

Aditivo y tolerante a reintentos (IF NOT EXISTS). Mismo DDL que el safety net
de `app/db_safety.py`.

Revision ID: 030
Revises: 029
Create Date: 2026-10-20
"""
from alembic import op

revision = '030'
down_revision = '029'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE comprobantes_iva ADD COLUMN IF NOT EXISTS lote_importacion VARCHAR(36)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_comprobantes_iva_lote_importacion "
        "ON comprobantes_iva (lote_importacion)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_comprobantes_iva_lote_importacion")
    op.execute("ALTER TABLE comprobantes_iva DROP COLUMN IF EXISTS lote_importacion")
