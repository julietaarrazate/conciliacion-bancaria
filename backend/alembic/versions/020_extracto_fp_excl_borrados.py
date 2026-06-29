"""Excluir extractos borrados (soft delete) del índice único de fingerprint

Antes el índice uq_extracto_fp_org cubría (fingerprint, organizacion_id) sin
mirar deleted_at: una fila borrada seguía ocupando el slot, así que borrar un
extracto y re-subir el mismo archivo chocaba contra el índice (error genérico
de "procesar el archivo"). Ahora el índice ignora los borrados, de modo que
re-subir un archivo borrado crea un extracto nuevo y limpio.

Revision ID: 020
Revises: 019
Create Date: 2026-06-29
"""
from alembic import op

revision = '020'
down_revision = '019'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_extracto_fp_org")
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_extracto_fp_org
        ON extractos_bancarios (fingerprint, organizacion_id)
        WHERE fingerprint IS NOT NULL AND deleted_at IS NULL
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_extracto_fp_org")
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_extracto_fp_org
        ON extractos_bancarios (fingerprint, organizacion_id)
        WHERE fingerprint IS NOT NULL
    """)
