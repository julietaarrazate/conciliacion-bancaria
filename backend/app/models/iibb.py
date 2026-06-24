"""Modelos del módulo Ingresos Brutos (IIBB) y Convenio Multilateral.

Herramienta de proyección INTERNA (no presenta DDJJ oficiales). El sistema
proyecta el impuesto a los Ingresos Brutos de un período a partir de los ingresos
contables reconocidos, aplicando alícuotas que la organización configura por
jurisdicción.

Dos modos de cálculo:
  - simple: la org opera en UNA jurisdicción → ingreso total × alícuota de esa
    jurisdicción.
  - convenio_multilateral: la org opera en VARIAS jurisdicciones → el ingreso
    total se distribuye según `coeficiente_distribucion` de cada jurisdicción y a
    cada porción se le aplica SU PROPIA alícuota. El coeficiente es un % editable
    por la org (no se recalcula automáticamente — esto NO es una DDJJ oficial).

IMPORTANTE — alícuotas y coeficientes: cada una de las 24 jurisdicciones
argentinas (CABA + 23 provincias) tiene su propio régimen, alícuotas que varían
por actividad y cambian con frecuencia. Por eso NO se siembran alícuotas reales:
se crea una sola jurisdicción ILUSTRATIVA (alícuota 0) marcada como ejemplo y el
admin DEBE completar/verificar todo contra AGIP (CABA), ARBA (Buenos Aires) o el
organismo de cada provincia. Todo es 100% editable vía la API
(`POST/PUT /iibb/jurisdicciones`).

Tablas:
  - jurisdicciones_iibb : jurisdicciones por org con alícuota y coeficiente.
  - iibb_config         : 1 config por org (opt-in: apagado hasta activarse).
  - proyecciones_iibb   : snapshot por período (mismo patrón que ProyeccionIva).
"""

from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, ForeignKey, Numeric, JSON,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class JurisdiccionIIBB(Base):
    __tablename__ = "jurisdicciones_iibb"

    id                       = Column(Integer, primary_key=True, index=True)
    organizacion_id          = Column(Integer, ForeignKey("organizaciones.id"), nullable=False, index=True)
    nombre                   = Column(String(80), nullable=False)            # "CABA", "Buenos Aires"...
    alicuota                 = Column(Numeric(5, 4), nullable=False, default=0)  # ej. 0.0500 = 5%
    coeficiente_distribucion = Column(Numeric(5, 4), nullable=False, default=0)  # 0..1, solo convenio_multilateral
    activa                   = Column(Boolean, nullable=False, default=True)
    orden                    = Column(Integer, nullable=False, default=0)     # orden de visualización
    created_at               = Column(DateTime, default=datetime.utcnow)
    updated_at               = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organizacion = relationship("Organizacion", foreign_keys=[organizacion_id])

    __table_args__ = (
        UniqueConstraint(
            "organizacion_id", "nombre",
            name="uq_jurisdiccion_iibb_org_nombre",
        ),
    )


class IIBBConfig(Base):
    __tablename__ = "iibb_config"

    id                    = Column(Integer, primary_key=True, index=True)
    organizacion_id       = Column(Integer, ForeignKey("organizaciones.id"), nullable=False, unique=True, index=True)
    activo                = Column(Boolean, nullable=False, default=False)        # opt-in
    modo                  = Column(String(24), nullable=False, default="simple")  # "simple" | "convenio_multilateral"
    jurisdiccion_unica_id = Column(Integer, ForeignKey("jurisdicciones_iibb.id"), nullable=True)  # solo modo simple
    created_at            = Column(DateTime, default=datetime.utcnow)
    updated_at            = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organizacion       = relationship("Organizacion", foreign_keys=[organizacion_id])
    jurisdiccion_unica = relationship("JurisdiccionIIBB", foreign_keys=[jurisdiccion_unica_id])


class ProyeccionIIBB(Base):
    __tablename__ = "proyecciones_iibb"

    id                       = Column(Integer, primary_key=True, index=True)
    organizacion_id          = Column(Integer, ForeignKey("organizaciones.id"), nullable=False, index=True)
    periodo                  = Column(String(7), nullable=False)        # "YYYY-MM"
    ingreso_total            = Column(Numeric(12, 2), nullable=False, default=0)
    impuesto_total           = Column(Numeric(12, 2), nullable=False, default=0)
    detalle_por_jurisdiccion = Column(JSON, nullable=True)             # [{jurisdiccion_id, nombre, ingreso_atribuido, alicuota, impuesto}]
    estado                   = Column(String(20), nullable=False, default="proyectado")  # proyectado | presentado
    fecha_presentacion       = Column(DateTime, nullable=True)
    created_at               = Column(DateTime, default=datetime.utcnow)
    updated_at               = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organizacion = relationship("Organizacion", foreign_keys=[organizacion_id])

    __table_args__ = (
        UniqueConstraint("organizacion_id", "periodo", name="uq_proyeccion_iibb_org_periodo"),
    )
