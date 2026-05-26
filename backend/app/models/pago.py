from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, Numeric
from sqlalchemy.orm import relationship
from app.database import Base


class Pago(Base):
    __tablename__ = "pagos"

    id              = Column(Integer, primary_key=True, index=True)
    organizacion_id = Column(Integer, ForeignKey("organizaciones.id"), nullable=False, default=1, index=True)
    cliente_id      = Column(Integer, ForeignKey("clientes.id"), nullable=True, index=True)
    concepto        = Column(String, nullable=True)
    monto           = Column(Numeric(12, 2), nullable=False)
    medio           = Column(String, nullable=False, default="banco")  # banco | efectivo
    fecha           = Column(Date, nullable=True)
    referencia      = Column(String, nullable=True)
    notas           = Column(String, nullable=True)
    usuario_id      = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow)

    cliente      = relationship("Cliente", foreign_keys=[cliente_id])
    organizacion = relationship("Organizacion", foreign_keys=[organizacion_id])
    usuario      = relationship("User", foreign_keys=[usuario_id])


class Gasto(Base):
    __tablename__ = "gastos"

    id              = Column(Integer, primary_key=True, index=True)
    organizacion_id = Column(Integer, ForeignKey("organizaciones.id"), nullable=False, default=1, index=True)
    concepto        = Column(String, nullable=False)
    categoria       = Column(String, nullable=True)   # impuestos | bancarios | otros
    monto           = Column(Numeric(12, 2), nullable=False)
    medio           = Column(String, nullable=False, default="banco")  # banco | efectivo
    fecha           = Column(Date, nullable=True)
    referencia      = Column(String, nullable=True)
    notas           = Column(String, nullable=True)
    usuario_id      = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow)

    organizacion = relationship("Organizacion", foreign_keys=[organizacion_id])
    usuario      = relationship("User", foreign_keys=[usuario_id])
