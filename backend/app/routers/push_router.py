"""Endpoints de Web Push — suscripción y configuración."""
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.push_subscription import PushSubscription
from app.models.user import User
from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/push", tags=["push"])


class SubscribeBody(BaseModel):
    endpoint: str
    keys: dict  # {p256dh, auth}


@router.get("/public-key")
def get_vapid_public_key():
    settings = get_settings()
    return {"vapid_public_key": settings.vapid_public_key or None}


@router.post("/subscribe")
def subscribe(
    body: SubscribeBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = db.query(PushSubscription).filter(PushSubscription.endpoint == body.endpoint).first()
    if existing:
        return {"ok": True, "status": "already_subscribed"}
    sub = PushSubscription(
        user_id=current_user.id,
        endpoint=body.endpoint,
        p256dh=body.keys.get("p256dh", ""),
        auth=body.keys.get("auth", ""),
    )
    db.add(sub)
    db.commit()
    return {"ok": True, "status": "subscribed"}


@router.delete("/subscribe")
def unsubscribe(
    body: SubscribeBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db.query(PushSubscription).filter(PushSubscription.endpoint == body.endpoint).delete()
    db.commit()
    return {"ok": True}


@router.post("/test")
def send_test_push(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.is_superadmin:
        raise HTTPException(403, "Solo superadmin")
    from app.services.push_service import send_push_to_all
    count = send_push_to_all(db, "Cuadra", "Notificaciones activas ✓", "/resumen")
    return {"enviadas": count}


@router.post("/setup")
def setup_vapid(current_user: User = Depends(get_current_user)):
    """Genera un par de claves VAPID en formato base64url, listas para pegar como env vars."""
    if not current_user.is_superadmin:
        raise HTTPException(403, "Solo superadmin")
    try:
        import base64
        from py_vapid import Vapid
        v = Vapid()
        v.generate_keys()
        # Private key: 32 bytes raw → base64url sin padding
        priv_bytes = v.private_key.private_numbers().private_value.to_bytes(32, "big")
        priv_b64 = base64.urlsafe_b64encode(priv_bytes).rstrip(b"=").decode("ascii")
        # Public key: punto sin comprimir (0x04 || X || Y) = 65 bytes → base64url sin padding
        nums = v.public_key.public_numbers()
        pub_bytes = b"\x04" + nums.x.to_bytes(32, "big") + nums.y.to_bytes(32, "big")
        pub_b64 = base64.urlsafe_b64encode(pub_bytes).rstrip(b"=").decode("ascii")
        return {
            "vapid_public_key": pub_b64,
            "vapid_private_key": priv_b64,
            "instrucciones": "Pegá ambos valores como env vars VAPID_PUBLIC_KEY y VAPID_PRIVATE_KEY en Render, luego redeploy.",
        }
    except Exception as e:
        logger.exception("VAPID setup error")
        raise HTTPException(500, f"Error generando VAPID keys: {e}")
