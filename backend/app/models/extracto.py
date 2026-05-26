from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Date, Boolean, Numeric
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class ExtractoBancario(Base):
    __tablename__ = "extractos_bancarios"

    id = Column(Integer, primary_key=True, index=True)
    nombre_archivo = Column(String, nullable=False)
    creado_por = Column(Integer, ForeignKey("users.id"), nullable=False)
    fecha_creacion = Column(DateTime, default=datetime.utcnow)
    fecha_extracto = Column(Date, nullable=True)
    fingerprint = Column(String, nullable=True, index=True)
    banco = Column(String, nullable=True, default="Banco Macro")
    organizacion_id = Column(Integer, ForeignKey("organizaciones.id"), nullable=True, default=1)
    deleted_at = Column(DateTime, nullable=True, index=True)  # soft delete: NULL = activo

    # Relationships
    creado_por_user = relationship("User", back_populates="extractos")
    movimientos = relationship("MovimientoBanco", back_populates="extracto", cascade="all, delete-orphan")
    planillas = relationship("Planilla", back_populates="extracto")
    organizacion = relationship("Organizacion", foreign_keys=[organizacion_id])

class MovimientoBanco(Base):
    __tablename__ = "movimientos_banco"

    id = Column(Integer, primary_key=True, index=True)
    extracto_id = Column(Integer, ForeignKey("extractos_bancarios.id"), nullable=False)

    orden = Column(Integer, nullable=True)
    fecha = Column(Date, nullable=True)
    mes = Column(String, nullable=True)
    titular = Column(String, nullable=True)
    monto = Column(Numeric(12, 2), nullable=False)
    saldo = Column(Numeric(12, 2), nullable=True)

    cliente_acreditado = Column(String, nullable=True)
    fecha_acred = Column(Date, nullable=True)
    source = Column(String, nullable=True, default='extracto')
    um_lote = Column(Integer, nullable=True)
    organizacion_id = Column(Integer, ForeignKey("organizaciones.id"), nullable=True, default=1)

    # Relationships
    extracto = relationship("ExtractoBancario", back_populates="movimientos")
    planilla_rows = relationship("PlanillaRow", back_populates="movimiento_acreditado")
    organizacion = relationship("Organizacion", foreign_keys=[organizacion_id])
