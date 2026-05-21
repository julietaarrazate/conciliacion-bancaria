from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Gasto(Base):
    """Gasto operativo. Medio de pago: banco | efectivo."""
    __tablename__ = "gastos"

    id: Mapped[int] = mapped_column(primary_key=True)
    fecha: Mapped[date] = mapped_column(Date, index=True)
    concepto: Mapped[str] = mapped_column(String(200))
    monto: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    # banco | efectivo
    medio: Mapped[str] = mapped_column(String(20))
    cuenta_gasto_id: Mapped[int | None] = mapped_column(ForeignKey("cuentas_contables.id"))
    observacion: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
