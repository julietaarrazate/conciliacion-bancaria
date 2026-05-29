from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import List, Optional
from app.schemas.user import RoleEnum


class UserAdminUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[RoleEnum] = None
    is_active: Optional[bool] = None
    organizacion_id: Optional[int] = None
    allowed_org_ids: Optional[List[int]] = None


class UserAdminResponse(BaseModel):
    id: int
    email: str
    full_name: str
    role: RoleEnum
    is_active: bool
    is_superadmin: bool = False
    organizacion_id: Optional[int] = None
    allowed_org_ids: List[int] = []
    created_at: datetime

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    total: int
    items: List[UserAdminResponse]
