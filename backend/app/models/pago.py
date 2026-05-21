from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Pago(Base):
    """Pago a cliente. Medio: banco | efectivo."""
    __tablename__ = "pagos"

    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id"), index=True)
    fecha: Mapped[date] = mapped_column(Date, index=True)
    monto: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    # banco | efectivo
    medio: Mapped[str] = mapped_column(String(20))
    referencia: Mapped[str | None] = mapped_column(String(100))
    observacion: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    cliente: Mapped["Cliente"] = relationship("Cliente")  # noqa: F821
