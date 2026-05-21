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

    model_config = {"from_attributes": True}


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
    match_type: str
    matched_at: datetime

    model_config = {"from_attributes": True}


class ManualMatchRequest(BaseModel):
    bank_transaction_id: int
    accounting_entry_id: int


class AutoMatchResult(BaseModel):
    matched: int
    unmatched: int
    difference: Decimal
