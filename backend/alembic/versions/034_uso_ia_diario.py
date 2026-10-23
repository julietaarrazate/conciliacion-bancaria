"""Cupo diario de IA por organización (uso_ia_diario)

Una fila por (organización, día, tipo) con la cantidad de llamadas a la IA. Antes el
cupo era un contador global en memoria: lo gastaba cualquier organización y se
reiniciaba con cada deploy.

Aditivo e idempotente. Mismo DDL que el safety net de `app/db_safety.py`.

Revision ID: 034
Revises: 033
Create Date: 2026-10-22
"""
from alembic import op

revision = '034'
down_revision = '033'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE TABLE IF NOT EXISTS uso_ia_diario ("
        "id SERIAL PRIMARY KEY, "
        "organizacion_id INTEGER NOT NULL REFERENCES organizaciones(id), "
        "fecha DATE NOT NULL, "
        "tipo VARCHAR(20) NOT NULL, "
        "cantidad INTEGER NOT NULL DEFAULT 0, "
        "CONSTRAINT uq_uso_ia_org_fecha_tipo UNIQUE (organizacion_id, fecha, tipo))"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_uso_ia_diario_organizacion_id ON uso_ia_diario (organizacion_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS uso_ia_diario")
