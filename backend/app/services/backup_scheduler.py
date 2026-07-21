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

import gzip
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.config import get_settings
from app.database import SessionLocal
from app.models.organizacion import Organizacion
from app.models.user import User
from app.services.backup_service import export_org_backup
from app.services.auditoria import registrar_log
from app.services.email_sender import send_email

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


def start_alertas_push_job() -> None:
    """Agrega el job de push notifications de alertas al scheduler (8:00 ART).
    Arranca el scheduler si todavia no estaba corriendo.
    No hace nada si VAPID no esta configurado.
    """
    global _scheduler
    if not settings.vapid_private_key or not settings.vapid_public_key:
        logger.info("Push alertas no configurado: faltan VAPID_PRIVATE_KEY / VAPID_PUBLIC_KEY")
        return

    # Reusar el scheduler existente o crear uno nuevo
    if _scheduler is None:
        sched = BackgroundScheduler(timezone=_ART)
        sched.start()
        _scheduler = sched

    if _scheduler.get_job("push_alertas_diario"):
        return  # ya registrado

    _scheduler.add_job(
        _run_alertas_push,
        CronTrigger(hour=10, minute=0, timezone=_ART),
        id="push_alertas_diario",
        name="Push alertas diarias (cheques + movimientos)",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )
    logger.info("Push alertas diarias programadas para 10:00 ART")


def _run_alertas_push() -> None:
    """Revisa cheques por vencer, movimientos sin asignar, planillas con descuadre de
    total y filas ambiguas por revisar. Manda push si hay urgentes."""
    from datetime import datetime
    from sqlalchemy import func
    from app.models.cheque import Cheque
    from app.models.extracto import MovimientoBanco
    from app.models.planilla import Planilla, PlanillaRow

    db = SessionLocal()
    try:
        hoy = datetime.now(_ART).date()
        en_3_dias = hoy + timedelta(days=3)
        hace_7_dias = hoy - timedelta(days=7)

        cheques_urgentes = (
            db.query(Cheque)
            .filter(
                Cheque.estado == "pendiente",
                Cheque.fecha_deposito != None,
                Cheque.fecha_deposito >= hoy,
                Cheque.fecha_deposito <= en_3_dias,
            )
            .count()
        )

        movs_sin_asignar = (
            db.query(MovimientoBanco)
            .filter(
                MovimientoBanco.cliente_acreditado == None,
                MovimientoBanco.monto > 0,
                MovimientoBanco.fecha != None,
                MovimientoBanco.fecha <= hace_7_dias,
            )
            .count()
        )

        _descuadre_subq = (
            db.query(Planilla.id)
            .outerjoin(PlanillaRow, PlanillaRow.planilla_id == Planilla.id)
            .filter(
                Planilla.deleted_at.is_(None),
                Planilla.total_declarado.isnot(None),
            )
            .group_by(Planilla.id, Planilla.total_declarado)
            .having(func.abs(Planilla.total_declarado - func.coalesce(func.sum(PlanillaRow.monto), 0)) > 1)
            .subquery()
        )
        planillas_descuadre = db.query(func.count()).select_from(_descuadre_subq).scalar() or 0

        filas_ambiguas = (
            db.query(PlanillaRow)
            .join(Planilla, PlanillaRow.planilla_id == Planilla.id)
            .filter(
                Planilla.deleted_at.is_(None),
                PlanillaRow.status.like("ambiguo%"),
            )
            .count()
        )

        partes = []
        if cheques_urgentes:
            n = cheques_urgentes
            partes.append(f"{n} cheque{'s' if n > 1 else ''} vence{'n' if n > 1 else ''} en 3 días")
        if movs_sin_asignar:
            n = movs_sin_asignar
            partes.append(f"{n} movimiento{'s' if n > 1 else ''} sin conciliar (+7 días)")
        if planillas_descuadre:
            n = planillas_descuadre
            partes.append(f"{n} planilla{'s' if n > 1 else ''} con total que no cuadra")
        if filas_ambiguas:
            n = filas_ambiguas
            partes.append(f"{n} fila{'s' if n > 1 else ''} ambigua{'s' if n > 1 else ''} por revisar")

        if not partes:
            logger.info("Push alertas: sin novedades urgentes hoy")
            return

        from app.services.push_service import send_push_to_all
        body = " · ".join(partes)
        sent = send_push_to_all(db, "Cuadra — Alerta", body, "/resumen")
        logger.info("Push alertas enviadas a %d suscriptores: %s", sent, body)
    except Exception as ex:
        logger.error("Push alertas job FALLO: %s", ex, exc_info=True)
    finally:
        db.close()


