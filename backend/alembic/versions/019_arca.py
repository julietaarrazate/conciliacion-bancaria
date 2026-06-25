"""Módulo ARCA (ex-AFIP) — facturación electrónica, integración propia WSFEv1/WSAA

Agrega:
  - arca_config: configuración por organización (opt-in, certificado+clave cifrados)
  - comprobantes_arca: comprobantes emitidos/intentados con CAE

Tolerante a reintentos: CREATE TABLE/INDEX IF NOT EXISTS.

Revision ID: 019
Revises: 018
Create Date: 2026-06-25
"""
from alembic import op

revision = '019'
down_revision = '018'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE TABLE IF NOT EXISTS arca_config ("
        "id SERIAL PRIMARY KEY, "
        "organizacion_id INTEGER NOT NULL UNIQUE REFERENCES organizaciones(id), "
        "cuit VARCHAR(11), "
        "ambiente VARCHAR(20) NOT NULL DEFAULT 'homologacion', "
        "punto_venta INTEGER NOT NULL DEFAULT 1, "
        "activo BOOLEAN NOT NULL DEFAULT FALSE, "
        "certificado_enc TEXT, "
        "clave_privada_enc TEXT, "
        "certificado_subido_en TIMESTAMP, "
        "ultimo_token_enc TEXT, "
        "ultimo_sign_enc TEXT, "
        "token_expira TIMESTAMP, "
        "created_at TIMESTAMP DEFAULT NOW(), "
        "updated_at TIMESTAMP DEFAULT NOW())"
    )
    op.execute(
        "CREATE TABLE IF NOT EXISTS comprobantes_arca ("
        "id SERIAL PRIMARY KEY, "
        "organizacion_id INTEGER NOT NULL REFERENCES organizaciones(id), "
        "cliente_id INTEGER REFERENCES clientes(id), "
        "tipo_comprobante INTEGER NOT NULL, "
        "punto_venta INTEGER NOT NULL, "
        "numero INTEGER, "
        "concepto INTEGER NOT NULL DEFAULT 1, "
        "doc_tipo INTEGER NOT NULL DEFAULT 99, "
        "doc_nro VARCHAR(11), "
        "fecha_emision DATE NOT NULL, "
        "importe_neto NUMERIC(12,2) NOT NULL DEFAULT 0, "
        "importe_iva NUMERIC(12,2) NOT NULL DEFAULT 0, "
        "importe_total NUMERIC(12,2) NOT NULL DEFAULT 0, "
        "cae VARCHAR(20), "
        "cae_vencimiento DATE, "
        "estado VARCHAR(20) NOT NULL DEFAULT 'borrador', "
        "error_detalle TEXT, "
        "referencia_planilla_id INTEGER REFERENCES planillas(id), "
        "asiento_id INTEGER REFERENCES asientos(id), "
        "usuario_id INTEGER REFERENCES users(id), "
        "created_at TIMESTAMP DEFAULT NOW(), "
        "updated_at TIMESTAMP DEFAULT NOW(), "
        "CONSTRAINT uq_comprobante_arca_org_pv_tipo_numero UNIQUE (organizacion_id, punto_venta, tipo_comprobante, numero))"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_arca_config_org ON arca_config (organizacion_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_comprobantes_arca_org ON comprobantes_arca (organizacion_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_comprobantes_arca_cliente ON comprobantes_arca (cliente_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS comprobantes_arca")
    op.execute("DROP TABLE IF EXISTS arca_config")
