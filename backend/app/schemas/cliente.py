from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel


class ClienteBase(BaseModel):
    nombre: str
    cuit: str | None = None
    titular: str | None = None
    cuenta: str | None = None
    comision: Decimal = Decimal("0")
    forma_pago: str | None = None
    activo: bool = True


class ClienteCreate(ClienteBase):
    pass


class ClienteUpdate(BaseModel):
    nombre: str | None = None
    cuit: str | None = None
    titular: str | None = None
    cuenta: str | None = None
    comision: Decimal | None = None
    forma_pago: str | None = None
    activo: bool | None = None


class ClienteResponse(ClienteBase):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}
