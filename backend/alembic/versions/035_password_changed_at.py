"""Cambio de contraseña cierra las sesiones abiertas (users.password_changed_at)

Al cambiar o restablecer la contraseña se guarda la fecha (UTC); `get_current_user`
rechaza los JWT emitidos antes (`iat` anterior). NULL = nunca cambió: los usuarios
existentes siguen igual.

Aditivo e idempotente. Mismo DDL que el safety net de `app/db_safety.py`.

Revision ID: 035
Revises: 034
Create Date: 2026-10-23
"""
from alembic import op

revision = '035'
down_revision = '034'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS password_changed_at TIMESTAMP")


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS password_changed_at")
