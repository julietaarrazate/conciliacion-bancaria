from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.models.user import User
from app.schemas.user import UserResponse
from app.middleware.auth import get_current_user
from app.database import get_db
from app.services.auth import get_password_hash, verify_password

router = APIRouter(tags=["me"])


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/me/change-password")
def change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Cambia la contraseña del usuario autenticado"""
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(400, "Contraseña actual incorrecta")
    if len(payload.new_password) < 6:
        raise HTTPException(400, "La nueva contraseña debe tener al menos 6 caracteres")
    current_user.hashed_password = get_password_hash(payload.new_password)
    db.commit()
    return {"ok": True, "mensaje": "Contraseña actualizada correctamente"}


class UpdateProfileRequest(BaseModel):
    full_name: str | None = None
    email: str | None = None


@router.patch("/me", response_model=UserResponse)
def update_profile(
    payload: UpdateProfileRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Actualiza perfil del usuario autenticado (nombre, email)"""
    if payload.full_name:
        current_user.full_name = payload.full_name
    if payload.email:
        existing = db.query(User).filter(User.email == payload.email, User.id != current_user.id).first()
        if existing:
            raise HTTPException(400, "Ese email ya está en uso")
        current_user.email = payload.email
    db.commit()
    db.refresh(current_user)
    return current_user
