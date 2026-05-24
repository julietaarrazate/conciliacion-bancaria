"""Logica de recuperacion de contraseña por email.

Flujo:
1. Usuario pide reset (POST /auth/forgot-password con su email)
2. Si el email existe, generamos token aleatorio de 32 bytes (256 bits)
3. Guardamos SHA-256 del token en DB (nunca el plano)
4. Enviamos email con link `https://app.../restablecer-password?token=PLANO`
5. Usuario abre link, escribe nueva password, POST /auth/reset-password
6. Hasheamos el token recibido, lo buscamos, validamos, cambiamos password
7. Marcamos token como usado (uso unico) e invalidamos OTROS tokens del mismo user

Seguridad:
- Tokens son 32 bytes random (secrets.token_urlsafe) — imposibles de adivinar
- Solo guardamos el hash — si la DB se filtra, los tokens no se pueden usar
- Vida util: 1 hora
- Uso unico: una vez consumido, no se puede volver a usar
- Al cambiar password, se invalidan TODOS los otros tokens del user
- /forgot-password siempre devuelve 200 aunque el email no exista
  (no leakea cuales emails estan registrados)
"""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.password_reset import PasswordResetToken
from app.models.user import User
from app.services.auth import get_password_hash
from app.services.email_sender import send_email

logger = logging.getLogger(__name__)
settings = get_settings()

# Vida util del token: 1 hora desde la generacion.
TOKEN_TTL_MINUTES = 60


def _hash_token(token_plano: str) -> str:
    """SHA-256 hex (64 chars). Igual logica que guardamos en la columna token_hash."""
    return hashlib.sha256(token_plano.encode("utf-8")).hexdigest()


def crear_token_y_enviar_email(
    db: Session,
    email: str,
    requested_ip: Optional[str] = None,
) -> bool:
    """Genera token, lo guarda hasheado, envia el email.

    Devuelve True si se proceso (email existia y se mando), False si no.
    El caller siempre debe devolver 200 al usuario igual — no leakeamos esto.
    """
    user = db.query(User).filter(User.email == email.lower().strip()).first()
    if not user:
        logger.info("forgot-password: email %s no existe (silencioso)", email)
        return False
    if not user.is_active:
        logger.info("forgot-password: user %s inactivo", email)
        return False

    # Generar token plano (43 chars URL-safe) y guardar hash
    token_plano = secrets.token_urlsafe(32)
    token_hash = _hash_token(token_plano)
    now = datetime.utcnow()
    expires_at = now + timedelta(minutes=TOKEN_TTL_MINUTES)

    registro = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        created_at=now,
        expires_at=expires_at,
        requested_ip=requested_ip,
    )
    db.add(registro)
    db.commit()

    # Construir link al frontend
    reset_url = f"{settings.frontend_url.rstrip('/')}/restablecer-password?token={token_plano}"

    try:
        send_email(
            to=user.email,
            subject="Recuperar contraseña — Conciliacion Bancaria",
            html=_html_email(user.full_name, reset_url, TOKEN_TTL_MINUTES),
        )
        logger.info("forgot-password: email enviado a %s", email)
        return True
    except Exception as ex:
        logger.error("forgot-password: fallo envio a %s: %s", email, ex)
        # No tiramos error al usuario: aunque falle, devolvemos OK
        # (asi tampoco se puede usar el endpoint para verificar emails)
        return False


def validar_y_cambiar_password(
    db: Session,
    token_plano: str,
    nueva_password: str,
) -> Optional[User]:
    """Valida el token y cambia la password.

    Devuelve el User actualizado si OK, None si el token es invalido/expirado/usado.
    """
    if not token_plano or len(token_plano) < 20:
        return None
    if not nueva_password or len(nueva_password) < 6:
        return None

    token_hash = _hash_token(token_plano)
    registro = db.query(PasswordResetToken).filter(
        PasswordResetToken.token_hash == token_hash
    ).first()
    if not registro:
        logger.warning("reset-password: token no encontrado")
        return None
    if registro.used_at is not None:
        logger.warning("reset-password: token ya usado (user_id=%s)", registro.user_id)
        return None
    if registro.expires_at < datetime.utcnow():
        logger.warning("reset-password: token expirado (user_id=%s)", registro.user_id)
        return None

    user = db.query(User).filter(User.id == registro.user_id).first()
    if not user or not user.is_active:
        return None

    # Cambiar password
    user.hashed_password = get_password_hash(nueva_password)
    # Marcar este token como usado
    registro.used_at = datetime.utcnow()
    # Invalidar TODOS los otros tokens activos de este user (defense in depth)
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.id != registro.id,
        PasswordResetToken.used_at.is_(None),
    ).update({"used_at": datetime.utcnow()})
    db.commit()
    db.refresh(user)
    logger.info("reset-password: password cambiada para user_id=%s", user.id)
    return user


def _html_email(nombre: str, reset_url: str, ttl_min: int) -> str:
    """Email HTML con boton de reset. Diseño limpio, alta legibilidad mobile."""
    saludo = (nombre or "").split()[0] if nombre else "Hola"
    return f"""
<div style="font-family:-apple-system,Segoe UI,sans-serif;max-width:520px;margin:0 auto;color:#222;padding:24px">
  <h2 style="color:#111;margin:0 0 12px;font-size:20px">Recuperar contraseña</h2>
  <p style="color:#444;margin:0 0 16px;font-size:14px;line-height:1.5">
    Hola {saludo}, recibimos un pedido para restablecer tu contraseña de
    <strong>Conciliacion Bancaria</strong>.
  </p>
  <p style="color:#444;margin:0 0 24px;font-size:14px;line-height:1.5">
    Tocá el boton para elegir una nueva contraseña. El link sirve por {ttl_min} minutos
    y se desactiva en cuanto lo uses.
  </p>
  <div style="text-align:center;margin:24px 0">
    <a href="{reset_url}"
       style="display:inline-block;background:#0B0B0F;color:#FFD60A;text-decoration:none;
              padding:14px 32px;border-radius:10px;font-weight:600;font-size:15px">
      Elegir nueva contraseña
    </a>
  </div>
  <p style="color:#666;font-size:12px;margin:24px 0 4px">
    Si el boton no funciona, copia este link en tu navegador:
  </p>
  <p style="color:#0B0B0F;font-size:12px;word-break:break-all;font-family:monospace;
            background:#f6f6f8;padding:10px;border-radius:6px;margin:0 0 24px">
    {reset_url}
  </p>
  <p style="color:#888;font-size:11px;margin:24px 0 0;border-top:1px solid #eee;padding-top:16px">
    Si no pediste este cambio, ignora este email — tu contraseña no se va a modificar.
  </p>
</div>
""".strip()
