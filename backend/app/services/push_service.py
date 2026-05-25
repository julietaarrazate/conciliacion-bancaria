"""Servicio de Web Push (VAPID) — envía notificaciones al browser."""
import json
import logging

logger = logging.getLogger(__name__)


def send_push(endpoint: str, p256dh: str, auth_key: str, title: str, body: str, url: str = "/") -> bool:
    """Envía una web push notification. Retorna True si OK, False si falló."""
    try:
        from pywebpush import webpush, WebPushException
        from app.config import get_settings
        settings = get_settings()
        if not settings.vapid_private_key or not settings.vapid_public_key:
            logger.warning("VAPID keys no configuradas — push deshabilitado")
            return False
        subscription_info = {
            "endpoint": endpoint,
            "keys": {"p256dh": p256dh, "auth": auth_key},
        }
        webpush(
            subscription_info=subscription_info,
            data=json.dumps({"title": title, "body": body, "url": url}),
            vapid_private_key=settings.vapid_private_key,
            vapid_claims={"sub": f"mailto:{settings.admin_email}"},
        )
        return True
    except Exception as e:
        logger.error("Push error: %s", e)
        return False


def send_push_to_all(db, title: str, body: str, url: str = "/") -> int:
    """Envía push a todas las subscripciones. Retorna cantidad de envíos exitosos."""
    from app.models.push_subscription import PushSubscription
    subs = db.query(PushSubscription).all()
    ok = 0
    dead = []
    for s in subs:
        if send_push(s.endpoint, s.p256dh, s.auth, title, body, url):
            ok += 1
        else:
            dead.append(s.id)
    # Purge dead subscriptions (410 Gone)
    if dead:
        db.query(PushSubscription).filter(PushSubscription.id.in_(dead)).delete(synchronize_session=False)
        db.commit()
    return ok
