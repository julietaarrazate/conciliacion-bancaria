"""Módulo IVA Proyección y DDJJ

Agrega:
  - columna `tasa_iva` (Numeric 5,4, nullable) a `plan_cuentas` — % de IVA
    aplicable a la cuenta cuando se usa en un asiento (0.21, 0.105, 0=exento,
    NULL=no aplica/no configurado).
  - tabla `proyecciones_iva` — snapshot del IVA proyectado/DDJJ por período, con
    constraint único (organizacion_id, periodo).

Tolerante a reintentos: IF NOT EXISTS donde aplica.

Revision ID: 013
Revises: 012
Create Date: 2026-06-23
"""
from alembic import op

revision = '013'
down_revision = '012'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # tasa_iva por cuenta
    op.execute("ALTER TABLE plan_cuentas ADD COLUMN IF NOT EXISTS tasa_iva NUMERIC(5,4)")

    # snapshot por período
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS proyecciones_iva (
            id SERIAL PRIMARY KEY,
            organizacion_id INTEGER NOT NULL REFERENCES organizaciones(id),
            periodo VARCHAR(7) NOT NULL,
            debito_fiscal NUMERIC(12,2) NOT NULL DEFAULT 0,
            credito_fiscal NUMERIC(12,2) NOT NULL DEFAULT 0,
            saldo NUMERIC(12,2) NOT NULL DEFAULT 0,
            estado VARCHAR(20) NOT NULL DEFAULT 'proyectado',
            fecha_presentacion TIMESTAMP,
            detalle JSONB,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            CONSTRAINT uq_proyeccion_iva_org_periodo UNIQUE (organizacion_id, periodo)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_proyeccion_iva_org ON proyecciones_iva (organizacion_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_proyeccion_iva_org")
    op.execute("DROP TABLE IF EXISTS proyecciones_iva")
    op.execute("ALTER TABLE plan_cuentas DROP COLUMN IF EXISTS tasa_iva")
