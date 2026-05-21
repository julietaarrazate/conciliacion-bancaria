from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel


class BankStatementResponse(BaseModel):
    id: int
    account_id: int
    period_start: date
    period_end: date
    opening_balance: Decimal
    closing_balance: Decimal
    status: str
    imported_at: datetime

    model_config = {"from_attributes": True}


class BankTransactionResponse(BaseModel):
    id: int
    statement_id: int
    transaction_date: date
    description: str
    amount: Decimal
    reference: str | None
    is_reconciled: bool
    cliente_id: int | None = None
    planilla_movimiento_id: int | None = None
    estado: str = "pendiente"
    fecha_acreditacion_original: date | None = None
    es_manual: bool = False

    model_config = {"from_attributes": True}


class BankTransactionUpdate(BaseModel):
    """Edición manual de una fila del extracto."""
    transaction_date: date | None = None
    description: str | None = None
    amount: Decimal | None = None
    reference: str | None = None
    cliente_id: int | None = None
    estado: str | None = None
    fecha_acreditacion_original: date | None = None


class BankTransactionCreateManual(BaseModel):
    """Agregar UM manual a un extracto existente."""
    transaction_date: date
    description: str
    amount: Decimal
    reference: str | None = None
    cliente_id: int | None = None


class AccountingEntryResponse(BaseModel):
    id: int
    account_id: int
    entry_date: date
    description: str
    amount: Decimal
    reference: str | None
    is_reconciled: bool

    model_config = {"from_attributes": True}


class ReconciliationCreate(BaseModel):
    statement_id: int


class ReconciliationResponse(BaseModel):
    id: int
    statement_id: int
    status: str
    difference: Decimal
    created_at: datetime
    closed_at: datetime | None

    model_config = {"from_attributes": True}


class ReconciliationItemResponse(BaseModel):
    id: int
    reconciliation_id: int
    bank_transaction_id: int | None
    accounting_entry_id: int | None
    planilla_movimiento_id: int | None = None
    match_type: str
    estado: str = "acreditado"
    observacion: str | None = None
    matched_at: datetime

    model_config = {"from_attributes": True}


class ManualMatchRequest(BaseModel):
    bank_transaction_id: int
    accounting_entry_id: int | None = None
    # Planilla destino obligatoria cuando se acredita manualmente sin asiento
    planilla_movimiento_id: int | None = None
    estado: str = "acreditado"
    observacion: str | None = None


class ReconciliationItemUpdate(BaseModel):
    estado: str | None = None
    planilla_movimiento_id: int | None = None
    accounting_entry_id: int | None = None
    observacion: str | None = None


class AutoMatchResult(BaseModel):
    matched: int
    unmatched: int
    difference: Decimal
    no_esta: int = 0
    faltan_datos: int = 0
