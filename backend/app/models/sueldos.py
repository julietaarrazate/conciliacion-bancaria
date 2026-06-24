"""Modelos del módulo Liquidador de Sueldos y F931.

Herramienta de liquidación INTERNA de sueldos + proyección del F931 (la DDJJ
mensual de AFIP/ARCA de aportes y contribuciones de la seguridad social).

IMPORTANTE — esto NO sustituye un sistema de liquidación de sueldos homologado ni
reemplaza el SUSS/AFIP. Es una herramienta de gestión interna del estudio para
calcular recibos y anticipar el F931 antes de presentarlo oficialmente.

Dominio de datos nuevo (empleados) además de la lógica de liquidación:
  - convenios_colectivos   : convenios por org (varios clientes/rubros).
  - categorias_convenio    : escala de categorías por convenio con sueldo básico.
  - empleados              : empleados por org, con soft delete (deleted_at).
  - config_sueldos         : 1 config por org (opt-in) con las alícuotas de
                             aportes (empleado) y contribuciones (empleador).
  - liquidaciones_sueldo   : snapshot por período (mismo patrón ProyeccionIva /
                             ProyeccionIIBB: inmutable una vez "presentado").
  - detalles_liquidacion_sueldo : una fila por empleado liquidado en el período.

Las alícuotas de aportes/contribuciones se siembran como DEFAULT EDITABLE con una
nota clara de "valores de referencia — verificar vigencia con tu contador/AFIP".
La ART queda en 0 obligatoriamente editable (varía 100% por póliza contratada).
"""

from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Date, ForeignKey, Numeric, JSON,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class ConvenioColectivo(Base):
    __tablename__ = "convenios_colectivos"

    id              = Column(Integer, primary_key=True, index=True)
    organizacion_id = Column(Integer, ForeignKey("organizaciones.id"), nullable=False, index=True)
    nombre          = Column(String(120), nullable=False)
    descripcion     = Column(String(255), nullable=True)
    activo          = Column(Boolean, nullable=False, default=True)
    created_at      = Column(DateTime, default=datetime.utcnow)
    updated_at      = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organizacion = relationship("Organizacion", foreign_keys=[organizacion_id])
    categorias   = relationship(
        "CategoriaConvenio", back_populates="convenio", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("organizacion_id", "nombre", name="uq_convenio_org_nombre"),
    )


class CategoriaConvenio(Base):
    __tablename__ = "categorias_convenio"

    id            = Column(Integer, primary_key=True, index=True)
    convenio_id   = Column(Integer, ForeignKey("convenios_colectivos.id"), nullable=False, index=True)
    nombre        = Column(String(120), nullable=False)
    sueldo_basico = Column(Numeric(12, 2), nullable=False, default=0)
    orden         = Column(Integer, nullable=False, default=0)
    created_at    = Column(DateTime, default=datetime.utcnow)
    updated_at    = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    convenio = relationship("ConvenioColectivo", back_populates="categorias")

    __table_args__ = (
        UniqueConstraint("convenio_id", "nombre", name="uq_categoria_convenio_nombre"),
    )


class Empleado(Base):
    __tablename__ = "empleados"

    id              = Column(Integer, primary_key=True, index=True)
    organizacion_id = Column(Integer, ForeignKey("organizaciones.id"), nullable=False, index=True)
    nombre          = Column(String(160), nullable=False)
    cuil            = Column(String(13), nullable=True)   # 11 dígitos (validado en el router)
    convenio_id     = Column(Integer, ForeignKey("convenios_colectivos.id"), nullable=True)
    categoria_id    = Column(Integer, ForeignKey("categorias_convenio.id"), nullable=True)
    fecha_ingreso   = Column(Date, nullable=True)
    sueldo_basico   = Column(Numeric(12, 2), nullable=True)  # override del básico de la categoría
    cargas_familia  = Column(Integer, nullable=False, default=0)
    activo          = Column(Boolean, nullable=False, default=True)
    deleted_at      = Column(DateTime, nullable=True, index=True)  # soft delete: NULL = activo
    created_at      = Column(DateTime, default=datetime.utcnow)
    updated_at      = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organizacion = relationship("Organizacion", foreign_keys=[organizacion_id])
    convenio     = relationship("ConvenioColectivo", foreign_keys=[convenio_id])
    categoria    = relationship("CategoriaConvenio", foreign_keys=[categoria_id])


