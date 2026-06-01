from datetime import datetime
from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, Text, Numeric, Boolean
from sqlalchemy.orm import relationship
from app.database import Base


class Cheque(Base):
    __tablename__ = "cheques"

    id              = Column(Integer, primary_key=True, index=True)
    organizacion_id = Column(Integer, ForeignKey("organizaciones.id"), nullable=False, default=1, index=True)
    cliente_id      = Column(Integer, ForeignKey("clientes.id"), nullable=True, index=True)
    portador_id     = Column(Integer, ForeignKey("portadores.id"), nullable=True)
    numero          = Column(String, nullable=True)
    banco_origen    = Column(String, nullable=True)
    librador        = Column(String, nullable=True)    # renombrado de "titular"
    titular         = Column(String, nullable=True)    # deprecated — compat con registros anteriores
    monto           = Column(Numeric(12, 2), nullable=False)
    comision        = Column(Numeric(12, 2), nullable=False, default=0.0)
    porcentaje_comision = Column(Numeric(5, 4), nullable=True)
    codigo_postal   = Column(String, nullable=True)
    local_interior  = Column(String, nullable=True)    # "local" | "interior"
    fecha_emision   = Column(Date, nullable=True)
    fecha_deposito  = Column(Date, nullable=True)
    fecha_acred     = Column(Date, nullable=True)
    banco_cuenta_id = Column(Integer, ForeignKey("plan_cuentas.id"), nullable=True)  # banco usado al acreditar
    estado          = Column(String, nullable=False, default="registrado")  # registrado | depositado | acreditado | rechazado | anulado
    fecha_rechazo   = Column(Date, nullable=True)
    fisico          = Column(Boolean, nullable=True, default=False)
    fecha_devolucion = Column(Date, nullable=True)
    notas           = Column(String, nullable=True)
    foto_comprobante = Column(Text, nullable=True)
    usuario_id      = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow)

    cliente      = relationship("Cliente",      foreign_keys=[cliente_id])
    portador     = relationship("Portador",     foreign_keys=[portador_id])
    organizacion = relationship("Organizacion", foreign_keys=[organizacion_id])
    usuario      = relationship("User",         foreign_keys=[usuario_id])
