from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List


class PlanillaHistorialItem(BaseModel):
    id: int
    cliente_nombre: str
    nombre_archivo: str
    fecha_carga: datetime
    usuario_nombre: str
    total_filas: int
    acreditadas: int
    no_encontradas: int
    duplicadas: int
    sin_datos: int
    monto_conciliado: float = 0.0
    porcentaje_comision: Optional[float] = None

    class Config:
        from_attributes = True


class ExtractoHistorialItem(BaseModel):
    id: int
    nombre_archivo: str
    fecha_creacion: datetime
    usuario_nombre: str
    total_movimientos: int
    acreditados: int = 0
    banco: Optional[str] = "Banco Macro"

    class Config:
        from_attributes = True


class HistorialPlanillasResponse(BaseModel):
    total: int
    items: List[PlanillaHistorialItem]


class HistorialExtractosResponse(BaseModel):
    total: int
    items: List[ExtractoHistorialItem]
