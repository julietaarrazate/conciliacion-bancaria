import re
from pydantic import BaseModel, field_validator
from datetime import datetime
from enum import Enum

# Validación de email permisiva: formato básico, SIN rechazar dominios reservados
# (.test, .local, etc.). Esto permite crear cuentas de prueba con mails inventados
# como "contador1@cuadra.test" — el mail es solo el identificador de login, no
# necesita ser una casilla real. EmailStr de pydantic rechazaba estos dominios.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validar_email(value: str) -> str:
    v = (value or "").strip().lower()
    if not _EMAIL_RE.match(v):
        raise ValueError("Email inválido: debe tener formato usuario@dominio.ext")
    return v


class RoleEnum(str, Enum):
    ADMIN = "admin"
    OPERADOR = "operador"
    REVISOR = "revisor"
    AUDITOR = "auditor"
    CONTADOR = "contador"

class UserRegister(BaseModel):
    email: str
    full_name: str
    password: str

    @field_validator("email")
    @classmethod
    def _ck_email(cls, v): return _validar_email(v)

class UserLogin(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def _ck_email(cls, v): return _validar_email(v)

class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    role: RoleEnum
    is_active: bool
    is_superadmin: bool = False
    organizacion_id: int | None = None
    allowed_org_ids: list[int] = []
    created_at: datetime

    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class TokenRefresh(BaseModel):
    refresh_token: str
