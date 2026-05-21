from datetime import date
from decimal import Decimal
from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AccountingEntry(Base):
    __tablename__ = "accounting_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("bank_accounts.id"), index=True)
    entry_date: Mapped[date] = mapped_column(Date, index=True)
    description: Mapped[str] = mapped_column(Text)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    reference: Mapped[str | None] = mapped_column(String(100))
    is_reconciled: Mapped[bool] = mapped_column(Boolean, default=False)

    account: Mapped["BankAccount"] = relationship("BankAccount")  # noqa: F821
