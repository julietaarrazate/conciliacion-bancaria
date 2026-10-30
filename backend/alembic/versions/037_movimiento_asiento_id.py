"""movimientos_banco.asiento_id — qué asiento contable registró cada movimiento

El extracto bancario principal se registra con un asiento por día
(motor_contable.registrar_asientos_extracto, módulo "extracto_banco"). Esta
columna marca cada movimiento con el asiento que lo incluyó: así el registro es
idempotente a nivel movimiento (correr de nuevo solo toma los que no tienen
asiento) y se sabe qué asientos pertenecen a cada extracto (purga, corrección).

FK lógica (como asientos.referencia_id), sin constraint: "Empezar limpio" borra
asientos y limpia esta columna en la misma transacción.

Aditivo e idempotente. Mismo DDL que el safety net de `app/db_safety.py`.

Revision ID: 037
Revises: 036
Create Date: 2026-10-23
"""
from alembic import op

revision = '037'
down_revision = '036'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE movimientos_banco ADD COLUMN IF NOT EXISTS asiento_id INTEGER")


def downgrade() -> None:
    op.execute("ALTER TABLE movimientos_banco DROP COLUMN IF EXISTS asiento_id")
