from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Date, Boolean
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
    # Huella digital para detectar duplicados: hash de (total, primer_orden, ultimo_orden, suma_montos)
    fingerprint = Column(String, nullable=True, index=True)

    # Relationships
    creado_por_user = relationship("User", back_populates="extractos")
    movimientos = relationship("MovimientoBanco", back_populates="extracto", cascade="all, delete-orphan")
    planillas = relationship("Planilla", back_populates="extracto")

class MovimientoBanco(Base):
    __tablename__ = "movimientos_banco"

    id = Column(Integer, primary_key=True, index=True)
    extracto_id = Column(Integer, ForeignKey("extractos_bancarios.id"), nullable=False)

    # Campos del extracto
    orden = Column(Integer, nullable=True)  # Número secuencial
    fecha = Column(Date, nullable=True)
    mes = Column(String, nullable=True)
    titular = Column(String, nullable=True)  # Concepto/CUIT del ordenante
    monto = Column(Float, nullable=False)
    saldo = Column(Float, nullable=True)

    # Acreditación
    cliente_acreditado = Column(String, nullable=True)  # Nombre del cliente acreditado
    fecha_acred = Column(Date, nullable=True)  # Fecha de acreditación

    # Relationships
    extracto = relationship("ExtractoBancario", back_populates="movimientos")
    planilla_rows = relationship("PlanillaRow", back_populates="movimiento_acreditado")
