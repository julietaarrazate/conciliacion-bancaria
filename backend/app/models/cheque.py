from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Cheque(Base):
    """Cheque recibido de cliente. Estado: cargado, acreditado, rechazado."""
    __tablename__ = "cheques"

    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id"), index=True)
    numero: Mapped[str] = mapped_column(String(50), index=True)
    banco_emisor: Mapped[str | None] = mapped_column(String(100))
    fecha_emision: Mapped[date] = mapped_column(Date)
    fecha_cobro: Mapped[date] = mapped_column(Date)
    monto: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    comision: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=Decimal("0"))
    # cargado | acreditado | rechazado
    estado: Mapped[str] = mapped_column(String(20), default="cargado", index=True)
    fecha_acreditacion: Mapped[date | None] = mapped_column(Date)
    motivo_rechazo: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    cliente: Mapped["Cliente"] = relationship("Cliente")  # noqa: F821
