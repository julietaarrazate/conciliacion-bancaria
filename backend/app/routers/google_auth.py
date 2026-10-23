import logging
import requests as http_requests
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from slowapi import Limiter
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.routers.auth import emitir_sesion
from app.services.limites import ip_cliente
from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()
limiter = Limiter(key_func=ip_cliente)


class GoogleCodePayload(BaseModel):
    code: str
    redirect_uri: str


def _email_verificado(valor) -> bool:
    """tokeninfo devuelve email_verified como string ("true"/"false"): un "false"
    no vacío no puede contar como verificado."""
    return valor is True or (isinstance(valor, str) and valor.strip().lower() == "true")


@router.post("/google")
@limiter.limit("10/minute")
def google_login(request: Request, payload: GoogleCodePayload, db: Session = Depends(get_db)):
    """Intercambia un Google authorization code y devuelve un JWT de sesión.
    Flujo auth-code (redirect) — funciona en mobile sin popups.
    Solo funciona para usuarios ya registrados en el sistema.
    Activar seteando GOOGLE_CLIENT_ID y GOOGLE_CLIENT_SECRET en Render.
    """
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(503, "Google OAuth no está configurado en este servidor")

    # 1) Intercambiar el authorization code por tokens
    try:
        token_resp = http_requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": payload.code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": payload.redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=10,
        )
    except Exception:
        raise HTTPException(503, "No se pudo contactar a Google")

    if token_resp.status_code != 200:
        logger.warning("Google token exchange falló: %s", token_resp.text[:300])
        raise HTTPException(401, "No se pudo validar el código de Google")

    id_token = token_resp.json().get("id_token")
    if not id_token:
        raise HTTPException(401, "Google no devolvió un id_token")

    # 2) Verificar el id_token y extraer el email
    try:
        resp = http_requests.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"id_token": id_token},
            timeout=10,
        )
    except Exception:
        raise HTTPException(503, "No se pudo verificar el token con Google")

    if resp.status_code != 200:
        raise HTTPException(401, "Token de Google inválido o expirado")

    info = resp.json()

    if info.get("aud") != settings.google_client_id:
        raise HTTPException(401, "Token de Google no pertenece a esta aplicación")

    email = info.get("email", "").lower().strip()
    if not email or not _email_verificado(info.get("email_verified")):
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

    logger.info("Google OAuth login: %s", email)
    # Mismo camino que el login con contraseña: admin/superadmin pasan por el 2FA
    # por email (si RESEND está configurado) en vez de recibir el token directo.
    return emitir_sesion(db, user)
