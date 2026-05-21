from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel


class CuentaContableResponse(BaseModel):
    id: int
    codigo: str
    nombre: str
    tipo: str
    naturaleza: str

    model_config = {"from_attributes": True}


class LineaAsientoResponse(BaseModel):
    id: int
    cuenta_id: int
    cuenta_nombre: str | None = None
    debe: Decimal
    haber: Decimal

    model_config = {"from_attributes": True}


class AsientoResponse(BaseModel):
    id: int
    fecha: date
    descripcion: str
    origen: str
    origen_id: int | None
    created_at: datetime
    lineas: list[LineaAsientoResponse] = []

    model_config = {"from_attributes": True}


class MayorRow(BaseModel):
    fecha: date
    descripcion: str
    debe: Decimal
    haber: Decimal
    saldo: Decimal


class SumasSaldosRow(BaseModel):
    cuenta_id: int
    codigo: str
    nombre: str
    suma_debe: Decimal
    suma_haber: Decimal
    saldo_deudor: Decimal
    saldo_acreedor: Decimal


class BalanceRow(BaseModel):
    cuenta_id: int
    codigo: str
    nombre: str
    tipo: str
    saldo: Decimal
