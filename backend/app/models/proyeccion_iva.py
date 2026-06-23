"""Modelo de proyección de IVA y DDJJ por período.

Cada registro es un snapshot del IVA proyectado de un período (mes), calculado a
partir de los asientos contables del período cruzados con la `tasa_iva`
configurada en cada cuenta del plan.

- `debito_fiscal`: IVA débito proyectado (sobre ingresos gravados reconocidos).
- `credito_fiscal`: IVA crédito total = proyectado (sobre gastos gravados) +
  real ya contabilizado en la cuenta 1-1-2-4 IVA Crédito Fiscal.
- `saldo`: debito_fiscal - credito_fiscal. Positivo = a pagar a ARCA;
  negativo = saldo a favor.

Constraint único `(organizacion_id, periodo)`: un solo registro por período por
organización. Al recalcular se hace upsert (no se duplica). Si el período ya está
en estado "presentado", el recálculo NO lo pisa.
"""

from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, Numeric, JSON,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class ProyeccionIva(Base):
    __tablename__ = "proyecciones_iva"

    id                 = Column(Integer, primary_key=True, index=True)
    organizacion_id    = Column(Integer, ForeignKey("organizaciones.id"), nullable=False, index=True)
    periodo            = Column(String(7), nullable=False)        # "YYYY-MM"
    debito_fiscal      = Column(Numeric(12, 2), nullable=False, default=0)
    credito_fiscal     = Column(Numeric(12, 2), nullable=False, default=0)
    saldo              = Column(Numeric(12, 2), nullable=False, default=0)  # +: a pagar, -: a favor
    estado             = Column(String(20), nullable=False, default="proyectado")  # proyectado | presentado
    fecha_presentacion = Column(DateTime, nullable=True)
    detalle            = Column(JSON, nullable=True)              # desglose por cuenta
    created_at         = Column(DateTime, default=datetime.utcnow)
    updated_at         = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organizacion = relationship("Organizacion", foreign_keys=[organizacion_id])

    __table_args__ = (
        UniqueConstraint("organizacion_id", "periodo", name="uq_proyeccion_iva_org_periodo"),
    )
