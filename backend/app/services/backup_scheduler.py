"""Backup automatico diario por email.

Scheduler interno (APScheduler) que todos los dias a las 03:00 ART:
1. Genera el JSON completo (todas las orgs)
2. Lo gzippea
3. Lo manda por email via Resend a la usuaria
4. Registra el resultado en auditoria y en memoria para /admin/backup/status

Pensado para correr en Render free tier: UptimeRobot mantiene el servicio
despierto pingeando /health cada 5 min, asi que el job dispara puntual.

Para habilitarlo en Render: settear RESEND_API_KEY en las env vars.
Si esta vacio, el scheduler simplemente no arranca (modo dev/opt-in).
"""

import base64
import gzip
import io
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

import requests
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import get_settings
from app.database import SessionLocal
from app.models.organizacion import Organizacion
from app.models.user import User
from app.services.backup_service import export_org_backup
from app.services.auditoria import registrar_log

logger = logging.getLogger(__name__)
settings = get_settings()

# ART = UTC-3 (Argentina no usa DST)
_ART = timezone(timedelta(hours=-3))

# Estado global del ultimo backup (en memoria; se pierde al redeploy pero
# tambien queda en auditoria). Lo expone /admin/backup/status.
_ultimo_backup: Dict[str, Any] = {
    "ultimo_intento": None,      # ISO timestamp ART
    "ultimo_ok": None,           # ISO timestamp ART (solo cuando OK)
    "ultimo_error": None,        # mensaje breve
    "tamano_bytes": None,        # tamano del .json.gz adjunto
    "destinatario": None,
}


def _scheduler_singleton() -> Optional[BackgroundScheduler]:
    """Devuelve el scheduler global (singleton). None si esta desactivado."""
    global _scheduler
    return _scheduler


_scheduler: Optional[BackgroundScheduler] = None


def start_backup_scheduler() -> None:
    """Arranca el scheduler si esta habilitado y configurado.

    No falla si no esta configurado: simplemente loguea y sale.
    """
    global _scheduler
    if not settings.backup_enabled:
        logger.info("Backup automatico DESACTIVADO (settings.backup_enabled=false)")
        return
    if not settings.resend_api_key:
        logger.info("Backup automatico no configurado: falta RESEND_API_KEY")
        return
    if _scheduler is not None:
        logger.debug("Scheduler de backup ya iniciado")
        return

    sched = BackgroundScheduler(timezone=_ART)
    trigger = CronTrigger(
        hour=settings.backup_hour_art,
        minute=settings.backup_minute,
        timezone=_ART,
    )
    sched.add_job(
        run_backup_job,
        trigger=trigger,
        id="backup_diario",
        name="Backup completo diario por email",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,  # si quedo dormido, igual lo corre dentro de 1h
    )
    sched.start()
    _scheduler = sched
    logger.info(
        "Backup automatico programado para %02d:%02d ART (envio a %s)",
        settings.backup_hour_art, settings.backup_minute, settings.backup_email_to,
    )


def stop_backup_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def run_backup_job() -> Dict[str, Any]:
    """Ejecuta el backup completo y lo envia por email. Retorna el estado.

    Tambien se puede invocar manualmente desde un endpoint admin para
    disparar un backup on-demand sin esperar al cron.
    """
    ahora_art = datetime.now(_ART).isoformat()
    _ultimo_backup["ultimo_intento"] = ahora_art
    _ultimo_backup["ultimo_error"] = None
    _ultimo_backup["destinatario"] = settings.backup_email_to

    db = SessionLocal()
    try:
        # actor del log de auditoria: el primer superadmin (Julieta)
        actor = db.query(User).filter(User.is_superadmin == True).order_by(User.id).first()
        actor_id = actor.id if actor else None

        orgs = db.query(Organizacion).all()
        payload = {
            "generado_en": ahora_art,
            "total_organizaciones": len(orgs),
            "organizaciones": [export_org_backup(db, o.id) for o in orgs],
        }
        body_bytes = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        gz_bytes = gzip.compress(body_bytes)
        _ultimo_backup["tamano_bytes"] = len(gz_bytes)

        fecha_str = datetime.now(_ART).strftime("%Y-%m-%d")
        filename = f"conciliacion_backup_{fecha_str}.json.gz"
        resumen = _resumen_humano(payload)

        _enviar_email(
            asunto=f"Backup diario · {fecha_str}",
            cuerpo_html=_html_email(fecha_str, resumen, len(gz_bytes), len(body_bytes)),
            attachment_name=filename,
            attachment_bytes=gz_bytes,
        )

        _ultimo_backup["ultimo_ok"] = datetime.now(_ART).isoformat()
        if actor_id is not None:
            try:
                registrar_log(db, actor_id, "sistema", 0, "BACKUP_AUTO_OK",
                              {"tamano_gz": len(gz_bytes), "tamano_json": len(body_bytes),
                               "orgs": len(orgs), "destinatario": settings.backup_email_to})
            except Exception:
                pass
        logger.info("Backup automatico OK: %d bytes gz enviado a %s",
                    len(gz_bytes), settings.backup_email_to)
        return {"ok": True, **_ultimo_backup}
    except Exception as ex:
        msg = f"{type(ex).__name__}: {ex}"
        _ultimo_backup["ultimo_error"] = msg
        try:
            actor = db.query(User).filter(User.is_superadmin == True).order_by(User.id).first()
            if actor:
                registrar_log(db, actor.id, "sistema", 0, "BACKUP_AUTO_ERROR", {"error": msg})
        except Exception:
            pass
        logger.error("Backup automatico FALLO: %s", msg, exc_info=True)
        return {"ok": False, **_ultimo_backup}
    finally:
        db.close()


