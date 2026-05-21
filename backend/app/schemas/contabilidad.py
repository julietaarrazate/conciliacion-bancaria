from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel


class CuentaContableResponse(BaseModel):
    id: int
    codigo: str
    nombre: str
    tipo: str
    naturaleza: str
    nivel: int = 1
    parent_id: int | None = None
    imputable: bool = False
    cliente_id: int | None = None

    model_config = {"from_attributes": True}


class CuentaTreeNode(BaseModel):
    id: int
    codigo: str
    nombre: str
    tipo: str
    naturaleza: str
    nivel: int
    imputable: bool
    cliente_id: int | None = None
    saldo: Decimal = Decimal("0")
    hijas: list["CuentaTreeNode"] = []


class LineaAsientoResponse(BaseModel):
    id: int
    cuenta_id: int
    cuenta_codigo: str | None = None
    cuenta_nombre: str | None = None
    debe: Decimal
    haber: Decimal

    model_config = {"from_attributes": True}


class AsientoResponse(BaseModel):
    id: int
    numero: int = 0
    fecha: date
    descripcion: str
    origen: str
    origen_id: int | None
    created_at: datetime
    lineas: list[LineaAsientoResponse] = []

    model_config = {"from_attributes": True}


class MayorRow(BaseModel):
    fecha: date
    asiento_numero: int
    descripcion: str
    debe: Decimal
    haber: Decimal
    saldo: Decimal


class SumasSaldosRow(BaseModel):
    cuenta_id: int
    codigo: str
    nombre: str
    nivel: int
    suma_debe: Decimal
    suma_haber: Decimal
    saldo_deudor: Decimal
    saldo_acreedor: Decimal


class BalanceRow(BaseModel):
    cuenta_id: int
    codigo: str
    nombre: str
    tipo: str
    nivel: int
    parent_id: int | None
    saldo: Decimal
