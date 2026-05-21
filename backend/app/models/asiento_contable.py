from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AsientoContable(Base):
    """Asiento contable (cabecera). Cada asiento tiene N líneas Debe/Haber que deben balancear."""
    __tablename__ = "asientos_contables"

    id: Mapped[int] = mapped_column(primary_key=True)
    fecha: Mapped[date] = mapped_column(Date, index=True)
    descripcion: Mapped[str] = mapped_column(Text)
    # módulo origen: acreditacion | cheque | pago | gasto | manual
    origen: Mapped[str] = mapped_column(String(30), index=True)
    # referencia al objeto del módulo (id de cheque, pago, etc.)
    origen_id: Mapped[int | None] = mapped_column(index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    lineas: Mapped[list["LineaAsiento"]] = relationship(
        "LineaAsiento", back_populates="asiento", cascade="all, delete-orphan"
    )


class LineaAsiento(Base):
    __tablename__ = "lineas_asiento"

    id: Mapped[int] = mapped_column(primary_key=True)
    asiento_id: Mapped[int] = mapped_column(ForeignKey("asientos_contables.id"), index=True)
    cuenta_id: Mapped[int] = mapped_column(ForeignKey("cuentas_contables.id"), index=True)
    debe: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=Decimal("0"))
    haber: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=Decimal("0"))

    asiento: Mapped["AsientoContable"] = relationship("AsientoContable", back_populates="lineas")
    cuenta: Mapped["CuentaContable"] = relationship("CuentaContable")  # noqa: F821
