from datetime import date
from decimal import Decimal
from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class BankTransaction(Base):
    __tablename__ = "bank_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    statement_id: Mapped[int] = mapped_column(ForeignKey("bank_statements.id"), index=True)
    transaction_date: Mapped[date] = mapped_column(Date, index=True)
    description: Mapped[str] = mapped_column(Text)
    # positivo = crédito, negativo = débito
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    reference: Mapped[str | None] = mapped_column(String(100))
    is_reconciled: Mapped[bool] = mapped_column(Boolean, default=False)

    statement: Mapped["BankStatement"] = relationship("BankStatement", back_populates="transactions")  # noqa: F821
