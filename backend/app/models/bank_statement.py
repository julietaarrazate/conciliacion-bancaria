from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class BankStatement(Base):
    __tablename__ = "bank_statements"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("bank_accounts.id"), index=True)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    opening_balance: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    closing_balance: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    # draft → processing → closed
    status: Mapped[str] = mapped_column(String(20), default="draft")
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    account: Mapped["BankAccount"] = relationship("BankAccount", back_populates="statements")  # noqa: F821
    transactions: Mapped[list["BankTransaction"]] = relationship("BankTransaction", back_populates="statement")  # noqa: F821
