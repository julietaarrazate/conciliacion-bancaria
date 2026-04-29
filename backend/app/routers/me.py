from fastapi import APIRouter, Depends
from app.models.user import User
from app.schemas.user import UserResponse
from app.middleware.auth import get_current_user

router = APIRouter(tags=["me"])


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Retorna el usuario actualmente autenticado"""
    return current_user
