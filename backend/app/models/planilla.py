from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Date
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class Planilla(Base):
    __tablename__ = "planillas"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    extracto_id = Column(Integer, ForeignKey("extractos_bancarios.id"), nullable=False)
    usuario_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    nombre_archivo = Column(String, nullable=False)
    fecha_carga = Column(DateTime, default=datetime.utcnow)

    # Relationships
    cliente = relationship("Cliente", back_populates="planillas")
    extracto = relationship("ExtractoBancario", back_populates="planillas")
    usuario = relationship("User", back_populates="planillas")
    rows = relationship("PlanillaRow", back_populates="planilla", cascade="all, delete-orphan")

class PlanillaRow(Base):
    __tablename__ = "planilla_rows"

    id = Column(Integer, primary_key=True, index=True)
    planilla_id = Column(Integer, ForeignKey("planillas.id"), nullable=False)

    # Datos de la planilla
    monto = Column(Float, nullable=False)
    cuit = Column(String, nullable=True)
    titular = Column(String, nullable=True)

    # Resultado de la conciliación
    status = Column(String, nullable=False)  # "ok", "no está", "duplicado", "faltan datos", "acreditado DD/MM"
    orden_movimiento_acreditado = Column(Integer, ForeignKey("movimientos_banco.id"), nullable=True)

    # Relationships
    planilla = relationship("Planilla", back_populates="rows")
    movimiento_acreditado = relationship("MovimientoBanco", back_populates="planilla_rows")
