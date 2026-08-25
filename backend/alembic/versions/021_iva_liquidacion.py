"""Módulo Liquidación REAL de IVA (Excel "Mis Comprobantes" de ARCA)

Agrega:
  - tabla `comprobantes_iva` — staging de cada fila del Excel de ARCA
    (emitidos/recibidos), con UNIQUE de dedup para re-import.
  - tabla `liquidaciones_iva` — snapshot mensual de la posición de IVA con
    saldos técnico / de libre disponibilidad, UNIQUE (organizacion_id, periodo).

Distinto del módulo de *proyección* (migración 013): esto es la liquidación real
importada de ARCA. No toca el módulo de proyección.

Tolerante a reintentos: IF NOT EXISTS donde aplica.

Revision ID: 021
Revises: 020
Create Date: 2026-07-03
"""
from alembic import op

revision = '021'
down_revision = '020'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS comprobantes_iva (
            id SERIAL PRIMARY KEY,
            organizacion_id INTEGER NOT NULL REFERENCES organizaciones(id),
            direccion VARCHAR(10) NOT NULL,
            periodo VARCHAR(7) NOT NULL,
            fecha DATE NOT NULL,
            tipo_codigo INTEGER NOT NULL,
            tipo_desc VARCHAR(80),
            punto_venta INTEGER,
            numero INTEGER,
            cuit_contraparte VARCHAR(20),
            denominacion VARCHAR(255),
            neto_gravado_total NUMERIC(14,2) NOT NULL DEFAULT 0,
            total_iva NUMERIC(14,2) NOT NULL DEFAULT 0,
            imp_total NUMERIC(14,2) NOT NULL DEFAULT 0,
            detalle_alicuotas JSONB,
            incluido BOOLEAN NOT NULL DEFAULT TRUE,
            archivo_origen VARCHAR(255),
            created_at TIMESTAMP DEFAULT NOW(),
            CONSTRAINT uq_comprobante_iva_dedup UNIQUE
                (organizacion_id, direccion, tipo_codigo, punto_venta, numero, cuit_contraparte)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_comprobante_iva_org ON comprobantes_iva (organizacion_id)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_comprobante_iva_org_periodo "
        "ON comprobantes_iva (organizacion_id, periodo)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS liquidaciones_iva (
            id SERIAL PRIMARY KEY,
            organizacion_id INTEGER NOT NULL REFERENCES organizaciones(id),
            periodo VARCHAR(7) NOT NULL,
            debito_fiscal NUMERIC(14,2) NOT NULL DEFAULT 0,
            credito_fiscal NUMERIC(14,2) NOT NULL DEFAULT 0,
            tecnico_periodo NUMERIC(14,2) NOT NULL DEFAULT 0,
            saldo_tecnico_anterior NUMERIC(14,2) NOT NULL DEFAULT 0,
            saldo_tecnico_nuevo NUMERIC(14,2) NOT NULL DEFAULT 0,
            retenciones NUMERIC(14,2) NOT NULL DEFAULT 0,
            percepciones NUMERIC(14,2) NOT NULL DEFAULT 0,
            saldo_libre_anterior NUMERIC(14,2) NOT NULL DEFAULT 0,
            saldo_libre_nuevo NUMERIC(14,2) NOT NULL DEFAULT 0,
            saldo_a_pagar NUMERIC(14,2) NOT NULL DEFAULT 0,
            cant_emitidos INTEGER NOT NULL DEFAULT 0,
            cant_recibidos INTEGER NOT NULL DEFAULT 0,
            estado VARCHAR(20) NOT NULL DEFAULT 'borrador',
            fecha_presentacion TIMESTAMP,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            CONSTRAINT uq_liquidacion_iva_org_periodo UNIQUE (organizacion_id, periodo)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_liquidacion_iva_org ON liquidaciones_iva (organizacion_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_liquidacion_iva_org")
    op.execute("DROP TABLE IF EXISTS liquidaciones_iva")
    op.execute("DROP INDEX IF EXISTS ix_comprobante_iva_org_periodo")
    op.execute("DROP INDEX IF EXISTS ix_comprobante_iva_org")
    op.execute("DROP TABLE IF EXISTS comprobantes_iva")
