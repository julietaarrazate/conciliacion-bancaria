"""Planilla.fingerprint — bloquear re-subir la misma planilla para un cliente

Agrega `fingerprint` (sha1 del contenido del archivo) a `planillas` + índice único
parcial por (cliente_id, fingerprint, organizacion_id), excluyendo planillas
borradas (deleted_at IS NULL) — mismo patrón que uq_extracto_fp_org (migración 006 /
safety net). Borrar la planilla existente libera el fingerprint para re-subir.

Aditivo y tolerante a reintentos (IF NOT EXISTS). No toca datos existentes.

Revision ID: 026
Revises: 025
Create Date: 2026-08-20
"""
from alembic import op

revision = '026'
down_revision = '025'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE planillas ADD COLUMN IF NOT EXISTS fingerprint VARCHAR")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_planilla_fp_cliente_org "
        "ON planillas (cliente_id, fingerprint, organizacion_id) "
        "WHERE fingerprint IS NOT NULL AND deleted_at IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_planilla_fp_cliente_org")
    op.execute("ALTER TABLE planillas DROP COLUMN IF EXISTS fingerprint")
