from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base


class Cheque(Base):
    __tablename__ = "cheques"

    id              = Column(Integer, primary_key=True, index=True)
    organizacion_id = Column(Integer, ForeignKey("organizaciones.id"), nullable=False, default=1, index=True)
    cliente_id      = Column(Integer, ForeignKey("clientes.id"), nullable=True, index=True)
    numero          = Column(String, nullable=True)
    banco_origen    = Column(String, nullable=True)
    titular         = Column(String, nullable=True)
    monto           = Column(Float, nullable=False)
    comision        = Column(Float, nullable=False, default=0.0)
    fecha_emision   = Column(Date, nullable=True)
    fecha_deposito  = Column(Date, nullable=True)
    fecha_acred     = Column(Date, nullable=True)
    estado          = Column(String, nullable=False, default="pendiente")  # pendiente | acreditado | rechazado
    notas              = Column(String, nullable=True)
    foto_comprobante   = Column(Text, nullable=True)  # base64 de la imagen
    usuario_id         = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow)

    cliente      = relationship("Cliente", foreign_keys=[cliente_id])
    organizacion = relationship("Organizacion", foreign_keys=[organizacion_id])
    usuario      = relationship("User", foreign_keys=[usuario_id])
