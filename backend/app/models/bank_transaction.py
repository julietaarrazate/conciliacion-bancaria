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

    # Vínculo opcional con cliente y movimiento de planilla (no cascade desde extracto)
    cliente_id: Mapped[int | None] = mapped_column(ForeignKey("clientes.id", ondelete="SET NULL"), index=True)
    planilla_movimiento_id: Mapped[int | None] = mapped_column(
        ForeignKey("movimientos_planilla.id", ondelete="SET NULL"), index=True
    )
    # pendiente | acreditado | no_esta | faltan_datos | duplicado
    estado: Mapped[str] = mapped_column(String(20), default="pendiente", index=True)
    # info de duplicado/acreditacion previa: fecha original (cuando estado=duplicado y en realidad ya fue acreditado)
    fecha_acreditacion_original: Mapped[date | None] = mapped_column(Date)
    # Es una UM agregada manualmente (no provino del archivo de importación)
    es_manual: Mapped[bool] = mapped_column(Boolean, default=False)

    statement: Mapped["BankStatement"] = relationship("BankStatement", back_populates="transactions")  # noqa: F821
    cliente: Mapped["Cliente"] = relationship("Cliente")  # noqa: F821
    planilla_movimiento: Mapped["MovimientoPlanilla"] = relationship("MovimientoPlanilla")  # noqa: F821
