from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.models.user import User, RoleEnum
from app.database import get_db
from app.services.auth import verify_token

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
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
        # Mapeo de permisos por rol (clave es el valor string del enum)
        permissions = {
            "admin": ["upload_files", "reconcile", "manage_users", "view_audit"],
            "operador": ["upload_files", "reconcile"],
            "revisor": ["view_results"],
            "auditor": ["view_audit"]
        }

        role_value = current_user.role if isinstance(current_user.role, str) else getattr(current_user.role, "value", None)
        if permission not in permissions.get(role_value, []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para esta acción"
            )

        return current_user

    return check_permission
