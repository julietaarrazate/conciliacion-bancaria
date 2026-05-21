from datetime import datetime
from pydantic import BaseModel


class BankAccountCreate(BaseModel):
    name: str
    account_number: str
    bank_name: str
    currency: str = "ARS"


class BankAccountUpdate(BaseModel):
    name: str | None = None
    bank_name: str | None = None


class BankAccountResponse(BaseModel):
    id: int
    name: str
    account_number: str
    bank_name: str
    currency: str
    user_id: int
    created_at: datetime

    model_config = {"from_attributes": True}
