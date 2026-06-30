"""Envio de emails via Resend HTTP API.

Servicio compartido: lo usa el scheduler de backup y el flujo de recuperacion
de contraseña. Centraliza la integracion con Resend para que cambiar de
proveedor sea un solo lugar.

Si RESEND_API_KEY no esta seteada, levanta RuntimeError — el caller decide
si silenciar (caso: scheduler en dev) o propagar al usuario.
"""

import base64
import logging
from typing import Optional

import requests

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def send_email(
    to: str,
    subject: str,
    html: str,
    attachment_name: Optional[str] = None,
    attachment_bytes: Optional[bytes] = None,
    reply_to: Optional[str] = None,
) -> None:
    """Envia un email via Resend. Levanta RuntimeError si falla.

    Args:
        to: destinatario (email)
        subject: asunto
        html: cuerpo HTML
        attachment_name: nombre del archivo adjunto (opcional)
        attachment_bytes: contenido binario del adjunto (opcional)
        reply_to: email para "Responder a" (opcional)
    """
    if not settings.resend_api_key:
        raise RuntimeError("RESEND_API_KEY no configurada")

    url = "https://api.resend.com/emails"
    headers = {
        "Authorization": f"Bearer {settings.resend_api_key}",
        "Content-Type": "application/json",
    }
    body: dict = {
        "from": settings.backup_email_from,
        "to": [to],
        "subject": subject,
        "html": html,
    }
    if reply_to:
        body["reply_to"] = [reply_to]
    if attachment_name and attachment_bytes is not None:
        body["attachments"] = [{
            "filename": attachment_name,
            "content": base64.b64encode(attachment_bytes).decode("ascii"),
        }]

    r = requests.post(url, headers=headers, json=body, timeout=30)
    if r.status_code >= 300:
        raise RuntimeError(f"Resend devolvio {r.status_code}: {r.text[:300]}")
