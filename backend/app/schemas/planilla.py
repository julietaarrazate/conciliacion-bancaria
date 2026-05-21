from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel


class PlanillaCreate(BaseModel):
    cliente_id: int
    nombre: str
    periodo: str | None = None


class PlanillaResponse(BaseModel):
    id: int
    cliente_id: int
    nombre: str
    periodo: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MovimientoPlanillaCreate(BaseModel):
    planilla_id: int
    fecha: date
    descripcion: str
    monto: Decimal
    referencia: str | None = None
    estado: str = "pendiente"


class MovimientoPlanillaUpdate(BaseModel):
    fecha: date | None = None
    descripcion: str | None = None
    monto: Decimal | None = None
    referencia: str | None = None
    estado: str | None = None
    fecha_acreditacion: date | None = None
    observacion: str | None = None


class MovimientoPlanillaResponse(BaseModel):
    id: int
    planilla_id: int
    fecha: date
    descripcion: str
    monto: Decimal
    referencia: str | None
    estado: str
    fecha_acreditacion: date | None
    datos_faltantes: str | None
    observacion: str | None
    updated_at: datetime

    model_config = {"from_attributes": True}
