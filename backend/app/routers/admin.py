from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models.user import User, RoleEnum
from app.schemas.admin import (
    UserAdminResponse,
    UserAdminUpdate,
    UserListResponse
)
from app.middleware.auth import get_current_user, require_permission
from app.services.auditoria import registrar_log

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=UserListResponse)
def list_users(
    skip: int = 0,
    limit: int = 50,
    role: Optional[RoleEnum] = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("manage_users"))
):
    """Lista todos los usuarios. Requiere permiso 'manage_users' (admin)."""
    q = db.query(User)
    if role is not None:
        q = q.filter(User.role == role)
    total = q.count()
    items = q.order_by(User.created_at.desc()).offset(skip).limit(limit).all()
    return {"total": total, "items": items}


@router.get("/users/{user_id}", response_model=UserAdminResponse)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("manage_users"))
):
    """Obtiene un usuario específico"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )
    return user


@router.patch("/users/{user_id}", response_model=UserAdminResponse)
def update_user(
    user_id: int,
    payload: UserAdminUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage_users"))
):
    """Actualiza datos de un usuario (rol, nombre, activo). Solo admin."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )

    cambios_antes = {
        "full_name": user.full_name,
        "role": user.role.value if user.role else None,
        "is_active": user.is_active
    }

    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.role is not None:
        user.role = RoleEnum(payload.role.value)
    if payload.is_active is not None:
        user.is_active = payload.is_active

    db.commit()
    db.refresh(user)

    cambios_despues = {
        "full_name": user.full_name,
        "role": user.role.value if user.role else None,
        "is_active": user.is_active
    }

    registrar_log(
        db=db,
        usuario_id=current_user.id,
        tabla="users",
        registro_id=user.id,
        accion="UPDATE",
        cambios={"antes": cambios_antes, "despues": cambios_despues}
    )

    return user
