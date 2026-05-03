from pydantic import BaseModel
from typing import Optional, Dict, Any


class OrganizacionBase(BaseModel):
    nombre: str
    plan: str = "basic"
    configuracion: Optional[Dict[str, Any]] = None
    activo: bool = True


class OrganizacionCreate(OrganizacionBase):
    pass


class OrganizacionUpdate(BaseModel):
    nombre: Optional[str] = None
    plan: Optional[str] = None
    configuracion: Optional[Dict[str, Any]] = None
    activo: Optional[bool] = None


class OrganizacionResponse(OrganizacionBase):
    id: int

    class Config:
        from_attributes = True
