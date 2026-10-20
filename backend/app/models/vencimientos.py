"""Vencimientos impositivos: calendario general + marcas manuales por org.

`CalendarioVencimiento` es GENERAL (no por organización): lo que publica ARCA
(u otro organismo) mes a mes — impuesto + período fiscal + bloque de
terminación de CUIT → fecha. Lo carga el superadmin desde la web oficial.

`VencimientoMarcado` es POR ORG: "esta obligación ya se presentó/pagó" para
lo que ningún módulo registra (p. ej. la cuota de Monotributo) o se hizo por
fuera de Cuadra. Ver services/vencimientos.py.
"""
from datetime import datetime

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint

from app.database import Base

# Impuestos que entiende la grilla. Clave → nombre visible.
IMPUESTOS = {
    "iva": "IVA (F.2002)",
    "monotributo": "Monotributo",
    "iibb_cm": "IIBB Convenio Multilateral",
    "f931": "F.931 cargas sociales",
}


class CalendarioVencimiento(Base):
    __tablename__ = "calendario_vencimientos"

    id                = Column(Integer, primary_key=True, index=True)
    impuesto          = Column(String(20), nullable=False)    # clave de IMPUESTOS
    periodo           = Column(String(7), nullable=False)     # período fiscal 'YYYY-MM'
    terminacion_desde = Column(Integer, nullable=False)       # último dígito del CUIT, 0..9
    terminacion_hasta = Column(Integer, nullable=False)
    fecha             = Column(Date, nullable=False)
    fuente            = Column(String(255), nullable=True)    # de dónde salió (URL / RG)
    cargado_por       = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at        = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("impuesto", "periodo", "terminacion_desde", name="uq_calendario_venc_bloque"),
    )


class VencimientoMarcado(Base):
    __tablename__ = "vencimientos_marcados"

    id              = Column(Integer, primary_key=True, index=True)
    organizacion_id = Column(Integer, ForeignKey("organizaciones.id"), nullable=False, index=True)
    impuesto        = Column(String(20), nullable=False)
    periodo         = Column(String(7), nullable=False)
    marcado_por     = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    marcado_at      = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("organizacion_id", "impuesto", "periodo", name="uq_vencimiento_marcado"),
    )
