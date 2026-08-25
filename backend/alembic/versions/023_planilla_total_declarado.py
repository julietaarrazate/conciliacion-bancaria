"""Planilla.total_declarado — total declarado por el cliente en su planilla

Agrega la columna `total_declarado` (NUMERIC(14,2)) a `planillas`. Guarda el monto
de la fila de resumen/total que algunos clientes ponen al final de su planilla, que
el pipeline de estandarización detecta y excluye de los movimientos
(services/planilla_mapper.py::_detectar_totales). Sirve para calcular el cuadre
(total declarado vs. suma de movimientos).

Aditivo y tolerante a reintentos (IF NOT EXISTS). No toca datos existentes.

Revision ID: 023
Revises: 022
Create Date: 2026-07-03
"""
from alembic import op

revision = '023'
down_revision = '022'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE planillas ADD COLUMN IF NOT EXISTS total_declarado NUMERIC(14,2)")


def downgrade() -> None:
    op.execute("ALTER TABLE planillas DROP COLUMN IF EXISTS total_declarado")
