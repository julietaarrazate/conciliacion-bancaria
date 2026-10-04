"""Comprobantes por revisar — facturas de compra por mail / lectura con IA

Crea `buzon_comprobantes` (la dirección de mail de cada organización, opt-in) y
`borradores_comprobante` (archivos recibidos con los datos leídos por la IA,
pendientes de confirmar). Al confirmar, el borrador crea un `comprobantes_iva`
(dirección "recibido") y opcionalmente un `egresos`; esas tablas no cambian.

Aditivo y tolerante a reintentos (IF NOT EXISTS). Mismo DDL que el safety net
de `app/db_safety.py`.

Revision ID: 027
Revises: 026
Create Date: 2026-10-04
"""
from alembic import op

revision = '027'
down_revision = '026'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE TABLE IF NOT EXISTS buzon_comprobantes ("
        "id SERIAL PRIMARY KEY, "
        "organizacion_id INTEGER NOT NULL UNIQUE REFERENCES organizaciones(id), "
        "token VARCHAR(32) NOT NULL UNIQUE, "
        "activo BOOLEAN NOT NULL DEFAULT TRUE, "
        "created_at TIMESTAMP DEFAULT NOW(), "
        "updated_at TIMESTAMP DEFAULT NOW())"
    )
    op.execute(
        "CREATE TABLE IF NOT EXISTS borradores_comprobante ("
        "id SERIAL PRIMARY KEY, "
        "organizacion_id INTEGER NOT NULL REFERENCES organizaciones(id), "
        "origen VARCHAR(10) NOT NULL DEFAULT 'subida', "
        "estado VARCHAR(20) NOT NULL DEFAULT 'procesando', "
        "email_id VARCHAR(64), "
        "adjunto_id VARCHAR(64), "
        "remitente VARCHAR(255), "
        "asunto VARCHAR(500), "
        "archivo_nombre VARCHAR(255), "
        "archivo_mime VARCHAR(100), "
        "archivo TEXT, "
        "datos JSON, "
        "alertas JSON, "
        "error TEXT, "
        "comprobante_iva_id INTEGER REFERENCES comprobantes_iva(id), "
        "egreso_id INTEGER REFERENCES egresos(id), "
        "creado_por INTEGER REFERENCES users(id), "
        "confirmado_por INTEGER REFERENCES users(id), "
        "confirmado_at TIMESTAMP, "
        "created_at TIMESTAMP DEFAULT NOW(), "
        "updated_at TIMESTAMP DEFAULT NOW(), "
        "CONSTRAINT uq_borrador_email_adjunto UNIQUE (organizacion_id, email_id, adjunto_id))"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_borrador_comprobante_org_estado "
        "ON borradores_comprobante (organizacion_id, estado)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_borrador_comprobante_email "
        "ON borradores_comprobante (email_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS borradores_comprobante")
    op.execute("DROP TABLE IF EXISTS buzon_comprobantes")
