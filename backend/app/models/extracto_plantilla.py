"""Plantillas de lectura de extractos en Excel/CSV (por organización).

Cuando un extracto se importa con un mapeo de columnas confirmado por la persona
(porque el sistema no lo reconoció solo, o lo reconoció con dudas), ese mapeo se
guarda acá. La próxima vez que llega un archivo con el mismo encabezado (y el
mismo banco detectado) se aplica solo: un clic, como hoy.

La clave es `firma`: huella del renglón de encabezado normalizado + banco
detectado (ver `extracto_mapper.firma_encabezado`), igual que los moldes de PDF.
Tabla nueva, sin columnas nuevas en tablas existentes (migración 038).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint

from app.database import Base


class PlantillaExtractoExcel(Base):
    """Mapeo de columnas aprendido para un formato de extracto en Excel/CSV."""

    __tablename__ = "plantillas_extracto_excel"

    id              = Column(Integer, primary_key=True)
    organizacion_id = Column(Integer, ForeignKey("organizaciones.id"), nullable=False)
    banco_clave     = Column(String(40), nullable=True)
    firma           = Column(String(64), nullable=False)
    # Encabezados tal como venían (para mostrarle a la persona de qué formato se trata).
    encabezados     = Column(JSON, nullable=True)
    # Mapeo confirmado: {columnas: {rol: índice}, signo, formato_fecha, decimal, ...}
    mapeo           = Column(JSON, nullable=False)
    usos            = Column(Integer, nullable=False, default=0)
    creado_at       = Column(DateTime, default=datetime.utcnow)
    actualizado_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    ultimo_uso_at   = Column(DateTime, nullable=True)
    creado_por      = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        # El índice del UNIQUE (organizacion_id primero) sirve también para filtrar por org.
        UniqueConstraint("organizacion_id", "firma", name="uq_plantilla_extracto_excel_org_firma"),
    )
