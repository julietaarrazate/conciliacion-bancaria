from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
import enum

class RoleEnum(str, enum.Enum):
    ADMIN = "admin"
    OPERADOR = "operador"
    REVISOR = "revisor"
    AUDITOR = "auditor"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(RoleEnum), default=RoleEnum.OPERADOR)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    planillas = relationship("Planilla", back_populates="usuario")
    auditoria = relationship("AuditoriaLog", back_populates="usuario")
    extractos = relationship("ExtractoBancario", back_populates="creado_por_user")
