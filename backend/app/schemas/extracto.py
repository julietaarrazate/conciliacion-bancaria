from pydantic import BaseModel
from datetime import datetime, date
from typing import List, Optional

class MovimientoBancoResponse(BaseModel):
    id: int
    orden: Optional[int] = None
    fecha: Optional[date] = None
    titular: Optional[str] = None
    monto: float
    cliente_acreditado: Optional[str] = None
    fecha_acred: Optional[date] = None

    class Config:
        from_attributes = True

class ExtractoBancarioResponse(BaseModel):
    id: int
    nombre_archivo: str
    fecha_creacion: datetime
    fecha_extracto: Optional[date] = None
    movimientos: List[MovimientoBancoResponse]

    class Config:
        from_attributes = True

class ExtractoBancarioCreate(BaseModel):
    nombre_archivo: str
    fecha_extracto: Optional[date] = None
