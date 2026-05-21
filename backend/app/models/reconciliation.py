from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Reconciliation(Base):
    __tablename__ = "reconciliations"

    id: Mapped[int] = mapped_column(primary_key=True)
    statement_id: Mapped[int] = mapped_column(ForeignKey("bank_statements.id"), unique=True)
    # open → in_progress → closed
    status: Mapped[str] = mapped_column(String(20), default="open")
    # saldo banco - saldo contable (0 = conciliado perfecto)
    difference: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=Decimal("0"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    statement: Mapped["BankStatement"] = relationship("BankStatement")  # noqa: F821
    items: Mapped[list["ReconciliationItem"]] = relationship(
        "ReconciliationItem", back_populates="reconciliation", cascade="all, delete-orphan"
    )


class ReconciliationItem(Base):
    __tablename__ = "reconciliation_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    reconciliation_id: Mapped[int] = mapped_column(ForeignKey("reconciliations.id"), index=True)
    bank_transaction_id: Mapped[int | None] = mapped_column(ForeignKey("bank_transactions.id"))
    accounting_entry_id: Mapped[int | None] = mapped_column(ForeignKey("accounting_entries.id"))
    # NUEVO: vínculo opcional con el movimiento de planilla destino (resuelve "acreditación manual a planilla aparte")
    planilla_movimiento_id: Mapped[int | None] = mapped_column(
        ForeignKey("movimientos_planilla.id", ondelete="SET NULL")
    )
    # auto = algoritmo, manual = usuario
    match_type: Mapped[str] = mapped_column(String(20), default="manual")
    # acreditado | no_esta | faltan_datos | duplicado | pendiente
    estado: Mapped[str] = mapped_column(String(20), default="acreditado", index=True)
    observacion: Mapped[str | None] = mapped_column(Text)
    matched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    matched_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    reconciliation: Mapped["Reconciliation"] = relationship("Reconciliation", back_populates="items")
    bank_transaction: Mapped["BankTransaction"] = relationship("BankTransaction")  # noqa: F821
    accounting_entry: Mapped["AccountingEntry"] = relationship("AccountingEntry")  # noqa: F821
