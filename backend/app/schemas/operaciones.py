from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel


# === Cheques ===
class ChequeCreate(BaseModel):
    cliente_id: int
    numero: str
    banco_emisor: str | None = None
    fecha_emision: date
    fecha_cobro: date
    monto: Decimal
    comision: Decimal = Decimal("0")


class ChequeAcreditar(BaseModel):
    fecha_acreditacion: date


class ChequeRechazar(BaseModel):
    motivo: str


class ChequeResponse(BaseModel):
    id: int
    cliente_id: int
    numero: str
    banco_emisor: str | None
    fecha_emision: date
    fecha_cobro: date
    monto: Decimal
    comision: Decimal
    estado: str
    fecha_acreditacion: date | None
    motivo_rechazo: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# === Pagos ===
class PagoCreate(BaseModel):
    cliente_id: int
    fecha: date
    monto: Decimal
    medio: str  # banco | efectivo
    referencia: str | None = None
    observacion: str | None = None


class PagoResponse(BaseModel):
    id: int
    cliente_id: int
    fecha: date
    monto: Decimal
    medio: str
    referencia: str | None
    observacion: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# === Gastos ===
class GastoCreate(BaseModel):
    fecha: date
    concepto: str
    monto: Decimal
    medio: str  # banco | efectivo
    cuenta_gasto_id: int | None = None
    observacion: str | None = None


class GastoResponse(BaseModel):
    id: int
    fecha: date
    concepto: str
    monto: Decimal
    medio: str
    cuenta_gasto_id: int | None
    observacion: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
