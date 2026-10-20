"""Ficha de proveedores PROPIOS de la organización (a quien le compra).

No incluye a los proveedores de los clientes: una OP por cuenta de un cliente
(`Egreso.tipo == "pago_cliente"`) va a nombre del cliente y no se vincula acá.
Es la base para las retenciones (condición frente al IVA, regímenes).
"""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base

CONDICIONES_IVA = ["responsable_inscripto", "monotributo", "exento", "no_alcanzado"]
ORIGENES_PROVEEDOR = ["manual", "comprobantes"]


class Proveedor(Base):
    __tablename__ = "proveedores"
    __table_args__ = (UniqueConstraint("organizacion_id", "cuit", name="uq_proveedor_org_cuit"),)

    id              = Column(Integer, primary_key=True, index=True)
    organizacion_id = Column(Integer, ForeignKey("organizaciones.id"), nullable=False, index=True)
    cuit            = Column(String(11), nullable=True)       # 11 dígitos; null = proveedor informal
    razon_social    = Column(String(255), nullable=False)
    condicion_iva   = Column(String(30), nullable=True)       # ver CONDICIONES_IVA
    email           = Column(String(255), nullable=True)
    cbu             = Column(String(22), nullable=True)
    notas           = Column(Text, nullable=True)
    origen          = Column(String(20), nullable=False, default="manual")   # manual | comprobantes
    activo          = Column(Boolean, nullable=False, default=True)
    created_at      = Column(DateTime, default=datetime.utcnow)
    updated_at      = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organizacion    = relationship("Organizacion", foreign_keys=[organizacion_id])
