"""baseline — estado actual de la DB al incorporar Alembic

Revision ID: 001
Revises:
Create Date: 2026-05-23

Esta migración no ejecuta ningún SQL.
Representa el estado de la base de datos al momento de incorporar Alembic.
Las tablas ya existen (creadas por SQLAlchemy create_all + ALTER TABLEs del startup).
"""
from typing import Sequence, Union

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
