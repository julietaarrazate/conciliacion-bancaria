import secrets
import logging
import requests as http_requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserResponse
from app.services.auth import create_access_token
from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


class GoogleCredentialPayload(BaseModel):
    access_token: str


def _serialize_user(user: User) -> dict:
    return UserResponse.model_validate(user).model_dump(mode="json")


@router.post("/google")
def google_login(payload: GoogleCredentialPayload, db: Session = Depends(get_db)):
    """Verifica un Google access token y devuelve un JWT de sesión.
    Solo funciona para usuarios ya registrados en el sistema.
    Activar seteando GOOGLE_CLIENT_ID en Render.
    """
    if not settings.google_client_id:
        raise HTTPException(503, "Google OAuth no está configurado en este servidor")

    # Verify the access token with Google's tokeninfo endpoint
    try:
        resp = http_requests.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"access_token": payload.access_token},
            timeout=10,
        )
    except Exception:
        raise HTTPException(503, "No se pudo verificar el token con Google")

    if resp.status_code != 200:
        raise HTTPException(401, "Token de Google inválido o expirado")

    info = resp.json()

    # azp = authorized party (client_id que emitió el token en implicit flow)
    if info.get("azp") != settings.google_client_id:
        raise HTTPException(401, "Token de Google no pertenece a esta aplicación")

    email = info.get("email", "").lower().strip()
    if not email or not info.get("email_verified"):
        raise HTTPException(401, "Email no verificado por Google")

    # Only allow existing users — admins manage user creation
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(
            404,
            "No existe una cuenta con este email. Solicitá acceso al administrador.",
        )

    if not user.is_active:
        raise HTTPException(403, "Cuenta desactivada. Contactá al administrador.")

    access_token = create_access_token({"sub": user.email})
    logger.info("Google OAuth login: %s", email)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": _serialize_user(user),
    }
