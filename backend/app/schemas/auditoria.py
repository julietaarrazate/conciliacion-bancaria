from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Any, List


class AuditoriaLogResponse(BaseModel):
    id: int
    usuario_id: int
    usuario_nombre: Optional[str] = None
    usuario_email: Optional[str] = None
    tabla: str
    registro_id: int
    accion: str
    cambios: Optional[Any] = None
    timestamp: datetime

    class Config:
        from_attributes = True


class AuditoriaListResponse(BaseModel):
    total: int
    items: List[AuditoriaLogResponse]
