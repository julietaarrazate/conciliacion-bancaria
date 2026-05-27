from pydantic import BaseModel
from datetime import datetime, date
from typing import List, Optional


class MovimientoBancoResponse(BaseModel):
    id: int
    extracto_id: int
    orden: Optional[int] = None
    fecha: Optional[date] = None
    mes: Optional[str] = None
    titular: Optional[str] = None
    monto: float
    saldo: Optional[float] = None
    cliente_acreditado: Optional[str] = None
    fecha_acred: Optional[date] = None
    source: Optional[str] = 'extracto'  # 'extracto' | 'um'

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


class ExtractoListItem(BaseModel):
    id: int
    nombre_archivo: str
    fecha_creacion: datetime
    total_movimientos: int

    class Config:
        from_attributes = True


class ExtractoListResponse(BaseModel):
    total: int
    items: List[ExtractoListItem]


class MergeUMResponse(BaseModel):
    extracto_id: int
    agregados: int
    duplicados: int
    duplicados_internos: int = 0
    duplicados_internos_detalle: list = []
    total_recibido: int
    corte_metodo: Optional[str] = None
    corte_saldo_detectado: Optional[float] = None


class MovimientosFiltradosResponse(BaseModel):
    extracto_id: int
    total: int
    items: List[MovimientoBancoResponse]
