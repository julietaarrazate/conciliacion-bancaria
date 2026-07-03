from pydantic import BaseModel
from datetime import datetime, date
from typing import List, Optional, Any, Dict

class PlanillaRowBase(BaseModel):
    monto: float
    cuit: Optional[str] = None
    titular: Optional[str] = None

class PlanillaRowResponse(PlanillaRowBase):
    id: int
    status: str
    orden_movimiento_acreditado: Optional[int] = None
    # Datos del movimiento bancario acreditado (para el panel de detalle)
    mov_titular: Optional[str] = None
    mov_fecha: Optional[date] = None
    mov_fecha_acred: Optional[date] = None

    class Config:
        from_attributes = True

class PlanillaResponse(BaseModel):
    id: int
    nombre_archivo: str
    cliente_id: int
    extracto_id: int
    fecha_carga: datetime
    rows: List[PlanillaRowResponse]
    # Metadatos de cómo se detectó/estandarizó la planilla en el upload.
    # Solo lo llena POST /planillas/upload; en el resto queda None.
    deteccion: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class PlanillaDetalleResponse(BaseModel):
    id: int
    nombre_archivo: str
    cliente_nombre: str
    extracto_nombre: str
    fecha_carga: datetime
    usuario_nombre: str
    rows: List[PlanillaRowResponse]
    total: int
    total_filtered: int
    acreditadas: int
    no_encontradas: int
    duplicadas: int
    sin_datos: int

    class Config:
        from_attributes = True

class ConciliacionResultado(BaseModel):
    planilla_id: int
    filas_procesadas: int
    acreditadas: int
    no_encontradas: int
    duplicadas: int
    sin_datos: int
