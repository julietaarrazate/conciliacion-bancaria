from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.models.user import User, RoleEnum
from app.database import get_db
from app.services.auth import verify_token

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Middleware para autenticación basada en JWT"""
    token = credentials.credentials
    payload = verify_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado"
        )

    email = payload.get("sub")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido"
        )

    user = db.query(User).filter(User.email == email).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado o inactivo"
        )

    return user

def require_permission(permission: str):
    """Decorator para verificar permisos específicos"""
    async def check_permission(current_user: User = Depends(get_current_user)):
        # Mapeo simple de permisos por rol
        permissions = {
            RoleEnum.ADMIN: ["upload_files", "reconcile", "manage_users", "view_audit"],
            RoleEnum.OPERADOR: ["upload_files", "reconcile"],
            RoleEnum.REVISOR: ["view_results"],
            RoleEnum.AUDITOR: ["view_audit"]
        }

        if permission not in permissions.get(current_user.role, []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para esta acción"
            )

        return current_user

    return check_permission
