"""Token de recuperacion de contraseña.

Se guarda solo el hash sha256 del token (no el plano), igual que con passwords.
Asi, si la DB se filtra, el atacante no puede usar los tokens directamente.

Vida util: 1 hora. Uso unico (used_at se setea al usarlo).
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index
from datetime import datetime

from app.database import Base


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    # Para auditoria: IP que pidio el reset
    requested_ip = Column(String(64), nullable=True)

    __table_args__ = (
        Index("idx_pwd_reset_user_expires", "user_id", "expires_at"),
    )
