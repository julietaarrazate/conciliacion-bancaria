from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Date, Boolean, Text, JSON, Numeric
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
from app.services.tz import hoy_art


# Tipos de egreso soportados por el módulo unificado "Pagos"
TIPOS_EGRESO = ["proveedor", "gasto", "pago_cliente"]
FORMAS_PAGO  = ["banco", "efectivo"]


class CategoriaEgreso(Base):
    """Categoría editable por la usuaria (impuestos, bancarios, alquiler, etc.).
    Sembrada con las categorías que existían en el modelo Gasto viejo."""
    __tablename__ = "categorias_egreso"

    id              = Column(Integer, primary_key=True, index=True)
    organizacion_id = Column(Integer, ForeignKey("organizaciones.id"), nullable=False, index=True)
    nombre          = Column(String, nullable=False)
    activo          = Column(Boolean, default=True)
    created_at      = Column(DateTime, default=datetime.utcnow)

    organizacion    = relationship("Organizacion", foreign_keys=[organizacion_id])


class Egreso(Base):
    """Módulo unificado de egresos: reemplaza OrdenDePago + Pago + Gasto.
    Un egreso es cualquier salida de plata con comprobante:
    - tipo=proveedor      → pago a proveedor (la vieja OP)
    - tipo=gasto          → gasto operativo (el viejo Gasto)
    - tipo=pago_cliente   → devolución/pago a un cliente (el viejo Pago)
    """
    __tablename__ = "egresos"

    id              = Column(Integer, primary_key=True, index=True)
    organizacion_id = Column(Integer, ForeignKey("organizaciones.id"), nullable=False, index=True)

    tipo            = Column(String, nullable=False, default="gasto", index=True)   # proveedor | gasto | pago_cliente
    categoria       = Column(String, nullable=True)
    forma_pago      = Column(String, nullable=False, default="banco", index=True)  # banco | efectivo

    monto           = Column(Numeric(12, 2), nullable=False)
    fecha           = Column(Date, nullable=False, default=hoy_art, index=True)

    beneficiario    = Column(String, nullable=True)                       # proveedor / destinatario
    cliente_id      = Column(Integer, ForeignKey("clientes.id"), nullable=True, index=True)
    concepto        = Column(String, nullable=True)
    referencia      = Column(String, nullable=True)

    # Comprobante (foto firmada). URL si hay S3/R2, base64 si no (igual que OP/cheques).
    foto_comprobante    = Column(Text, nullable=True)
    compartido_whatsapp = Column(Boolean, default=False)

    # Vínculo con la caja física (solo si forma_pago == efectivo)
    arqueo_id             = Column(Integer, ForeignKey("arqueos_diarios.id"), nullable=True)
    denominaciones_usadas = Column(JSON, nullable=True)   # {"20000": 2, "10000": 1}

    notas           = Column(Text, nullable=True)

    usuario_id      = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow)

    organizacion    = relationship("Organizacion", foreign_keys=[organizacion_id])
    cliente         = relationship("Cliente",      foreign_keys=[cliente_id])
    arqueo          = relationship("ArqueoDiario",  foreign_keys=[arqueo_id], back_populates="egresos")
    usuario         = relationship("User",          foreign_keys=[usuario_id])
