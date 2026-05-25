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
    """Genera un par de claves VAPID. Copiá el resultado a VAPID_PRIVATE_KEY y VAPID_PUBLIC_KEY en Render."""
    if not current_user.is_superadmin:
        raise HTTPException(403, "Solo superadmin")
    try:
        from py_vapid import Vapid
        v = Vapid()
        v.generate_keys()
        return {
            "vapid_public_key": v.public_key,
            "vapid_private_key": v.private_key,
            "instrucciones": "Copiá estos valores como env vars VAPID_PUBLIC_KEY y VAPID_PRIVATE_KEY en Render, luego redeploy.",
        }
    except Exception as e:
        return {
            "error": str(e),
            "message": "Instalá pywebpush>=1.14 en requirements.txt",
        }
