"""005_revoked_tokens — tabla para JWT revocados (logout efectivo)

Cada entrada vive hasta `expires_at` (cuando el token habria expirado).
"""

from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "revoked_tokens",
        sa.Column("jti", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.Integer, nullable=True),
        sa.Column("revoked_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime, nullable=False),
        if_not_exists=True,
    )
    op.create_index("idx_revoked_user", "revoked_tokens", ["user_id"], if_not_exists=True)
    op.create_index("idx_revoked_expires", "revoked_tokens", ["expires_at"], if_not_exists=True)


def downgrade() -> None:
    op.drop_index("idx_revoked_expires", table_name="revoked_tokens")
    op.drop_index("idx_revoked_user", table_name="revoked_tokens")
    op.drop_table("revoked_tokens")
