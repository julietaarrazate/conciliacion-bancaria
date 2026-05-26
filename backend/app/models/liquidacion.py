from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Date, Text, Numeric
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class Liquidacion(Base):
    __tablename__ = "liquidaciones"

    id = Column(Integer, primary_key=True, index=True)
    organizacion_id = Column(Integer, ForeignKey("organizaciones.id"), nullable=False, index=True)

    periodo_inicio = Column(Date, nullable=False)
    periodo_fin    = Column(Date, nullable=False)

    # borrador → aprobada → pagada
    estado = Column(String, default="borrador", nullable=False)

    total_conciliado = Column(Numeric(12, 2), default=0)
    total_comision   = Column(Numeric(12, 2), default=0)
    total_neto       = Column(Numeric(12, 2), default=0)
    notas            = Column(Text, nullable=True)

    created_by  = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at  = Column(DateTime, default=datetime.utcnow)
    aprobado_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    aprobado_at = Column(DateTime, nullable=True)

    organizacion = relationship("Organizacion", foreign_keys=[organizacion_id])
    creador      = relationship("User", foreign_keys=[created_by])
    aprobador    = relationship("User", foreign_keys=[aprobado_by])
    detalles     = relationship("LiquidacionDetalle", back_populates="liquidacion",
                                cascade="all, delete-orphan")


class LiquidacionDetalle(Base):
    __tablename__ = "liquidacion_detalles"

    id             = Column(Integer, primary_key=True, index=True)
    liquidacion_id = Column(Integer, ForeignKey("liquidaciones.id"), nullable=False)
    cliente_id     = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    cliente_nombre = Column(String, nullable=False)

    monto_conciliado    = Column(Numeric(12, 2), default=0)
    porcentaje_comision = Column(Numeric(5, 4), default=0)
    monto_comision      = Column(Numeric(12, 2), default=0)
    monto_neto          = Column(Numeric(12, 2), default=0)
    observaciones       = Column(Text, nullable=True)

    liquidacion = relationship("Liquidacion", back_populates="detalles")
    cliente     = relationship("Cliente", foreign_keys=[cliente_id])


class CierrePeriodo(Base):
    __tablename__ = "cierres_periodo"

    id             = Column(Integer, primary_key=True, index=True)
    organizacion_id = Column(Integer, ForeignKey("organizaciones.id"), nullable=False, index=True)
    periodo_inicio = Column(Date, nullable=False)
    periodo_fin    = Column(Date, nullable=False)
    cerrado_at     = Column(DateTime, default=datetime.utcnow)
    cerrado_by     = Column(Integer, ForeignKey("users.id"), nullable=False)
    liquidacion_id = Column(Integer, ForeignKey("liquidaciones.id"), nullable=True)

    organizacion = relationship("Organizacion", foreign_keys=[organizacion_id])
    cerrador     = relationship("User", foreign_keys=[cerrado_by])
    liquidacion  = relationship("Liquidacion", foreign_keys=[liquidacion_id])
