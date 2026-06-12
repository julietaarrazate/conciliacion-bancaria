"""Modelo de liquidaciones de tarjetas de crédito (Visa / Mastercard / Amex).

Cada liquidación representa la acreditación mensual de una marca de tarjeta:
el banco deposita el neto, reteniendo aranceles, IVA crédito fiscal,
percepciones de IIBB y retenciones de impuestos. El asiento contable
agrupado (módulo `tarjeta_liq`) descompone esos componentes.

Invariante contable:
    neto + aranceles + iva_df + percepciones_iibb + retenciones == monto_bruto
"""

from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Column, Integer, String, Date, DateTime, ForeignKey, Text, Numeric,
    Enum as SAEnum,
)
from sqlalchemy.orm import relationship

from app.database import Base


class MarcaTarjeta(str, Enum):
    visa = "visa"
    mastercard = "mastercard"
    amex = "amex"


class EstadoTarjeta(str, Enum):
    pendiente = "pendiente"
    conciliada = "conciliada"
    anulada = "anulada"


class LiquidacionTarjeta(Base):
    __tablename__ = "liquidaciones_tarjeta"

    id                     = Column(Integer, primary_key=True, index=True)
    organizacion_id        = Column(Integer, ForeignKey("organizaciones.id"), nullable=False, index=True)
    marca                  = Column(SAEnum(MarcaTarjeta, name="marca_tarjeta"), nullable=False)
    periodo                = Column(String(7), nullable=False)        # "2026-05"
    fecha_acreditacion     = Column(Date, nullable=False)
    monto_bruto            = Column(Numeric(12, 2), nullable=False)
    aranceles              = Column(Numeric(12, 2), nullable=False, default=0)
    iva_df                 = Column(Numeric(12, 2), nullable=False, default=0)
    percepciones_iibb      = Column(Numeric(12, 2), nullable=False, default=0)
    retenciones            = Column(Numeric(12, 2), nullable=False, default=0)
    neto                   = Column(Numeric(12, 2), nullable=False)  # calculado, guardado
    estado                 = Column(String(20), default="pendiente")
    extracto_movimiento_id = Column(Integer, ForeignKey("movimientos_banco.id"), nullable=True)
    archivo_original       = Column(String(255), nullable=True)
    asiento_id             = Column(Integer, ForeignKey("asientos.id"), nullable=True)
    notas                  = Column(Text, nullable=True)
    usuario_id             = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at             = Column(DateTime, default=datetime.utcnow)
    deleted_at             = Column(DateTime, nullable=True)         # soft delete: NULL = activo

    organizacion = relationship("Organizacion", foreign_keys=[organizacion_id])
    movimiento   = relationship("MovimientoBanco", foreign_keys=[extracto_movimiento_id])
    usuario      = relationship("User", foreign_keys=[usuario_id])
