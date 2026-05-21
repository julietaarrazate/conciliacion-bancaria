from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PlanillaCliente(Base):
    """Planilla persistente por cliente. NO se borra cuando se elimina un extracto."""
    __tablename__ = "planillas_cliente"

    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id"), index=True)
    nombre: Mapped[str] = mapped_column(String(200))
    periodo: Mapped[str | None] = mapped_column(String(20))  # ej: "2026-05"
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    cliente: Mapped["Cliente"] = relationship("Cliente", back_populates="planillas")  # noqa: F821
    movimientos: Mapped[list["MovimientoPlanilla"]] = relationship(
        "MovimientoPlanilla", back_populates="planilla", cascade="all, delete-orphan"
    )


class MovimientoPlanilla(Base):
    """Movimiento dentro de una planilla del cliente. Estados: pendiente, ok, no_esta, faltan_datos, rechazado."""
    __tablename__ = "movimientos_planilla"

    id: Mapped[int] = mapped_column(primary_key=True)
    planilla_id: Mapped[int] = mapped_column(ForeignKey("planillas_cliente.id"), index=True)
    fecha: Mapped[date] = mapped_column(Date)
    descripcion: Mapped[str] = mapped_column(Text)
    monto: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    referencia: Mapped[str | None] = mapped_column(String(100))
    # pendiente | ok | no_esta | faltan_datos | rechazado
    estado: Mapped[str] = mapped_column(String(20), default="pendiente", index=True)
    # cuando se acredita, fecha real en que apareció en extracto
    fecha_acreditacion: Mapped[date | None] = mapped_column(Date)
    # datos faltantes serializados (json string) cuando estado=faltan_datos
    datos_faltantes: Mapped[str | None] = mapped_column(Text)
    observacion: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    planilla: Mapped["PlanillaCliente"] = relationship("PlanillaCliente", back_populates="movimientos")