def estado_backup() -> Dict[str, Any]:
    """Estado del scheduler para mostrar al admin (Julieta)."""
    sched = _scheduler_singleton()
    next_run = None
    if sched is not None:
        job = sched.get_job("backup_diario")
        if job and job.next_run_time:
            next_run = job.next_run_time.astimezone(_ART).isoformat()
    return {
        "activo": sched is not None,
        "configurado": bool(settings.resend_api_key),
        "habilitado": settings.backup_enabled,
        "hora_art": f"{settings.backup_hour_art:02d}:{settings.backup_minute:02d}",
        "proximo_run": next_run,
        **_ultimo_backup,
        "destinatario": settings.backup_email_to,  # siempre el configurado
    }


# ── helpers ──────────────────────────────────────────────────────────────

def _resumen_humano(payload: Dict[str, Any]) -> Dict[str, int]:
    """Conteo total por tabla para mostrar en el cuerpo del email."""
    totales: Dict[str, int] = {}
    for org in payload.get("organizaciones", []):
        for k, v in (org.get("resumen") or {}).items():
            if isinstance(v, int):
                totales[k] = totales.get(k, 0) + v
    return totales


def _html_email(fecha: str, resumen: Dict[str, int], gz_size: int, json_size: int) -> str:
    filas = "".join(
        f'<tr><td style="padding:4px 12px;color:#555">{k}</td>'
        f'<td style="padding:4px 12px;text-align:right;font-family:monospace">{v}</td></tr>'
        for k, v in sorted(resumen.items())
    )
    return f"""
<div style="font-family:-apple-system,Segoe UI,sans-serif;max-width:520px;margin:0 auto;color:#222">
  <h2 style="color:#111;margin:0 0 8px">Backup diario — {fecha}</h2>
  <p style="color:#555;margin:0 0 16px">
    Adjunto el backup completo de Conciliacion Bancaria del dia.
    Guarda este email; el .json.gz contiene TODOS los datos para
    reconstruir el sistema en caso de desastre.
  </p>
  <table style="border-collapse:collapse;width:100%;font-size:13px;border-top:1px solid #eee;border-bottom:1px solid #eee">
    {filas}
  </table>
  <p style="color:#888;font-size:11px;margin-top:16px">
    Tamano comprimido: {gz_size/1024:.1f} KB · Sin comprimir: {json_size/1024:.1f} KB<br>
    Para restaurar: descomprimi con gunzip y consultá BACKUP_Y_RECUPERACION.md.
  </p>
</div>
""".strip()


def _enviar_email(asunto: str, cuerpo_html: str, attachment_name: str, attachment_bytes: bytes) -> None:
    """Manda email via Resend HTTP API (https://resend.com/docs/api-reference/emails/send-email)."""
    url = "https://api.resend.com/emails"
    headers = {
        "Authorization": f"Bearer {settings.resend_api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "from": settings.backup_email_from,
        "to": [settings.backup_email_to],
        "subject": asunto,
        "html": cuerpo_html,
        "attachments": [{
            "filename": attachment_name,
            "content": base64.b64encode(attachment_bytes).decode("ascii"),
        }],
    }
    r = requests.post(url, headers=headers, json=body, timeout=60)
    if r.status_code >= 300:
        raise RuntimeError(f"Resend devolvio {r.status_code}: {r.text[:300]}")
