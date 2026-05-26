"""
Tabla de patrones aprendidos del matching.
Cada vez que se corrige manualmente un 'sin datos' o 'no coincide' a 'ok',
se extrae el patron que lo identifico y se guarda aqui.

Con suficientes patrones, el motor de match los usa como referencia adicional
antes de declarar que no hay suficientes datos.
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Numeric
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class PatronAprendido(Base):
    __tablename__ = "patrones_aprendidos"

    id = Column(Integer, primary_key=True, index=True)
    organizacion_id = Column(Integer, ForeignKey("organizaciones.id"), nullable=False, index=True)

    # Identidad del pagador (lo que la planilla tenia)
    cliente_nombre = Column(String, nullable=False, index=True)  # a quien pertenece
    titular_fragmento = Column(String, nullable=True)   # palabras clave del titular
    numeros_clave = Column(String, nullable=True)       # CUIT/CBU/nros separados por coma

    # Monto tipico (ayuda a priorizar patrones con ese monto)
    monto_tipico = Column(Numeric(12, 2), nullable=True)

    # Patron encontrado en el extracto
    titular_extracto_fragmento = Column(String, nullable=True)  # palabras del titular del banco

    # Estadisticas de uso
    veces_visto = Column(Integer, default=1)      # cuantas veces coincidio
    veces_correcto = Column(Integer, default=1)   # cuantas veces fue confirmado correcto
    activo = Column(Boolean, default=True)

    creado_at = Column(DateTime, default=datetime.utcnow)
    ultimo_uso = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organizacion = relationship("Organizacion", foreign_keys=[organizacion_id])
