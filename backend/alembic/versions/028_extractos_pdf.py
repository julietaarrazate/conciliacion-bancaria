"""Extractos en PDF — borradores de revisión y formatos aprendidos

Crea `moldes_extracto_pdf` (formato de tabla de un banco aprendido por
organización: la próxima vez ese PDF se lee sin IA) y `borradores_extracto_pdf`
(lo leído de un PDF, pendiente de revisión). Al confirmar, el borrador crea un
`extractos_bancarios` (igual que el upload de Excel) o agrega movimientos a uno
existente (igual que el UM); esas tablas no cambian.

Aditivo y tolerante a reintentos (IF NOT EXISTS). Mismo DDL que el safety net
de `app/db_safety.py`.

Revision ID: 028
Revises: 027
Create Date: 2026-10-16
"""
from alembic import op

revision = '028'
down_revision = '027'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE TABLE IF NOT EXISTS moldes_extracto_pdf ("
        "id SERIAL PRIMARY KEY, "
        "organizacion_id INTEGER NOT NULL REFERENCES organizaciones(id), "
        "banco_clave VARCHAR(40), "
        "firma VARCHAR(64) NOT NULL, "
        "layout JSON NOT NULL, "
        "origen VARCHAR(20), "
        "confirmaciones INTEGER NOT NULL DEFAULT 0, "
        "creado_at TIMESTAMP DEFAULT NOW(), "
        "ultimo_uso_at TIMESTAMP, "
        "creado_por INTEGER REFERENCES users(id) ON DELETE SET NULL, "
        "CONSTRAINT uq_molde_extracto_pdf_org_firma UNIQUE (organizacion_id, firma))"
    )
    op.execute(
        "CREATE TABLE IF NOT EXISTS borradores_extracto_pdf ("
        "id SERIAL PRIMARY KEY, "
        "organizacion_id INTEGER NOT NULL REFERENCES organizaciones(id), "
        "creado_por INTEGER REFERENCES users(id) ON DELETE SET NULL, "
        "creado_at TIMESTAMP DEFAULT NOW(), "
        "actualizado_at TIMESTAMP DEFAULT NOW(), "
        "nombre_archivo VARCHAR(255) NOT NULL, "
        "contenido_sha256 VARCHAR(64), "
        "tamano_bytes INTEGER, "
        "estado VARCHAR(20) NOT NULL DEFAULT 'procesando', "
        "metodo VARCHAR(20), "
        "banco VARCHAR(120), "
        "banco_clave VARCHAR(40), "
        "molde_id INTEGER REFERENCES moldes_extracto_pdf(id) ON DELETE SET NULL, "
        "periodo_desde DATE, "
        "periodo_hasta DATE, "
        "saldo_inicial NUMERIC(16,2), "
        "saldo_final NUMERIC(16,2), "
        "datos JSON, "
        "alertas JSON, "
        "error TEXT, "
        "extracto_id INTEGER REFERENCES extractos_bancarios(id) ON DELETE SET NULL, "
        "confirmado_por INTEGER REFERENCES users(id) ON DELETE SET NULL, "
        "confirmado_at TIMESTAMP)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_borrador_extracto_pdf_org_estado "
        "ON borradores_extracto_pdf (organizacion_id, estado)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_borrador_extracto_pdf_org_sha "
        "ON borradores_extracto_pdf (organizacion_id, contenido_sha256)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS borradores_extracto_pdf")
    op.execute("DROP TABLE IF EXISTS moldes_extracto_pdf")
