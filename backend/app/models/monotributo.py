"""Modelos del módulo Control Semestral Monotributo.

Herramienta de control/alerta INTERNA (no presenta DDJJ oficiales). El sistema
proyecta los ingresos de los últimos 12 meses de la organización a partir de los
asientos contables y los compara contra las escalas de categorías del Monotributo
que fija ARCA por Resolución General.

IMPORTANTE — montos de las categorías: los topes de ingresos por categoría se
actualizan semestralmente por ARCA y cambian con la inflación. Las categorías que
sembramos al crear la org usan valores de REFERENCIA / placeholder (ver
`seed_monotributo_categorias` en services/monotributo_service.py). El admin DEBE
verificar y actualizar esos límites contra la tabla oficial vigente de
arca.gob.ar antes de tomar decisiones reales — son totalmente editables vía la
API (`PUT /monotributo/categorias/{id}`).

Tablas:
  - categorias_monotributo : escalas A..K por org y tipo de actividad.
  - monotributo_config     : 1 config por org (opt-in: apagado hasta activarse).
  - controles_monotributo  : snapshot por semestre (mismo patrón que ProyeccionIva).
"""

from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Boolean, Date, DateTime, ForeignKey, Numeric, JSON,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class CategoriaMonotributo(Base):
    __tablename__ = "categorias_monotributo"

    id              = Column(Integer, primary_key=True, index=True)
    organizacion_id = Column(Integer, ForeignKey("organizaciones.id"), nullable=False, index=True)
    categoria       = Column(String(2), nullable=False)             # "A".."K"
    tipo_actividad  = Column(String(20), nullable=False)            # "servicios" | "bienes"
    limite_anual    = Column(Numeric(12, 2), nullable=False, default=0)
    orden           = Column(Integer, nullable=False, default=0)    # A=1, B=2... (sort estable)
    created_at      = Column(DateTime, default=datetime.utcnow)
    updated_at      = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organizacion = relationship("Organizacion", foreign_keys=[organizacion_id])

    __table_args__ = (
        UniqueConstraint(
            "organizacion_id", "categoria", "tipo_actividad",
            name="uq_categoria_monotributo_org_cat_tipo",
        ),
    )


class MonotributoConfig(Base):
    __tablename__ = "monotributo_config"

    id               = Column(Integer, primary_key=True, index=True)
    organizacion_id  = Column(Integer, ForeignKey("organizaciones.id"), nullable=False, unique=True, index=True)
    categoria_actual = Column(String(2), nullable=True)
    tipo_actividad   = Column(String(20), nullable=False, default="servicios")  # "servicios" | "bienes"
    activo           = Column(Boolean, nullable=False, default=False)           # opt-in: apagado hasta activarse
    created_at       = Column(DateTime, default=datetime.utcnow)
    updated_at       = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organizacion = relationship("Organizacion", foreign_keys=[organizacion_id])


class ControlMonotributo(Base):
    __tablename__ = "controles_monotributo"

    id                      = Column(Integer, primary_key=True, index=True)
    organizacion_id         = Column(Integer, ForeignKey("organizaciones.id"), nullable=False, index=True)
    periodo                 = Column(String(7), nullable=False)        # "YYYY-S1" | "YYYY-S2"
    fecha_corte             = Column(Date, nullable=False)
    ingresos_12m            = Column(Numeric(12, 2), nullable=False, default=0)
    categoria_actual        = Column(String(2), nullable=True)
    limite_categoria_actual = Column(Numeric(12, 2), nullable=False, default=0)
    porcentaje_uso          = Column(Numeric(6, 2), nullable=False, default=0)   # 87.50 = 87.5%
    categoria_sugerida      = Column(String(2), nullable=True)
    excede                  = Column(Boolean, nullable=False, default=False)      # supera la categoría más alta
    estado                  = Column(String(20), nullable=False, default="pendiente")  # pendiente | revisado
    fecha_revision          = Column(DateTime, nullable=True)
    detalle                 = Column(JSON, nullable=True)              # desglose mensual de ingresos
    created_at              = Column(DateTime, default=datetime.utcnow)
    updated_at              = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organizacion = relationship("Organizacion", foreign_keys=[organizacion_id])

    __table_args__ = (
        UniqueConstraint("organizacion_id", "periodo", name="uq_control_monotributo_org_periodo"),
    )
