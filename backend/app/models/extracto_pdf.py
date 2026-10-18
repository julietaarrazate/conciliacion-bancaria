"""Modelos del importador de extractos bancarios en PDF.

- `BorradorExtractoPdf`: lo que se leyó de un PDF, pendiente de revisión. Nada
  impacta en `extractos_bancarios` / `movimientos_banco` hasta `confirmar`: ahí se
  crea un extracto nuevo (igual que el upload de Excel) o se agregan solo los
  movimientos nuevos a uno existente (igual que el UM). El PDF en sí no se guarda:
  solo su sha256, para no importar dos veces el mismo archivo.
- `MoldeExtractoPdf`: formato aprendido por organización (la "forma" de la tabla de
  un banco). Un formato leído una vez —por la lectura automática o por la IA— y
  confirmado por la persona se lee la próxima vez sin IA y sin costo.

Montos de `datos` como string ("-1234.56") para no perder precisión en el JSON
(ver DATABASE_RULES §1). Tablas nuevas, sin columnas nuevas en tablas existentes.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Column, Date, DateTime, ForeignKey, Index, Integer, JSON, Numeric, String, Text,
    UniqueConstraint,
)

from app.database import Base


# Estados del borrador:
#   procesando  → leyéndose con IA en segundo plano
#   listo       → leído (con o sin filas), esperando revisión
#   error       → no se pudo leer (o la lectura se interrumpió)
#   confirmando → guardándose (transición atómica: evita doble confirmación)
#   confirmado  → ya es un extracto (o se agregó a uno existente)
#   descartado  → descartado a mano
ESTADOS_BORRADOR_PDF = ["procesando", "listo", "error", "confirmando", "confirmado", "descartado"]
ESTADOS_PENDIENTES_PDF = ["procesando", "listo", "error"]
ORIGENES_MOLDE = ["automatico", "ia"]


class MoldeExtractoPdf(Base):
    """Formato de extracto PDF aprendido (por organización)."""

    __tablename__ = "moldes_extracto_pdf"

    id              = Column(Integer, primary_key=True)
    organizacion_id = Column(Integer, ForeignKey("organizaciones.id"), nullable=False)
    banco_clave     = Column(String(40), nullable=True)
    # Huella del encabezado de la tabla (la calcula el lector). Única por org.
    firma           = Column(String(64), nullable=False)
    # Bandas de columnas / reglas que entiende el lector (JSON propio del lector).
    layout          = Column(JSON, nullable=False)
    origen          = Column(String(20), nullable=True)            # automatico | ia
    confirmaciones  = Column(Integer, nullable=False, default=0)
    creado_at       = Column(DateTime, default=datetime.utcnow)
    ultimo_uso_at   = Column(DateTime, nullable=True)
    creado_por      = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        # El índice del UNIQUE (organizacion_id primero) sirve también para filtrar por org.
        UniqueConstraint("organizacion_id", "firma", name="uq_molde_extracto_pdf_org_firma"),
    )


class BorradorExtractoPdf(Base):
    """Un PDF de extracto leído y pendiente de revisión."""

    __tablename__ = "borradores_extracto_pdf"

    id              = Column(Integer, primary_key=True)
    organizacion_id = Column(Integer, ForeignKey("organizaciones.id"), nullable=False)
    # Nullable + ON DELETE SET NULL: borrar un usuario (admin.py lo borra de verdad) no
    # tiene que trabarse por sus borradores (misma lección que extractos.creado_por).
    creado_por      = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    creado_at       = Column(DateTime, default=datetime.utcnow)
    actualizado_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    nombre_archivo  = Column(String(255), nullable=False)
    contenido_sha256 = Column(String(64), nullable=True)
    tamano_bytes    = Column(Integer, nullable=True)

    estado          = Column(String(20), nullable=False, default="procesando")
    metodo          = Column(String(20), nullable=True)            # molde | automatico | ia
    banco           = Column(String(120), nullable=True)           # nombre visible
    banco_clave     = Column(String(40), nullable=True)
    molde_id        = Column(Integer, ForeignKey("moldes_extracto_pdf.id", ondelete="SET NULL"), nullable=True)

    periodo_desde   = Column(Date, nullable=True)
    periodo_hasta   = Column(Date, nullable=True)
    saldo_inicial   = Column(Numeric(16, 2), nullable=True)
    saldo_final     = Column(Numeric(16, 2), nullable=True)

    # movimientos (montos string) + orden + cuadre + paginas + escaneado + ia_usada
    # + ia_disponible + aprendizaje (+ "confirmacion" con el resultado al confirmar).
    datos           = Column(JSON, nullable=True)
    alertas         = Column(JSON, nullable=True)                  # [{nivel, codigo, mensaje}]
    error           = Column(Text, nullable=True)

    extracto_id     = Column(Integer, ForeignKey("extractos_bancarios.id", ondelete="SET NULL"), nullable=True)
    confirmado_por  = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    confirmado_at   = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_borrador_extracto_pdf_org_estado", "organizacion_id", "estado"),
        Index("ix_borrador_extracto_pdf_org_sha", "organizacion_id", "contenido_sha256"),
    )
