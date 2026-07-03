"""Modelos de la liquidación REAL de IVA (Excel "Mis Comprobantes" de ARCA).

Distinto del módulo de *proyección* (`proyeccion_iva.py`): acá el débito/crédito
NO se estiman sobre los asientos contables, sino que se importan de los archivos
oficiales "Mis Comprobantes Emitidos/Recibidos" que ARCA le entrega al contador.

- `ComprobanteIva`: cada fila del Excel de ARCA (una factura/NC/recibo). Es
  staging re-importable — el UNIQUE (org, direccion, tipo, PV, número, cuit)
  deduplica al re-subir el mismo período. `incluido` permite excluir a mano un
  comprobante del cálculo sin borrarlo.
- `LiquidacionIva`: snapshot mensual del cálculo de posición de IVA con la
  mecánica real de saldos técnicos / de libre disponibilidad. UNIQUE (org,
  período): un registro por período por org, upsert al recalcular; si está
  'presentada' NO se recalcula.

Todos los montos en Decimal (columnas Numeric ya devuelven Decimal).
"""

from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Date, DateTime, ForeignKey, Numeric, JSON,
    Boolean, UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class ComprobanteIva(Base):
    __tablename__ = "comprobantes_iva"

    id                   = Column(Integer, primary_key=True, index=True)
    organizacion_id      = Column(Integer, ForeignKey("organizaciones.id"), nullable=False, index=True)
    direccion            = Column(String(10), nullable=False)   # 'emitido' | 'recibido'
    periodo              = Column(String(7), nullable=False)     # 'YYYY-MM'
    fecha                = Column(Date, nullable=False)
    tipo_codigo          = Column(Integer, nullable=False)       # 1, 6, 11, 3 (NC A), ...
    tipo_desc            = Column(String(80), nullable=True)     # "1 - Factura A"
    punto_venta          = Column(Integer, nullable=True)
    numero               = Column(Integer, nullable=True)        # "Número Desde"
    cuit_contraparte     = Column(String(20), nullable=True)     # receptor (emitido) / emisor (recibido)
    denominacion         = Column(String(255), nullable=True)
    neto_gravado_total   = Column(Numeric(14, 2), nullable=False, default=0)
    total_iva            = Column(Numeric(14, 2), nullable=False, default=0)
    imp_total            = Column(Numeric(14, 2), nullable=False, default=0)
    detalle_alicuotas    = Column(JSON, nullable=True)           # {alícuota: {neto, iva}} solo no-nulas
    incluido             = Column(Boolean, nullable=False, default=True)
    archivo_origen       = Column(String(255), nullable=True)
    created_at           = Column(DateTime, default=datetime.utcnow)

    organizacion = relationship("Organizacion", foreign_keys=[organizacion_id])

    __table_args__ = (
        UniqueConstraint(
            "organizacion_id", "direccion", "tipo_codigo",
            "punto_venta", "numero", "cuit_contraparte",
            name="uq_comprobante_iva_dedup",
        ),
    )


class LiquidacionIva(Base):
    __tablename__ = "liquidaciones_iva"

    id                     = Column(Integer, primary_key=True, index=True)
    organizacion_id        = Column(Integer, ForeignKey("organizaciones.id"), nullable=False, index=True)
    periodo                = Column(String(7), nullable=False)   # 'YYYY-MM'

    debito_fiscal          = Column(Numeric(14, 2), nullable=False, default=0)
    credito_fiscal         = Column(Numeric(14, 2), nullable=False, default=0)
    tecnico_periodo        = Column(Numeric(14, 2), nullable=False, default=0)  # débito - crédito
    saldo_tecnico_anterior = Column(Numeric(14, 2), nullable=False, default=0)
    saldo_tecnico_nuevo    = Column(Numeric(14, 2), nullable=False, default=0)
    retenciones            = Column(Numeric(14, 2), nullable=False, default=0)
    percepciones           = Column(Numeric(14, 2), nullable=False, default=0)
    saldo_libre_anterior   = Column(Numeric(14, 2), nullable=False, default=0)
    saldo_libre_nuevo      = Column(Numeric(14, 2), nullable=False, default=0)
    saldo_a_pagar          = Column(Numeric(14, 2), nullable=False, default=0)

    cant_emitidos          = Column(Integer, nullable=False, default=0)
    cant_recibidos         = Column(Integer, nullable=False, default=0)
    estado                 = Column(String(20), nullable=False, default="borrador")  # borrador | presentada
    fecha_presentacion     = Column(DateTime, nullable=True)
    created_at             = Column(DateTime, default=datetime.utcnow)
    updated_at             = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organizacion = relationship("Organizacion", foreign_keys=[organizacion_id])

    __table_args__ = (
        UniqueConstraint("organizacion_id", "periodo", name="uq_liquidacion_iva_org_periodo"),
    )
