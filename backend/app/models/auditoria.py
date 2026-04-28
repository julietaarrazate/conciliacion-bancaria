from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class AuditoriaLog(Base):
    __tablename__ = "auditoria"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    tabla = Column(String, nullable=False)  # Nombre de tabla afectada
    registro_id = Column(Integer, nullable=False)  # ID del registro
    accion = Column(String, nullable=False)  # "INSERT", "UPDATE", "DELETE"
    cambios = Column(JSON, nullable=True)  # {"antes": {...}, "despues": {...}}

    timestamp = Column(DateTime, default=datetime.utcnow)

    # Relationships
    usuario = relationship("User", back_populates="auditoria")
