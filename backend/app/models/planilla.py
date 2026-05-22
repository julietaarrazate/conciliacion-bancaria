from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Date, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


# Estados base (Caneland)
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
    monto = Column(Float, nullable=False)
    cuit = Column(String, nullable=True)
    titular = Column(String, nullable=True)
    referencia = Column(String, nullable=True)  # para match_rule "referencia"

    # Resultado de la conciliación
    # Estados base: "pendiente", "ok", "no está", "duplicado", "faltan datos", "acreditado DD/MM"
    # Estados ricos: "PAGO_PARCIAL", "CONCILIADO_CON_DIFERENCIA", "VENCIDO", "EN_REVISION"
    status = Column(String, nullable=False)
    monto_acreditado = Column(Float, nullable=True)  # para PAGO_PARCIAL / CONCILIADO_CON_DIFERENCIA
    comentario_revision = Column(Text, nullable=True)  # para EN_REVISION
    orden_movimiento_acreditado = Column(Integer, ForeignKey("movimientos_banco.id"), nullable=True)

    # Relationships
    planilla = relationship("Planilla", back_populates="rows")
    movimiento_acreditado = relationship("MovimientoBanco", back_populates="planilla_rows")
    organizacion = relationship("Organizacion", foreign_keys=[organizacion_id])
