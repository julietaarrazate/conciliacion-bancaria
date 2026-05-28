from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Date, Text, Boolean, Numeric
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


# Estados base
# "pendiente", "ok", "no está", "duplicado", "faltan datos", "acreditado DD/MM"
# Estados ricos (orgs con estados_habilitados extendidos)
ESTADOS_RICOS = ["PAGO_PARCIAL", "CONCILIADO_CON_DIFERENCIA", "VENCIDO", "EN_REVISION"]


class Planilla(Base):
    __tablename__ = "planillas"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    extracto_id = Column(Integer, ForeignKey("extractos_bancarios.id"), nullable=True)
    usuario_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    organizacion_id = Column(Integer, ForeignKey("organizaciones.id"), nullable=True, default=1)

    nombre_archivo = Column(String, nullable=False)
    fecha_carga = Column(DateTime, default=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True, index=True)  # soft delete: NULL = activo
    porcentaje_comision = Column(Numeric(5, 4), nullable=True)  # % comisión para liquidación

    # Relationships
    cliente = relationship("Cliente", back_populates="planillas")
    extracto = relationship("ExtractoBancario", back_populates="planillas")
    usuario = relationship("User", back_populates="planillas")
    rows = relationship("PlanillaRow", back_populates="planilla", cascade="all, delete-orphan")
    organizacion = relationship("Organizacion", foreign_keys=[organizacion_id])


class PlanillaRow(Base):
    __tablename__ = "planilla_rows"

    id = Column(Integer, primary_key=True, index=True)
    planilla_id = Column(Integer, ForeignKey("planillas.id"), nullable=False)
    organizacion_id = Column(Integer, ForeignKey("organizaciones.id"), nullable=True, default=1)

    # Datos de la planilla
    monto = Column(Numeric(12, 2), nullable=False)
    cuit = Column(String, nullable=True)
    titular = Column(String, nullable=True)
    referencia = Column(String, nullable=True)  # para match_rule "referencia"

    # Resultado de la conciliación
    # Estados base: "pendiente", "ok", "no está", "duplicado", "faltan datos", "acreditado DD/MM"
    # Estados ricos: "PAGO_PARCIAL", "CONCILIADO_CON_DIFERENCIA", "VENCIDO", "EN_REVISION"
    status = Column(String, nullable=False)
    fecha_acred = Column(Date, nullable=True)
    monto_acreditado = Column(Numeric(12, 2), nullable=True)
    comentario_revision = Column(Text, nullable=True)
    orden_movimiento_acreditado = Column(Integer, ForeignKey("movimientos_banco.id"), nullable=True)

    # Relationships
    planilla = relationship("Planilla", back_populates="rows")
    movimiento_acreditado = relationship("MovimientoBanco", back_populates="planilla_rows")
    organizacion = relationship("Organizacion", foreign_keys=[organizacion_id])
