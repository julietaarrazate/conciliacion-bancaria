"""Índices críticos en asientos y asiento_detalle

Los módulos de contabilidad (Libro Diario, Cuentas Corrientes, Mayor) filtran
por organizacion_id en CADA query a asientos, y hacen JOIN por asiento_id y
cuenta_id en asiento_detalle — sin índices eran full table scans.

Revision ID: 012
Revises: 011
Create Date: 2026-06-14
"""
from alembic import op

revision = '012'
down_revision = '011'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # asientos — organizacion_id está en TODOS los filtros contables
    op.execute("CREATE INDEX IF NOT EXISTS idx_asiento_org ON asientos(organizacion_id)")
    # compuesto org+fecha para rangos de fecha (Libro Diario, cuentas corrientes)
    op.execute("CREATE INDEX IF NOT EXISTS idx_asiento_org_fecha ON asientos(organizacion_id, fecha)")
    # modulo — filtrado en libro diario y fix-fechas
    op.execute("CREATE INDEX IF NOT EXISTS idx_asiento_modulo ON asientos(modulo)")

    # asiento_detalle — JOIN crítico; sin índice = full scan en cada query contable
    op.execute("CREATE INDEX IF NOT EXISTS idx_asdet_asiento ON asiento_detalle(asiento_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_asdet_cuenta ON asiento_detalle(cuenta_id)")
    # compuesto (cuenta_id, asiento_id) para las queries de cuentas corrientes que
    # filtran por cuenta y luego joinean con asientos
    op.execute("CREATE INDEX IF NOT EXISTS idx_asdet_cuenta_asiento ON asiento_detalle(cuenta_id, asiento_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_asiento_org")
    op.execute("DROP INDEX IF EXISTS idx_asiento_org_fecha")
    op.execute("DROP INDEX IF EXISTS idx_asiento_modulo")
    op.execute("DROP INDEX IF EXISTS idx_asdet_asiento")
    op.execute("DROP INDEX IF EXISTS idx_asdet_cuenta")
    op.execute("DROP INDEX IF EXISTS idx_asdet_cuenta_asiento")
