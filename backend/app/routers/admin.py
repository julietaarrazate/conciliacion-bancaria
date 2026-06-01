from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import text
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
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin)
):
    """Lista todos los usuarios. Solo superadmin (Julieta)."""
    q = db.query(User)
    if role is not None:
        q = q.filter(User.role == role)
    if org_id is not None:
        q = q.filter(User.organizacion_id == org_id)
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
             "organizacion_id": user.organizacion_id, "allowed_org_ids": user.allowed_org_ids}

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

    if payload.allowed_org_ids is not None:
        from app.models.organizacion import Organizacion as _Org
        for oid in payload.allowed_org_ids:
            if not db.query(_Org).filter(_Org.id == oid).first():
                raise HTTPException(status_code=404, detail=f"Organización {oid} no encontrada")
        user.allowed_org_ids = payload.allowed_org_ids

    db.commit()
    db.refresh(user)

    registrar_log(
        db=db,
        usuario_id=current_user.id,
        tabla="users",
        registro_id=user.id,
        accion="UPDATE",
        cambios={"antes": antes, "despues": {"full_name": user.full_name, "role": user.role, "is_active": user.is_active, "organizacion_id": user.organizacion_id, "allowed_org_ids": user.allowed_org_ids}}
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

    # NULL out FK references so the DELETE doesn't hit constraint violations
    nullify = [
        "UPDATE auditoria_logs       SET usuario_id  = NULL WHERE usuario_id  = :uid",
        "UPDATE planillas             SET usuario_id  = NULL WHERE usuario_id  = :uid",
        "UPDATE extractos_bancarios   SET creado_por  = NULL WHERE creado_por  = :uid",
        "UPDATE liquidaciones         SET created_by  = NULL WHERE created_by  = :uid",
        "UPDATE liquidaciones         SET aprobado_by = NULL WHERE aprobado_by = :uid",
        "UPDATE liquidaciones         SET cerrado_by  = NULL WHERE cerrado_by  = :uid",
        "UPDATE arqueos_diarios       SET creado_por  = NULL WHERE creado_por  = :uid",
        "UPDATE cheques               SET usuario_id  = NULL WHERE usuario_id  = :uid",
        "UPDATE egresos               SET usuario_id  = NULL WHERE usuario_id  = :uid",
        "UPDATE asientos              SET usuario_id  = NULL WHERE usuario_id  = :uid",
        "DELETE FROM login_approvals                          WHERE user_id    = :uid",
        "DELETE FROM revoked_tokens                           WHERE user_id    = :uid",
    ]
    for sql in nullify:
        try:
            db.execute(text(sql), {"uid": user_id})
        except Exception:
            pass  # tabla puede no existir en instalaciones viejas

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