def start_r2_storage_alert_job() -> None:
    """Cron diario 09:00 ART — chequea uso de R2 y alerta si > 8 GB."""
    global _scheduler
    if not settings.s3_endpoint or not settings.resend_api_key:
        logger.info("Alerta R2 no configurada: falta S3_ENDPOINT o RESEND_API_KEY")
        return
    if _scheduler is None:
        sched = BackgroundScheduler(timezone=_ART)
        sched.start()
        _scheduler = sched
    if _scheduler.get_job("r2_storage_alert"):
        return
    _scheduler.add_job(
        _run_r2_storage_alert,
        CronTrigger(hour=9, minute=0, timezone=_ART),
        id="r2_storage_alert",
        name="Alerta diaria de uso de R2",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )
    logger.info("Alerta de uso R2 programada para 09:00 ART")


def _run_r2_storage_alert() -> None:
    """Chequea uso total de R2. Si > 8 GB, envía email de alerta."""
    try:
        import os
        import boto3
        from botocore.config import Config

        endpoint = os.getenv("S3_ENDPOINT")
        bucket = os.getenv("S3_BUCKET")
        access_key = os.getenv("S3_ACCESS_KEY")
        secret_key = os.getenv("S3_SECRET_KEY")
        region = os.getenv("S3_REGION", "auto")

        if not all([endpoint, bucket, access_key, secret_key]):
            logger.warning("R2 storage alert: configuracion incompleta")
            return

        client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=Config(signature_version="s3v4"),
        )

        total_bytes = 0
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket):
            if "Contents" in page:
                for obj in page["Contents"]:
                    total_bytes += obj.get("Size", 0)

        total_gb = total_bytes / (1024 ** 3)
        limite_gb = 10
        umbral_gb = 8

        logger.info("Uso de R2: %.2f GB / %.0f GB", total_gb, limite_gb)

        if total_gb > umbral_gb:
            subject = f"⚠️ Alerta R2: Almacenamiento en {total_gb:.2f} GB"
            html_body = f"""
<div style="font-family:sans-serif;max-width:500px;margin:0 auto;color:#222">
  <h2 style="color:#d9534f">⚠️ Alerta de almacenamiento R2</h2>
  <p style="font-size:16px;margin:16px 0">
    <strong>Uso actual: {total_gb:.2f} GB</strong> (de {limite_gb} GB gratis/mes)
  </p>
  <p style="color:#666;font-size:14px;margin:16px 0">
    Se ha alcanzado el <strong>80% del límite gratuito</strong>.
    Una vez que se superen los {limite_gb} GB en un mes,
    los costos serán de <strong>$0.015/GB</strong>.
  </p>
  <p style="color:#666;font-size:14px;margin:16px 0">
    <strong>Recomendación:</strong> Revisar fotos duplicadas o antiguas que puedan eliminarse.
  </p>
  <table style="width:100%;border-collapse:collapse;margin:20px 0;font-size:13px">
    <tr style="background:#f5f5f5">
      <td style="padding:8px 12px;border:1px solid #ddd"><strong>Uso</strong></td>
      <td style="padding:8px 12px;border:1px solid #ddd;text-align:right"><strong>{total_gb:.2f} GB</strong></td>
    </tr>
    <tr>
      <td style="padding:8px 12px;border:1px solid #ddd">Límite gratuito</td>
      <td style="padding:8px 12px;border:1px solid #ddd;text-align:right">{limite_gb} GB</td>
    </tr>
    <tr>
      <td style="padding:8px 12px;border:1px solid #ddd">% disponible</td>
      <td style="padding:8px 12px;border:1px solid #ddd;text-align:right">{((limite_gb - total_gb) / limite_gb * 100):.0f}%</td>
    </tr>
  </table>
</div>
"""
            send_email(
                to=settings.backup_email_to,
                subject=subject,
                html=html_body,
            )
            logger.warning("Alerta R2 enviada: %.2f GB / %.0f GB", total_gb, limite_gb)
        else:
            logger.info("Uso R2 OK (%.2f / %.0f GB)", total_gb, limite_gb)
    except Exception as ex:
        logger.error("R2 storage alert FALLO: %s", ex, exc_info=True)


