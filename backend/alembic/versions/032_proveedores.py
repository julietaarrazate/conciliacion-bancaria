"""Ficha de proveedores propios de la organización + vínculo desde Pagos

Crea `proveedores` (a quien la org le compra; único por org + CUIT) y agrega
`egresos.proveedor_id`. Base para las retenciones. Los proveedores de los
clientes (OP por cuenta de un cliente) no van acá.

Aditivo y tolerante a reintentos (IF NOT EXISTS). Mismo DDL que el safety net
de `app/db_safety.py`.

Revision ID: 032
Revises: 031
Create Date: 2026-10-20
"""
from alembic import op

revision = '032'
down_revision = '031'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE TABLE IF NOT EXISTS proveedores ("
        "id SERIAL PRIMARY KEY, "
        "organizacion_id INTEGER NOT NULL REFERENCES organizaciones(id), "
        "cuit VARCHAR(11), "
        "razon_social VARCHAR(255) NOT NULL, "
        "condicion_iva VARCHAR(30), "
        "email VARCHAR(255), "
        "cbu VARCHAR(22), "
        "notas TEXT, "
        "origen VARCHAR(20) NOT NULL DEFAULT 'manual', "
        "activo BOOLEAN NOT NULL DEFAULT TRUE, "
        "created_at TIMESTAMP DEFAULT NOW(), "
        "updated_at TIMESTAMP DEFAULT NOW(), "
        "CONSTRAINT uq_proveedor_org_cuit UNIQUE (organizacion_id, cuit))"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_proveedores_organizacion_id ON proveedores (organizacion_id)")
    op.execute("ALTER TABLE egresos ADD COLUMN IF NOT EXISTS proveedor_id INTEGER "
               "REFERENCES proveedores(id) ON DELETE SET NULL")
    op.execute("CREATE INDEX IF NOT EXISTS ix_egresos_proveedor_id ON egresos (proveedor_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_egresos_proveedor_id")
    op.execute("ALTER TABLE egresos DROP COLUMN IF EXISTS proveedor_id")
    op.execute("DROP TABLE IF EXISTS proveedores")
