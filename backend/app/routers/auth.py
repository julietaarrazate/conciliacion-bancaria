import hashlib
import logging
import secrets
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address
from jose import jwt as jose_jwt, JWTError

from app.database import get_db
from app.models.revoked_token import RevokedToken
from app.models.user import User, RoleEnum
from app.models.login_approval import LoginApproval
from app.schemas.user import UserRegister, UserLogin, UserResponse, TokenResponse
from app.services.auth import register_user, authenticate_user, create_access_token
from app.services.password_reset import (
    crear_token_y_enviar_email,
    validar_y_cambiar_password,
)
from app.services.auditoria import registrar_log
from app.services.push_service import send_push_to_user
from app.middleware.auth import require_superadmin
from app.config import get_settings

# Sesión del contador de prueba: más corta (4h) y gateada por aprobación en vivo
CONTADOR_SESSION_MINUTES = 240
APPROVAL_REQUEST_TTL_MINUTES = 10
TWOFA_CODE_TTL_MINUTES = 10


def _serialize_user(user: User) -> dict:
    return UserResponse.model_validate(user).model_dump(mode="json")

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
def register(
    request: Request,
    user_data: UserRegister,
    db: Session = Depends(get_db),
    _: User = Depends(require_superadmin),
):
    """Crea un nuevo usuario. Solo el superadmin puede registrar usuarios."""
    user = register_user(db, user_data)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El email ya está registrado"
        )
    return user


@router.post("/login")
@limiter.limit("10/minute")
def login(request: Request, credentials: UserLogin, db: Session = Depends(get_db)):
    """Autentica un usuario y retorna JWT token.

    Para el rol `contador` no devuelve token directo: crea un pedido de
    aprobación (202) que el superadmin debe aceptar en vivo. El cliente del
    contador hace polling a /auth/login-approval/{id} hasta recibir el token
    (sesión de 4h). Pasadas las 4h el token expira y se repite la aprobación.
    """
    user = authenticate_user(db, credentials.email, credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña inválidos"
        )

    # Superadmin y Admin con RESEND_API_KEY → 2FA por email
    if (user.is_superadmin or user.role == RoleEnum.ADMIN.value) and settings.resend_api_key:
        from app.models.twofa_code import TwofaCode
        from app.services.email_sender import send_email
        # Limpiar códigos expirados del usuario antes de generar uno nuevo
        db.query(TwofaCode).filter(
            TwofaCode.user_id == user.id, TwofaCode.expires_at <= datetime.utcnow()
        ).delete()
        code = f"{secrets.randbelow(1_000_000):06d}"
        code_hash = hashlib.sha256(code.encode()).hexdigest()
        expires_at = datetime.utcnow() + timedelta(minutes=TWOFA_CODE_TTL_MINUTES)
        db.add(TwofaCode(user_id=user.id, code_hash=code_hash, expires_at=expires_at))
        db.commit()
        try:
            send_email(
                to=user.email,
                subject="Código de verificación Cuadra",
                html=f"""<div style="font-family:sans-serif;max-width:400px">
                  <h2>Código de verificación</h2>
                  <p>Tu código de acceso a Cuadra:</p>
                  <div style="font-size:36px;font-weight:bold;letter-spacing:8px;color:#5E6AD2;padding:16px 0">{code}</div>
                  <p style="color:#666">Válido por {TWOFA_CODE_TTL_MINUTES} minutos.</p>
                </div>""",
            )
        except Exception as _email_ex:
            logger.warning("2FA: no se pudo enviar email a %s: %s", user.email, _email_ex)
            if settings.debug:
                logger.warning("2FA DEBUG code for %s: %s", user.email, code)
        return JSONResponse(status_code=202, content={"requires_2fa": True, "email": user.email})

    # Contador → flujo de aprobación en vivo
    if user.role == RoleEnum.CONTADOR.value and not user.is_superadmin:
        secret = secrets.token_urlsafe(32)
        ap = LoginApproval(
            user_id=user.id,
            status="pending",
            poll_secret_hash=hashlib.sha256(secret.encode()).hexdigest(),
            ip=get_remote_address(request),
            request_expires_at=datetime.utcnow() + timedelta(minutes=APPROVAL_REQUEST_TTL_MINUTES),
        )
        db.add(ap)
        db.commit()
        db.refresh(ap)
        # Notificar a los superadmins (best-effort)
        try:
            for sa in db.query(User).filter(User.is_superadmin == True).all():  # noqa: E712
                send_push_to_user(
                    db, sa.id, "Solicitud de ingreso",
                    f"{user.full_name} ({user.email}) quiere ingresar", "/aprobaciones",
                )
        except Exception:
            logger.exception("No se pudo notificar la solicitud de ingreso")
        try:
            registrar_log(db, user.id, "auth", ap.id, "LOGIN_PENDING",
                          {"email": user.email, "ip": ap.ip})
        except Exception:
            pass
        return JSONResponse(status_code=202, content={
            "pending_approval": True,
            "approval_id": ap.id,
            "poll_secret": secret,
            "expires_at": ap.request_expires_at.isoformat(),
        })

    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": user.email, "user_id": user.id, "role": user.role},
        expires_delta=access_token_expires
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": _serialize_user(user),
    }


