"""Retención de Ganancias 4ta categoría (opt-in, independiente del módulo Sueldos)

Agrega:
  - config_sueldos.ganancias_activo / minimo_no_imponible / deduccion_especial
  - detalles_liquidacion_sueldo.retencion_ganancias
  - escala_ganancias (tabla nueva, por org, vacía por default — NO se siembra con
    valores reales porque la escala de AFIP/ARCA cambia varias veces por año)

Tolerante a reintentos: ADD COLUMN IF NOT EXISTS / CREATE TABLE IF NOT EXISTS.

Revision ID: 017
Revises: 016
Create Date: 2026-06-24
"""
from alembic import op

revision = '017'
down_revision = '016'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE config_sueldos ADD COLUMN IF NOT EXISTS "
        "ganancias_activo BOOLEAN NOT NULL DEFAULT FALSE"
    )
    op.execute(
        "ALTER TABLE config_sueldos ADD COLUMN IF NOT EXISTS "
        "minimo_no_imponible NUMERIC(12,2) NOT NULL DEFAULT 0"
    )
    op.execute(
        "ALTER TABLE config_sueldos ADD COLUMN IF NOT EXISTS "
        "deduccion_especial NUMERIC(12,2) NOT NULL DEFAULT 0"
    )
    op.execute(
        "ALTER TABLE detalles_liquidacion_sueldo ADD COLUMN IF NOT EXISTS "
        "retencion_ganancias NUMERIC(12,2) NOT NULL DEFAULT 0"
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS escala_ganancias (
            id SERIAL PRIMARY KEY,
            organizacion_id INTEGER NOT NULL REFERENCES organizaciones(id),
            tramo_desde NUMERIC(14,2) NOT NULL DEFAULT 0,
            tramo_hasta NUMERIC(14,2),
            alicuota NUMERIC(5,4) NOT NULL DEFAULT 0,
            monto_fijo NUMERIC(12,2) NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_escala_ganancias_org ON escala_ganancias (organizacion_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_escala_ganancias_org")
    op.execute("DROP TABLE IF EXISTS escala_ganancias")
    op.execute("ALTER TABLE detalles_liquidacion_sueldo DROP COLUMN IF EXISTS retencion_ganancias")
    op.execute("ALTER TABLE config_sueldos DROP COLUMN IF EXISTS deduccion_especial")
    op.execute("ALTER TABLE config_sueldos DROP COLUMN IF EXISTS minimo_no_imponible")
    op.execute("ALTER TABLE config_sueldos DROP COLUMN IF EXISTS ganancias_activo")
