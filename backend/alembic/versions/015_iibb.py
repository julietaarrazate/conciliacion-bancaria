"""Módulo Ingresos Brutos (IIBB) y Convenio Multilateral

Crea las 3 tablas del módulo:
  - jurisdicciones_iibb : jurisdicciones por org con alícuota y coeficiente, con
    unique (organizacion_id, nombre).
  - iibb_config         : 1 config por org (unique organizacion_id), opt-in.
  - proyecciones_iibb   : snapshot por período, unique (organizacion_id, periodo).

Tolerante a reintentos: IF NOT EXISTS donde aplica.

Revision ID: 015
Revises: 014
Create Date: 2026-06-24
"""
from alembic import op

revision = '015'
down_revision = '014'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS jurisdicciones_iibb (
            id SERIAL PRIMARY KEY,
            organizacion_id INTEGER NOT NULL REFERENCES organizaciones(id),
            nombre VARCHAR(80) NOT NULL,
            alicuota NUMERIC(5,4) NOT NULL DEFAULT 0,
            coeficiente_distribucion NUMERIC(5,4) NOT NULL DEFAULT 0,
            activa BOOLEAN NOT NULL DEFAULT TRUE,
            orden INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            CONSTRAINT uq_jurisdiccion_iibb_org_nombre
                UNIQUE (organizacion_id, nombre)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_jurisdiccion_iibb_org "
        "ON jurisdicciones_iibb (organizacion_id)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS iibb_config (
            id SERIAL PRIMARY KEY,
            organizacion_id INTEGER NOT NULL UNIQUE REFERENCES organizaciones(id),
            activo BOOLEAN NOT NULL DEFAULT FALSE,
            modo VARCHAR(24) NOT NULL DEFAULT 'simple',
            jurisdiccion_unica_id INTEGER REFERENCES jurisdicciones_iibb(id),
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS proyecciones_iibb (
            id SERIAL PRIMARY KEY,
            organizacion_id INTEGER NOT NULL REFERENCES organizaciones(id),
            periodo VARCHAR(7) NOT NULL,
            ingreso_total NUMERIC(12,2) NOT NULL DEFAULT 0,
            impuesto_total NUMERIC(12,2) NOT NULL DEFAULT 0,
            detalle_por_jurisdiccion JSONB,
            estado VARCHAR(20) NOT NULL DEFAULT 'proyectado',
            fecha_presentacion TIMESTAMP,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            CONSTRAINT uq_proyeccion_iibb_org_periodo
                UNIQUE (organizacion_id, periodo)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_proyeccion_iibb_org "
        "ON proyecciones_iibb (organizacion_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_proyeccion_iibb_org")
    op.execute("DROP TABLE IF EXISTS proyecciones_iibb")
    op.execute("DROP TABLE IF EXISTS iibb_config")
    op.execute("DROP INDEX IF EXISTS ix_jurisdiccion_iibb_org")
    op.execute("DROP TABLE IF EXISTS jurisdicciones_iibb")
