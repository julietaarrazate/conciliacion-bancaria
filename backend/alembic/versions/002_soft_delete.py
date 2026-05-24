"""soft delete para extractos y planillas

Revision ID: 002
Revises: 001
Create Date: 2026-05-24

Agrega columna deleted_at a extractos_bancarios y planillas.
- NULL = registro activo
- timestamp = registro borrado (queda en "papelera")

Es backwards-compatible: queries que no filtren ven todo,
queries actualizadas filtran deleted_at IS NULL.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "extractos_bancarios",
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "planillas",
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "idx_extractos_deleted_at",
        "extractos_bancarios",
        ["deleted_at"],
    )
    op.create_index(
        "idx_planillas_deleted_at",
        "planillas",
        ["deleted_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_planillas_deleted_at", table_name="planillas")
    op.drop_index("idx_extractos_deleted_at", table_name="extractos_bancarios")
    op.drop_column("planillas", "deleted_at")
    op.drop_column("extractos_bancarios", "deleted_at")
