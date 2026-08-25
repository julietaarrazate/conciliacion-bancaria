"""PlanillaRow.fecha — fecha de pago declarada en la planilla

Agrega la columna `fecha` (DATE) a `planilla_rows`. Guarda la fecha de pago que
trae la planilla del cliente (distinta de `fecha_acred`, que es la fecha de
acreditación al conciliar). Antes se descartaba al parsear. La usa el diagnóstico
de conciliación (services/conciliacion.py::diagnostico_conciliacion) para calcular
el período de la planilla y avisar si no solapa con el período del extracto.

Aditivo y tolerante a reintentos (IF NOT EXISTS). No toca datos existentes; las
filas viejas quedan con fecha NULL.

Revision ID: 024
Revises: 023
Create Date: 2026-07-04
"""
from alembic import op

revision = '024'
down_revision = '023'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE planilla_rows ADD COLUMN IF NOT EXISTS fecha DATE")


def downgrade() -> None:
    op.execute("ALTER TABLE planilla_rows DROP COLUMN IF EXISTS fecha")
