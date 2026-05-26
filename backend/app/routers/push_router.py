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

    settings = get_settings()
    subs = db.query(PushSubscription).all()
    diag = {
        "vapid_configurado": bool(settings.vapid_private_key and settings.vapid_public_key),
        "suscripciones_en_db": len(subs),
        "enviadas": 0,
        "errores": [],
    }

    if not diag["vapid_configurado"]:
        diag["errores"].append("Faltan VAPID_PRIVATE_KEY o VAPID_PUBLIC_KEY en Render")
        return diag

    if not subs:
        diag["errores"].append("No hay suscripciones guardadas — activá notificaciones en /perfil primero")
        return diag

    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        diag["errores"].append("pywebpush no está instalado en el servidor — verificá requirements.txt")
        return diag

    for s in subs:
        try:
            import json
            webpush(
                subscription_info={"endpoint": s.endpoint, "keys": {"p256dh": s.p256dh, "auth": s.auth}},
                data=json.dumps({"title": "Cuadra", "body": "Notificaciones activas ✓", "url": "/resumen"}),
                vapid_private_key=settings.vapid_private_key,
                vapid_claims={"sub": f"mailto:{settings.admin_email}"},
            )
            diag["enviadas"] += 1
        except WebPushException as e:
            msg = f"WebPushException sub={s.id}: {e} | response={getattr(e, 'response', None)}"
            logger.error(msg)
            diag["errores"].append(msg)
        except Exception as e:
            msg = f"Error sub={s.id}: {type(e).__name__}: {e}"
            logger.error(msg)
            diag["errores"].append(msg)

    return diag


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
