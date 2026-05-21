# Importar todos los modelos para que Alembic los detecte con autogenerate
from app.models.user import User
from app.models.bank_account import BankAccount
from app.models.bank_statement import BankStatement
from app.models.bank_transaction import BankTransaction
from app.models.accounting_entry import AccountingEntry
from app.models.reconciliation import Reconciliation, ReconciliationItem

__all__ = [
    "User", "BankAccount", "BankStatement",
    "BankTransaction", "AccountingEntry",
    "Reconciliation", "ReconciliationItem",
]
