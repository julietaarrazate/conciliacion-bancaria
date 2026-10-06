"""Modelos de "Comprobantes por revisar": facturas de compra que llegan por mail
o se suben a mano, se leen con IA y quedan como borrador hasta que alguien del
estudio las confirma.

- `BuzonComprobantes`: la dirección de mail propia de cada organización
  (`facturas-<token>@<INBOUND_EMAIL_DOMAIN>`). Opt-in: no existe hasta que un
  admin la activa; regenerar el token invalida la dirección anterior.
- `BorradorComprobante`: un archivo (PDF/foto) con los datos que leyó la IA.
  Nada impacta en IVA ni en Pagos hasta `confirmar`: ahí se crea el
  `ComprobanteIva` (dirección "recibido") y, opcionalmente, el `Egreso`.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON,
    Index, UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


# Estados del borrador:
#   procesando  → recién llegado, la IA todavía no lo leyó
#   listo       → leído, esperando revisión
#   error       → no se pudo leer (archivo ilegible, sin IA configurada, etc.)
#   sin_adjunto → mail sin PDF/foto (p. ej. la confirmación de reenvío de Gmail)
#   confirmado  → ya impactó en IVA (y en Pagos si se pidió)
#   descartado  → descartado a mano
ESTADOS_BORRADOR = ["procesando", "listo", "error", "sin_adjunto", "confirmado", "descartado"]
ORIGENES_BORRADOR = ["email", "subida"]


class BuzonComprobantes(Base):
    """Dirección de mail para recibir comprobantes — 1 por organización."""

    __tablename__ = "buzon_comprobantes"

    id              = Column(Integer, primary_key=True, index=True)
    organizacion_id = Column(Integer, ForeignKey("organizaciones.id"), nullable=False, unique=True, index=True)
    token           = Column(String(32), nullable=False, unique=True, index=True)
    activo          = Column(Boolean, nullable=False, default=True)
    created_at      = Column(DateTime, default=datetime.utcnow)
    updated_at      = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organizacion    = relationship("Organizacion", foreign_keys=[organizacion_id])


class BorradorComprobante(Base):
    __tablename__ = "borradores_comprobante"

    id              = Column(Integer, primary_key=True, index=True)
    organizacion_id = Column(Integer, ForeignKey("organizaciones.id"), nullable=False, index=True)

    origen          = Column(String(10), nullable=False, default="subida")   # email | subida
    estado          = Column(String(20), nullable=False, default="procesando")

    # Datos del mail (solo origen=email). email_id + adjunto_id hacen idempotente
    # el webhook de Resend (reintenta si no respondemos 200 a tiempo).
    email_id        = Column(String(64), nullable=True)
    adjunto_id      = Column(String(64), nullable=True)
    remitente       = Column(String(255), nullable=True)
    asunto          = Column(String(500), nullable=True)

    # Archivo: URL si hay S3/R2, data URL base64 si no (igual que cheques/pagos).
    archivo_nombre  = Column(String(255), nullable=True)
    archivo_mime    = Column(String(100), nullable=True)
    archivo         = Column(Text, nullable=True)

    # Lo que leyó la IA (y lo que corrigió la persona al confirmar). Montos como
    # string para no perder precisión en el JSON (ver DATABASE_RULES §1).
    datos           = Column(JSON, nullable=True)
    alertas         = Column(JSON, nullable=True)      # lista de textos para la persona
    error           = Column(Text, nullable=True)

    comprobante_iva_id = Column(Integer, ForeignKey("comprobantes_iva.id"), nullable=True)
    egreso_id          = Column(Integer, ForeignKey("egresos.id"), nullable=True)

    creado_por      = Column(Integer, ForeignKey("users.id"), nullable=True)
    confirmado_por  = Column(Integer, ForeignKey("users.id"), nullable=True)
    confirmado_at   = Column(DateTime, nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow)
    updated_at      = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organizacion    = relationship("Organizacion", foreign_keys=[organizacion_id])

    __table_args__ = (
        UniqueConstraint("organizacion_id", "email_id", "adjunto_id", name="uq_borrador_email_adjunto"),
        Index("ix_borrador_comprobante_org_estado", "organizacion_id", "estado"),
        Index("ix_borrador_comprobante_email", "email_id"),
    )
