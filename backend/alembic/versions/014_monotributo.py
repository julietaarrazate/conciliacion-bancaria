"""Módulo Control Semestral Monotributo

Crea las 3 tablas del módulo:
  - categorias_monotributo : escalas A..K por org + tipo de actividad, con unique
    (organizacion_id, categoria, tipo_actividad).
  - monotributo_config     : 1 config por org (unique organizacion_id), opt-in.
  - controles_monotributo  : snapshot por semestre, unique (organizacion_id, periodo).

Tolerante a reintentos: IF NOT EXISTS donde aplica.

Revision ID: 014
Revises: 013
Create Date: 2026-06-23
"""
from alembic import op

revision = '014'
down_revision = '013'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS categorias_monotributo (
            id SERIAL PRIMARY KEY,
            organizacion_id INTEGER NOT NULL REFERENCES organizaciones(id),
            categoria VARCHAR(2) NOT NULL,
            tipo_actividad VARCHAR(20) NOT NULL,
            limite_anual NUMERIC(12,2) NOT NULL DEFAULT 0,
            orden INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            CONSTRAINT uq_categoria_monotributo_org_cat_tipo
                UNIQUE (organizacion_id, categoria, tipo_actividad)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_categoria_monotributo_org "
        "ON categorias_monotributo (organizacion_id)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS monotributo_config (
            id SERIAL PRIMARY KEY,
            organizacion_id INTEGER NOT NULL UNIQUE REFERENCES organizaciones(id),
            categoria_actual VARCHAR(2),
            tipo_actividad VARCHAR(20) NOT NULL DEFAULT 'servicios',
            activo BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS controles_monotributo (
            id SERIAL PRIMARY KEY,
            organizacion_id INTEGER NOT NULL REFERENCES organizaciones(id),
            periodo VARCHAR(7) NOT NULL,
            fecha_corte DATE NOT NULL,
            ingresos_12m NUMERIC(12,2) NOT NULL DEFAULT 0,
            categoria_actual VARCHAR(2),
            limite_categoria_actual NUMERIC(12,2) NOT NULL DEFAULT 0,
            porcentaje_uso NUMERIC(6,2) NOT NULL DEFAULT 0,
            categoria_sugerida VARCHAR(2),
            excede BOOLEAN NOT NULL DEFAULT FALSE,
            estado VARCHAR(20) NOT NULL DEFAULT 'pendiente',
            fecha_revision TIMESTAMP,
            detalle JSONB,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            CONSTRAINT uq_control_monotributo_org_periodo
                UNIQUE (organizacion_id, periodo)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_control_monotributo_org "
        "ON controles_monotributo (organizacion_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_control_monotributo_org")
    op.execute("DROP TABLE IF EXISTS controles_monotributo")
    op.execute("DROP TABLE IF EXISTS monotributo_config")
    op.execute("DROP INDEX IF EXISTS ix_categoria_monotributo_org")
    op.execute("DROP TABLE IF EXISTS categorias_monotributo")
