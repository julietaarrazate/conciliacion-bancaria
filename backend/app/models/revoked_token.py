from sqlalchemy import Column, String, Integer, DateTime
from sqlalchemy.sql import func
from app.database import Base


class RevokedToken(Base):
    """JWT revocados — se chequean en cada request autenticado.

    Una entrada vive hasta `expires_at` (cuando el token habria expirado).
    Despues se purga automaticamente.
    """
    __tablename__ = "revoked_tokens"

    jti = Column(String(64), primary_key=True)
    user_id = Column(Integer, nullable=True, index=True)
    revoked_at = Column(DateTime, server_default=func.now(), nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
