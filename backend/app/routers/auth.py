import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address
from jose import jwt as jose_jwt, JWTError

from app.database import get_db
from app.models.revoked_token import RevokedToken
from app.schemas.user import UserRegister, UserLogin, UserResponse, TokenResponse
from app.services.auth import register_user, authenticate_user, create_access_token
from app.services.password_reset import (
    crear_token_y_enviar_email,
    validar_y_cambiar_password,
)
from app.services.auditoria import registrar_log
from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()
limiter = Limiter(key_func=get_remote_address)
_bearer = HTTPBearer(auto_error=False)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=20, max_length=128)
    new_password: str = Field(..., min_length=6, max_length=200)


@router.post("/register", response_model=UserResponse)
@limiter.limit("5/minute")
def register(request: Request, user_data: UserRegister, db: Session = Depends(get_db)):
    """Registra un nuevo usuario. Limitado a 5 intentos por minuto por IP."""
    user = register_user(db, user_data)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El email ya está registrado"
        )
    return user


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
def login(request: Request, credentials: UserLogin, db: Session = Depends(get_db)):
    """Autentica un usuario y retorna JWT token"""
    user = authenticate_user(db, credentials.email, credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña inválidos"
        )

    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": user.email, "user_id": user.id, "role": user.role},
        expires_delta=access_token_expires
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user
    }


@router.post("/forgot-password")
@limiter.limit("3/hour")
def forgot_password(
    request: Request,
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_db),
):
    """Envia email con link de reset si el email existe.

    Responde SIEMPRE 200 con el mismo mensaje, exista o no el email — asi
    el endpoint no se puede usar para descubrir cuales emails estan registrados.
    Rate limit: 3 pedidos por hora por IP (suficiente para uso real, blockea bots).
    """
    ip = get_remote_address(request)
    try:
        crear_token_y_enviar_email(db, payload.email, requested_ip=ip)
    except Exception as ex:
        logger.error("forgot-password: error inesperado: %s", ex, exc_info=True)

    return {
        "ok": True,
        "mensaje": (
            "Si el email está registrado, te llegará un link para cambiar la contraseña. "
            "Revisá tu bandeja de entrada (y spam) en los proximos minutos."
        ),
    }


@router.post("/reset-password")
@limiter.limit("10/hour")
def reset_password(
    request: Request,
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    """Valida el token y setea la nueva contraseña.

    Errores genericos para no leakear si el token existia o no.
    """
    user = validar_y_cambiar_password(db, payload.token, payload.new_password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El link expiró o ya fue usado. Pedí uno nuevo desde 'Olvidé mi contraseña'.",
        )

    # Auditoria: registramos el cambio (uno mismo es el actor)
    try:
        registrar_log(
            db, user.id, "users", user.id, "PASSWORD_RESET",
            {"via": "email", "ip": get_remote_address(request)},
        )
    except Exception:
        pass

    return {"ok": True, "mensaje": "Contraseña actualizada. Ya podes iniciar sesión."}


@router.post("/logout")
def logout(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: Session = Depends(get_db),
):
    """Revoca el token actual. La sesión deja de funcionar inmediatamente.

    No usa get_current_user — tokens ya inválidos también pueden cerrar sesión.
    """
    if not credentials:
        return {"ok": True}
    try:
        payload = jose_jwt.decode(
            credentials.credentials, settings.secret_key,
            algorithms=[settings.algorithm],
            options={"verify_exp": False},
        )
    except JWTError:
        return {"ok": True}

    jti = payload.get("jti")
    exp = payload.get("exp")
    if not jti or not exp:
        return {"ok": True}  # token viejo sin jti

    if not db.query(RevokedToken).filter(RevokedToken.jti == jti).first():
        db.add(RevokedToken(
            jti=jti,
            user_id=payload.get("user_id"),
            expires_at=datetime.utcfromtimestamp(exp),
        ))
        db.commit()
    return {"ok": True}
