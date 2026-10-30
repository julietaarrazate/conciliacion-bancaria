"""Plantillas de lectura de extractos en Excel/CSV (mapeo de columnas por org)

Crea `plantillas_extracto_excel`: el mapeo de columnas que la persona confirmó
para un formato de extracto (encabezado + banco). La próxima vez que llega un
archivo con el mismo encabezado se aplica solo. Además suma
`extractos_bancarios.aviso_saldos` (nullable): aviso no bloqueante que quedó al
importar (p. ej. "Los saldos no cuadran desde la fila N…").

Aditivo y tolerante a reintentos (IF NOT EXISTS). Mismo DDL que el safety net
de `app/db_safety.py`.

Revision ID: 038
Revises: 037
Create Date: 2026-10-30
"""
from alembic import op

revision = '038'
down_revision = '037'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE TABLE IF NOT EXISTS plantillas_extracto_excel ("
        "id SERIAL PRIMARY KEY, "
        "organizacion_id INTEGER NOT NULL REFERENCES organizaciones(id), "
        "banco_clave VARCHAR(40), "
        "firma VARCHAR(64) NOT NULL, "
        "encabezados JSON, "
        "mapeo JSON NOT NULL, "
        "usos INTEGER NOT NULL DEFAULT 0, "
        "creado_at TIMESTAMP DEFAULT NOW(), "
        "actualizado_at TIMESTAMP DEFAULT NOW(), "
        "ultimo_uso_at TIMESTAMP, "
        "creado_por INTEGER REFERENCES users(id) ON DELETE SET NULL, "
        "CONSTRAINT uq_plantilla_extracto_excel_org_firma UNIQUE (organizacion_id, firma))"
    )
    op.execute("ALTER TABLE extractos_bancarios ADD COLUMN IF NOT EXISTS aviso_saldos VARCHAR(300)")


def downgrade() -> None:
    op.execute("ALTER TABLE extractos_bancarios DROP COLUMN IF EXISTS aviso_saldos")
    op.execute("DROP TABLE IF EXISTS plantillas_extracto_excel")
