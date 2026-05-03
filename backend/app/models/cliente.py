from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class Cliente(Base):
    __tablename__ = "clientes"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False, index=True)
    cuit = Column(String, nullable=True)
    organizacion_id = Column(Integer, ForeignKey("organizaciones.id"), nullable=True, default=1)

    # Relationships
    planillas = relationship("Planilla", back_populates="cliente")
    organizacion = relationship("Organizacion", foreign_keys=[organizacion_id])
