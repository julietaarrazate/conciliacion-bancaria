from sqlalchemy import Column, Integer, String, ForeignKey, Numeric
from sqlalchemy.orm import relationship
from app.database import Base

class Cliente(Base):
    __tablename__ = "clientes"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False, index=True)
    cuit = Column(String, nullable=True)
    organizacion_id = Column(Integer, ForeignKey("organizaciones.id"), nullable=True, default=1)
    porcentaje_comision = Column(Numeric(5, 4), nullable=True)  # % comision propio; NULL = usa default org
    cuenta_contable_id = Column(Integer, ForeignKey("plan_cuentas.id"), nullable=True)  # cuenta corriente 2-1-2-X

    # Relationships
    planillas = relationship("Planilla", back_populates="cliente")
    organizacion = relationship("Organizacion", foreign_keys=[organizacion_id])
