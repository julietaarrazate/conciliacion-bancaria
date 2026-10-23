"""Uso diario de IA por organización (cupo del asistente, OCR y transcripción).

Una fila por (organización, día, tipo). El contador vive en la base para que el
cupo sea por organización y sobreviva a los reinicios del servidor.
"""
from sqlalchemy import Column, Date, ForeignKey, Integer, String, UniqueConstraint

from app.database import Base


class UsoIaDiario(Base):
    __tablename__ = "uso_ia_diario"

    id              = Column(Integer, primary_key=True, index=True)
    organizacion_id = Column(Integer, ForeignKey("organizaciones.id"), nullable=False, index=True)
    fecha           = Column(Date, nullable=False)
    tipo            = Column(String(20), nullable=False)   # "chat" | "ocr" | "audio"
    cantidad        = Column(Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("organizacion_id", "fecha", "tipo", name="uq_uso_ia_org_fecha_tipo"),
    )