class DecisionBody(BaseModel):
    approve: bool


@router.get("/login-approval/{approval_id}")
@limiter.limit("120/minute")
def login_approval_status(
    request: Request,
    approval_id: int,
    secret: str,
    db: Session = Depends(get_db),
):
    """Polling del contador: devuelve el estado del pedido. Si fue aprobado,
    entrega el token UNA sola vez (luego se limpia). Requiere el poll_secret."""
    ap = db.query(LoginApproval).filter(LoginApproval.id == approval_id).first()
    if not ap or hashlib.sha256(secret.encode()).hexdigest() != ap.poll_secret_hash:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")

    if ap.status == "pending" and datetime.utcnow() > ap.request_expires_at:
        ap.status = "expired"
        db.commit()

    if ap.status == "approved" and ap.access_token:
        token = ap.access_token
        ap.access_token = None  # entregar una sola vez
        db.commit()
        user = db.query(User).filter(User.id == ap.user_id).first()
        return {
            "status": "approved",
            "access_token": token,
            "token_type": "bearer",
            "user": _serialize_user(user) if user else None,
        }

    return {"status": ap.status}


@router.get("/pending-approvals")
def pending_approvals(
    db: Session = Depends(get_db),
    _: User = Depends(require_superadmin),
):
    """Lista de pedidos de ingreso pendientes (para el panel del superadmin)."""
    now = datetime.utcnow()
    out = []
    for ap in db.query(LoginApproval).filter(LoginApproval.status == "pending").order_by(LoginApproval.created_at.desc()).all():
        if now > ap.request_expires_at:
            ap.status = "expired"
            continue
        u = db.query(User).filter(User.id == ap.user_id).first()
        out.append({
            "id": ap.id,
            "user_email": u.email if u else "—",
            "user_name": u.full_name if u else "—",
            "ip": ap.ip,
            "created_at": ap.created_at.isoformat(),
            "expires_at": ap.request_expires_at.isoformat(),
        })
    db.commit()
    return out


@router.post("/login-approval/{approval_id}/decide")
def decide_login_approval(
    approval_id: int,
    body: DecisionBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    """El superadmin aprueba o rechaza un pedido de ingreso. Al aprobar se
    genera el JWT del contador con expiración de 4h."""
    ap = db.query(LoginApproval).filter(LoginApproval.id == approval_id).first()
    if not ap:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    if ap.status != "pending":
        raise HTTPException(status_code=409, detail="La solicitud ya fue resuelta o expiró")
    if datetime.utcnow() > ap.request_expires_at:
        ap.status = "expired"
        db.commit()
        raise HTTPException(status_code=409, detail="La solicitud expiró")

    user = db.query(User).filter(User.id == ap.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if body.approve:
        token = create_access_token(
            data={"sub": user.email, "user_id": user.id, "role": user.role},
            expires_delta=timedelta(minutes=CONTADOR_SESSION_MINUTES),
        )
        ap.access_token = token
        ap.status = "approved"
    else:
        ap.status = "denied"
    ap.decided_at = datetime.utcnow()
    ap.decided_by = current_user.id
    db.commit()
    try:
        registrar_log(db, current_user.id, "auth", ap.id,
                      "LOGIN_APPROVED" if body.approve else "LOGIN_DENIED",
                      {"contador": user.email})
    except Exception:
        pass
    return {"status": ap.status}


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


class TwofaVerifyBody(BaseModel):
    email: str
    code: str


TWOFA_MAX_ATTEMPTS = 3


@router.post("/verify-2fa")
@limiter.limit("10/minute")
def verify_2fa(request: Request, body: TwofaVerifyBody, db: Session = Depends(get_db)):
    from app.models.twofa_code import TwofaCode
    user = db.query(User).filter(User.email == body.email, User.is_active == True).first()  # noqa: E712
    is_eligible = user and (user.is_superadmin or user.role == RoleEnum.ADMIN.value)
    if not is_eligible:
        raise HTTPException(status_code=401, detail="Código inválido o expirado")
    now = datetime.utcnow()
    # Buscar el código activo más reciente para este usuario
    active = (
        db.query(TwofaCode)
        .filter(TwofaCode.user_id == user.id, TwofaCode.used == False,  # noqa: E712
                TwofaCode.expires_at > now)
        .order_by(TwofaCode.id.desc()).first()
    )
    if not active:
        raise HTTPException(status_code=401, detail="Código inválido o expirado")
    # Lockout tras 3 intentos fallidos
    if active.failed_attempts >= TWOFA_MAX_ATTEMPTS:
        active.used = True
        db.commit()
        raise HTTPException(status_code=401, detail="Demasiados intentos. Pedí un nuevo código iniciando sesión.")
    code_hash = hashlib.sha256(body.code.strip().encode()).hexdigest()
    if active.code_hash != code_hash:
        active.failed_attempts += 1
        if active.failed_attempts >= TWOFA_MAX_ATTEMPTS:
            active.used = True
        db.commit()
        raise HTTPException(status_code=401, detail="Código inválido o expirado")
    active.used = True
    db.commit()
    access_token = create_access_token(
        data={"sub": user.email, "user_id": user.id, "role": user.role},
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )
    return {"access_token": access_token, "token_type": "bearer", "user": _serialize_user(user)}
