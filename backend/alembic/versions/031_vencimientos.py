"""Grilla de vencimientos: calendario general + marcas manuales por organización

Crea `calendario_vencimientos` (general: impuesto + período + bloque de
terminación de CUIT → fecha, cargado mes a mes desde la web de ARCA) y
`vencimientos_marcados` (por org: obligación presentada por fuera de los módulos).

Aditivo y tolerante a reintentos (IF NOT EXISTS). Mismo DDL que el safety net
de `app/db_safety.py`.

Revision ID: 031
Revises: 030
Create Date: 2026-10-20
"""
from alembic import op

revision = '031'
down_revision = '030'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE TABLE IF NOT EXISTS calendario_vencimientos ("
        "id SERIAL PRIMARY KEY, "
        "impuesto VARCHAR(20) NOT NULL, "
        "periodo VARCHAR(7) NOT NULL, "
        "terminacion_desde INTEGER NOT NULL, "
        "terminacion_hasta INTEGER NOT NULL, "
        "fecha DATE NOT NULL, "
        "fuente VARCHAR(255), "
        "cargado_por INTEGER REFERENCES users(id) ON DELETE SET NULL, "
        "updated_at TIMESTAMP DEFAULT NOW(), "
        "CONSTRAINT uq_calendario_venc_bloque UNIQUE (impuesto, periodo, terminacion_desde))"
    )
    op.execute(
        "CREATE TABLE IF NOT EXISTS vencimientos_marcados ("
        "id SERIAL PRIMARY KEY, "
        "organizacion_id INTEGER NOT NULL REFERENCES organizaciones(id), "
        "impuesto VARCHAR(20) NOT NULL, "
        "periodo VARCHAR(7) NOT NULL, "
        "marcado_por INTEGER REFERENCES users(id) ON DELETE SET NULL, "
        "marcado_at TIMESTAMP DEFAULT NOW(), "
        "CONSTRAINT uq_vencimiento_marcado UNIQUE (organizacion_id, impuesto, periodo))"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_vencimientos_marcados_org ON vencimientos_marcados (organizacion_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS vencimientos_marcados")
    op.execute("DROP TABLE IF EXISTS calendario_vencimientos")
