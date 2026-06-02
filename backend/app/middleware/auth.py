from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.models.user import User, RoleEnum
from app.models.revoked_token import RevokedToken
from app.database import get_db
from app.services.auth import verify_token

security = HTTPBearer()

async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
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

    # Revocacion: si el token tiene jti y esta en la lista, rechazar
    # Tokens viejos sin jti pasan derecho (backward compat con sesiones activas)
    jti = payload.get("jti")
    if jti and db.query(RevokedToken).filter(RevokedToken.jti == jti).first():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión cerrada"
        )

    user = db.query(User).filter(User.email == email).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado o inactivo"
        )

    # Override de org en memoria: si el request trae ?org_id= y el usuario
    # tiene ese ID en su whitelist (o es superadmin), lo aplicamos sin persistir.
    raw_org = request.query_params.get("org_id")
    if raw_org and raw_org.isdigit():
        requested_org = int(raw_org)
        if user.is_superadmin or requested_org in (user.allowed_org_ids or []):
            # Expunge para que SQLAlchemy no persista el cambio en el commit del endpoint
            db.expunge(user)
            user.organizacion_id = requested_org

    return user


def can_switch_org(user: User, org_id: int) -> bool:
    """True si el usuario puede operar en esa org (superadmin siempre; contador si está en allowed_org_ids)."""
    if user.is_superadmin:
        return True
    allowed = user.allowed_org_ids or []
    return org_id in allowed


async def require_superadmin(current_user: User = Depends(get_current_user)) -> User:
    """Solo superadmin (Julieta) puede acceder."""
    if not current_user.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el superadmin puede realizar esta acción"
        )
    return current_user


def require_permission(permission: str):
    """Verifica permisos por rol. Superadmin tiene todos los permisos."""
    async def check_permission(current_user: User = Depends(get_current_user)):
        if current_user.is_superadmin:
            return current_user

        permissions = {
            "admin": ["upload_files", "reconcile", "manage_users", "view_audit", "view_accounting", "manage_finance", "admin_accounting", "delete_records"],
            "operador": ["upload_files", "reconcile", "manage_finance", "view_accounting"],
            "revisor": ["view_results", "view_accounting"],
            "auditor": ["view_audit", "view_accounting", "manage_finance"],
            # Contador de prueba: opera (sube, concilia, finanzas, liquidaciones) y ve
            # contabilidad + auditoría/actividad en solo lectura. NO tiene delete_records
            # (no puede borrar nada) ni manage_users (no ve Usuarios/Orgs/Papelera).
            "contador": ["upload_files", "reconcile", "manage_finance", "view_accounting", "view_audit"],
        }

        role_value = current_user.role if isinstance(current_user.role, str) else getattr(current_user.role, "value", None)
        if permission not in permissions.get(role_value, []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para esta acción"
            )

        return current_user

    return check_permission
