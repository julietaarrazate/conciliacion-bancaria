from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Date, Numeric
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class PlanCuenta(Base):
    __tablename__ = "plan_cuentas"

    id            = Column(Integer, primary_key=True, index=True)
    codigo        = Column(String, nullable=False, index=True)
    nombre        = Column(String, nullable=False)
    tipo          = Column(String, nullable=True)  # "activo" | "pasivo" | "resultado"
    parent_id     = Column(Integer, ForeignKey("plan_cuentas.id"), nullable=True)
    nivel         = Column(Integer, nullable=False, default=1)
    activo        = Column(Boolean, default=True)
    tasa_iva      = Column(Numeric(5, 4), nullable=True)  # % IVA de la cuenta: 0.21, 0.105, 0=exento, NULL=no aplica
    organizacion_id = Column(Integer, ForeignKey("organizaciones.id"), nullable=True, default=1)
    created_at    = Column(DateTime, default=datetime.utcnow)

    organizacion  = relationship("Organizacion", foreign_keys=[organizacion_id])


class ReglaContable(Base):
    __tablename__ = "reglas_contables"

    id              = Column(Integer, primary_key=True, index=True)
    evento          = Column(String, nullable=False, index=True)
    descripcion     = Column(String, nullable=True)
    cuenta_debe_id  = Column(Integer, ForeignKey("plan_cuentas.id"), nullable=False)
    cuenta_haber_id = Column(Integer, ForeignKey("plan_cuentas.id"), nullable=False)
    activo          = Column(Boolean, default=True)
    organizacion_id = Column(Integer, ForeignKey("organizaciones.id"), nullable=True, default=1)
    created_at      = Column(DateTime, default=datetime.utcnow)

    cuenta_debe    = relationship("PlanCuenta", foreign_keys=[cuenta_debe_id])
    cuenta_haber   = relationship("PlanCuenta", foreign_keys=[cuenta_haber_id])
    organizacion   = relationship("Organizacion", foreign_keys=[organizacion_id])


class Asiento(Base):
    __tablename__ = "asientos"

    id              = Column(Integer, primary_key=True, index=True)
    numero_asiento  = Column(Integer, nullable=True, index=True)  # número correlativo de visualización
    fecha           = Column(Date, nullable=False)
    descripcion     = Column(String, nullable=True)
    modulo          = Column(String, nullable=True)   # "extracto" | "planilla" | "caja" | "cheque"
    referencia_id   = Column(Integer, nullable=True)  # FK lógico al registro origen
    organizacion_id = Column(Integer, ForeignKey("organizaciones.id"), nullable=True, default=1)
    usuario_id      = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow)

    lineas        = relationship("AsientoDetalle", back_populates="asiento", cascade="all, delete-orphan")
    organizacion  = relationship("Organizacion", foreign_keys=[organizacion_id])
    usuario       = relationship("User", foreign_keys=[usuario_id])


class AsientoDetalle(Base):
    __tablename__ = "asiento_detalle"

    id         = Column(Integer, primary_key=True, index=True)
    asiento_id = Column(Integer, ForeignKey("asientos.id"), nullable=False)
    cuenta_id  = Column(Integer, ForeignKey("plan_cuentas.id"), nullable=False)
    debe       = Column(Numeric(12, 2), default=0.0)
    haber      = Column(Numeric(12, 2), default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    asiento = relationship("Asiento", back_populates="lineas")
    cuenta  = relationship("PlanCuenta", foreign_keys=[cuenta_id])
