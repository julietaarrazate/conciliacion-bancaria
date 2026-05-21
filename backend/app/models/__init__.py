# Importar todos los modelos para que Alembic los detecte con autogenerate
from app.models.user import User
from app.models.bank_account import BankAccount
from app.models.bank_statement import BankStatement
from app.models.bank_transaction import BankTransaction
from app.models.accounting_entry import AccountingEntry
from app.models.reconciliation import Reconciliation, ReconciliationItem
from app.models.cliente import Cliente
from app.models.planilla import PlanillaCliente, MovimientoPlanilla
from app.models.cuenta_contable import CuentaContable
from app.models.asiento_contable import AsientoContable, LineaAsiento
from app.models.cheque import Cheque
from app.models.pago import Pago
from app.models.gasto import Gasto

__all__ = [
    "User", "BankAccount", "BankStatement",
    "BankTransaction", "AccountingEntry",
    "Reconciliation", "ReconciliationItem",
    "Cliente", "PlanillaCliente", "MovimientoPlanilla",
    "CuentaContable", "AsientoContable", "LineaAsiento",
    "Cheque", "Pago", "Gasto",
]