def start_token_cleanup_job() -> None:
    """Cron diario 03:30 ART — purga tokens revocados que ya estan vencidos."""
    global _scheduler
    if _scheduler is None:
        sched = BackgroundScheduler(timezone=_ART)
        sched.start()
        _scheduler = sched
    if _scheduler.get_job("token_cleanup"):
        return
    _scheduler.add_job(
        _run_token_cleanup,
        CronTrigger(hour=3, minute=30, timezone=_ART),
        id="token_cleanup",
        name="Purga de tokens revocados vencidos",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )
    logger.info("Limpieza de tokens revocados programada para 03:30 ART")


def _run_token_cleanup() -> None:
    from datetime import datetime, timedelta
    from app.models.revoked_token import RevokedToken
    from app.models.login_approval import LoginApproval
    from app.models.twofa_code import TwofaCode
    db = SessionLocal()
    try:
        ahora = datetime.utcnow()
        hace_30_dias = ahora - timedelta(days=30)
        hace_7_dias = ahora - timedelta(days=7)

        rt = db.query(RevokedToken).filter(RevokedToken.expires_at < ahora).delete(synchronize_session=False)
        la = db.query(LoginApproval).filter(
            LoginApproval.request_expires_at < hace_30_dias
        ).delete(synchronize_session=False)
        tc = db.query(TwofaCode).filter(
            TwofaCode.expires_at < hace_7_dias
        ).delete(synchronize_session=False)

        db.commit()
        logger.info("Cleanup diario: revoked_tokens=%d login_approvals=%d twofa_codes=%d", rt, la, tc)
    except Exception as ex:
        logger.error("Token cleanup FALLO: %s", ex, exc_info=True)
    finally:
        db.close()


def start_db_keepalive_job() -> None:
    """Ping liviano a la DB cada 4 min para que Neon (free tier) no se duerma.

    Neon free tier autosuspende el compute tras ~5 min sin actividad. UptimeRobot
    pinguea /health, pero ese endpoint NO toca la DB → mantiene despierto a Render
    pero deja dormir a Neon. Resultado: al entrar después de un rato, la PRIMERA
    query de cada módulo paga la penalidad de despertar a Neon (y si se navega
    lento, Neon vuelve a dormirse entre pantalla y pantalla). Un SELECT 1 cada 4
    min desde el propio proceso FastAPI (que UptimeRobot ya mantiene vivo) evita
    que el compute idle-out, sin depender de reconfigurar UptimeRobot.
    """
    global _scheduler
    if _scheduler is None:
        sched = BackgroundScheduler(timezone=_ART)
        sched.start()
        _scheduler = sched
    if _scheduler.get_job("db_keepalive"):
        return
    _scheduler.add_job(
        _run_db_keepalive,
        IntervalTrigger(minutes=4),
        id="db_keepalive",
        name="Keep-alive de Neon (evita autosuspend)",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=120,
    )
    logger.info("Keep-alive de DB programado cada 4 min (evita autosuspend de Neon)")


def _run_db_keepalive() -> None:
    from sqlalchemy import text
    from app.database import engine
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as ex:
        # No es crítico: si falla, la próxima request despierta a Neon igual.
        logger.debug("DB keepalive ping falló (se reintenta en 4 min): %s", ex)


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

        send_email(
            to=settings.backup_email_to,
            subject=f"Backup diario · {fecha_str}",
            html=_html_email(fecha_str, resumen, len(gz_bytes), len(body_bytes)),
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


# envio de email centralizado en app/services/email_sender.py
