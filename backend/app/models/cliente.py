from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import DateTime, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Cliente(Base):
    __tablename__ = "clientes"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(200), index=True)
    cuit: Mapped[str | None] = mapped_column(String(20), index=True)
    titular: Mapped[str | None] = mapped_column(String(200))
    cuenta: Mapped[str | None] = mapped_column(String(100))
    # comisión asignada (porcentual)
    comision: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"))
    # banco, efectivo, cheque, transferencia
    forma_pago: Mapped[str | None] = mapped_column(String(30))
    activo: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    planillas: Mapped[list["PlanillaCliente"]] = relationship(  # noqa: F821
        "PlanillaCliente", back_populates="cliente"
    )
