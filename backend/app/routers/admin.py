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
from app.middleware.auth import get_current_user, require_superadmin
from app.services.auditoria import registrar_log

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=UserListResponse)
def list_users(
    skip: int = 0,
    limit: int = 50,
    role: Optional[RoleEnum] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin)
):
    """Lista todos los usuarios. Solo superadmin (Julieta)."""
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
    _: User = Depends(require_superadmin)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    return user


@router.patch("/users/{user_id}", response_model=UserAdminResponse)
def update_user(
    user_id: int,
    payload: UserAdminUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin)
):
    """Edita nombre, rol o estado de un usuario. Solo superadmin."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

    # No permitir modificar la propia cuenta de superadmin por esta vía
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Usá 'Mi Perfil' para editar tu propia cuenta")

    antes = {"full_name": user.full_name, "role": user.role, "is_active": user.is_active,
             "organizacion_id": user.organizacion_id}

    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.role is not None:
        user.role = payload.role.value
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.organizacion_id is not None:
        from app.models.organizacion import Organizacion as _Org
        if not db.query(_Org).filter(_Org.id == payload.organizacion_id).first():
            raise HTTPException(status_code=404, detail="Organización no encontrada")
        user.organizacion_id = payload.organizacion_id

    db.commit()
    db.refresh(user)

    registrar_log(
        db=db,
        usuario_id=current_user.id,
        tabla="users",
        registro_id=user.id,
        accion="UPDATE",
        cambios={"antes": antes, "despues": {"full_name": user.full_name, "role": user.role, "is_active": user.is_active, "organizacion_id": user.organizacion_id}}
    )

    return user


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin)
):
    """Elimina un usuario permanentemente. Solo superadmin."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="No podés eliminar tu propia cuenta")

    email = user.email
    nombre = user.full_name
    db.delete(user)
    db.commit()

    registrar_log(
        db=db,
        usuario_id=current_user.id,
        tabla="users",
        registro_id=user_id,
        accion="DELETE",
        cambios={"email": email, "full_name": nombre}
    )

    return {"ok": True, "mensaje": f"Usuario {email} eliminado"}