class ConfigSueldos(Base):
    __tablename__ = "config_sueldos"

    id              = Column(Integer, primary_key=True, index=True)
    organizacion_id = Column(Integer, ForeignKey("organizaciones.id"), nullable=False, unique=True, index=True)
    activo          = Column(Boolean, nullable=False, default=False)  # opt-in

    # ── Aportes del EMPLEADO (se descuentan del bruto) ──
    aporte_jubilacion   = Column(Numeric(5, 4), nullable=False, default=0)  # ej. 0.1100 = 11%
    aporte_inssjp       = Column(Numeric(5, 4), nullable=False, default=0)  # PAMI, ej. 0.0300
    aporte_obra_social  = Column(Numeric(5, 4), nullable=False, default=0)  # ej. 0.0300

    # ── Contribuciones del EMPLEADOR (las paga la empresa) ──
    contrib_jubilacion  = Column(Numeric(5, 4), nullable=False, default=0)
    contrib_inssjp      = Column(Numeric(5, 4), nullable=False, default=0)  # ley 19032
    contrib_obra_social = Column(Numeric(5, 4), nullable=False, default=0)
    contrib_asig_fam    = Column(Numeric(5, 4), nullable=False, default=0)  # asignaciones familiares
    contrib_fondo_desempleo = Column(Numeric(5, 4), nullable=False, default=0)
    alicuota_art        = Column(Numeric(5, 4), nullable=False, default=0)  # ART: SIEMPRE 0 por default (varía por póliza)

    # ── Retención de Ganancias 4ta categoría (opt-in INDEPENDIENTE del módulo) ──
    # Si ganancias_activo=False, calcular_ganancias_4ta() devuelve 0 sin calcular
    # — no rompe orgs que no lo activaron. minimo_no_imponible y deduccion_especial
    # son montos MENSUALES (se anualizan ×12 internamente para la proyección).
    ganancias_activo     = Column(Boolean, nullable=False, default=False)
    minimo_no_imponible  = Column(Numeric(12, 2), nullable=False, default=0)
    deduccion_especial   = Column(Numeric(12, 2), nullable=False, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organizacion = relationship("Organizacion", foreign_keys=[organizacion_id])


class EscalaGanancias(Base):
    """Escala de tramos del impuesto a las Ganancias 4ta categoría, por org.

    Fórmula AFIP: retención = monto_fijo + alicuota × (excedente sobre tramo_desde).
    tramo_hasta=NULL representa el último tramo (abierto, sin techo).

    NO se siembra con valores reales — la escala cambia varias veces por año
    según resoluciones de AFIP/ARCA. Queda vacía hasta que el admin la cargue
    manualmente con los valores vigentes (ver disclaimer en el router/UI)."""
    __tablename__ = "escala_ganancias"

    id              = Column(Integer, primary_key=True, index=True)
    organizacion_id = Column(Integer, ForeignKey("organizaciones.id"), nullable=False, index=True)
    tramo_desde     = Column(Numeric(14, 2), nullable=False, default=0)
    tramo_hasta     = Column(Numeric(14, 2), nullable=True)   # NULL = último tramo (sin techo)
    alicuota        = Column(Numeric(5, 4), nullable=False, default=0)
    monto_fijo      = Column(Numeric(12, 2), nullable=False, default=0)
    created_at      = Column(DateTime, default=datetime.utcnow)
    updated_at      = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organizacion = relationship("Organizacion", foreign_keys=[organizacion_id])


class LiquidacionSueldoPeriodo(Base):
    __tablename__ = "liquidaciones_sueldo"

    id              = Column(Integer, primary_key=True, index=True)
    organizacion_id = Column(Integer, ForeignKey("organizaciones.id"), nullable=False, index=True)
    periodo         = Column(String(7), nullable=False)  # "YYYY-MM"
    estado          = Column(String(20), nullable=False, default="borrador")  # borrador | aprobado | presentado
    total_bruto           = Column(Numeric(12, 2), nullable=False, default=0)
    total_aportes         = Column(Numeric(12, 2), nullable=False, default=0)
    total_contribuciones  = Column(Numeric(12, 2), nullable=False, default=0)
    total_neto            = Column(Numeric(12, 2), nullable=False, default=0)
    total_retencion_ganancias = Column(Numeric(12, 2), nullable=False, default=0, server_default="0")
    fecha_aprobacion      = Column(DateTime, nullable=True)
    fecha_presentacion    = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organizacion = relationship("Organizacion", foreign_keys=[organizacion_id])
    detalles     = relationship(
        "DetalleLiquidacionEmpleado",
        back_populates="liquidacion",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("organizacion_id", "periodo", name="uq_liquidacion_sueldo_org_periodo"),
    )


class DetalleLiquidacionEmpleado(Base):
    __tablename__ = "detalles_liquidacion_sueldo"

    id                   = Column(Integer, primary_key=True, index=True)
    liquidacion_periodo_id = Column(Integer, ForeignKey("liquidaciones_sueldo.id"), nullable=False, index=True)
    empleado_id          = Column(Integer, ForeignKey("empleados.id"), nullable=True)
    sueldo_bruto         = Column(Numeric(12, 2), nullable=False, default=0)
    sac_proporcional     = Column(Numeric(12, 2), nullable=False, default=0)
    total_aportes        = Column(Numeric(12, 2), nullable=False, default=0)
    total_contribuciones = Column(Numeric(12, 2), nullable=False, default=0)
    sueldo_neto          = Column(Numeric(12, 2), nullable=False, default=0)
    # Retención de Ganancias 4ta categoría (0 si ganancias_activo=False en ConfigSueldos).
    retencion_ganancias  = Column(Numeric(12, 2), nullable=False, default=0)
    detalle_json         = Column(JSON, nullable=True)  # desglose de cada concepto
    created_at           = Column(DateTime, default=datetime.utcnow)

    liquidacion = relationship("LiquidacionSueldoPeriodo", back_populates="detalles")
    empleado    = relationship("Empleado", foreign_keys=[empleado_id])
