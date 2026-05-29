from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
import enum


class RoleEnum(str, enum.Enum):
    ADMIN = "admin"
    OPERADOR = "operador"
    REVISOR = "revisor"
    AUDITOR = "auditor"
    CONTADOR = "contador"  # contador de prueba: opera pero NO borra; login por aprobación


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default=RoleEnum.OPERADOR.value, nullable=False)
    is_active = Column(Boolean, default=True)
    # Multi-tenant
    organizacion_id = Column(Integer, ForeignKey("organizaciones.id"), nullable=True, default=1)
    is_superadmin = Column(Boolean, default=False, nullable=False)
    # Lista de org IDs extras a los que este usuario puede cambiar (solo CONTADOR)
    allowed_org_ids = Column(JSON, nullable=True, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    planillas = relationship("Planilla", back_populates="usuario")
    auditoria = relationship("AuditoriaLog", back_populates="usuario")
    extractos = relationship("ExtractoBancario", back_populates="creado_por_user")
    organizacion = relationship("Organizacion", foreign_keys=[organizacion_id])
