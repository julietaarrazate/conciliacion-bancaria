"""Auditoría por organización (auditoria.organizacion_id)

El listado de auditoría filtraba por la org "de casa" del usuario que hizo la acción: un
usuario con `view_audit` en la org 1 veía las acciones del superadmin en todas las orgs.
Ahora cada fila guarda la org de la acción. Las filas viejas quedan en NULL (sin backfill:
la org de una acción vieja no se puede derivar con certeza) y el listado las sigue
filtrando por la org del usuario, como antes.

Aditivo e idempotente. Mismo DDL que el safety net de `app/db_safety.py`.

Revision ID: 035
Revises: 034
Create Date: 2026-10-23
"""
from alembic import op

revision = '035'
down_revision = '034'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE auditoria ADD COLUMN IF NOT EXISTS organizacion_id INTEGER "
        "REFERENCES organizaciones(id) ON DELETE SET NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_auditoria_organizacion_id ON auditoria (organizacion_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_auditoria_organizacion_id")
    op.execute("ALTER TABLE auditoria DROP COLUMN IF EXISTS organizacion_id")
