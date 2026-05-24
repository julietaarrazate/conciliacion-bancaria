"""Endpoints de administracion del backup automatico.

- GET  /admin/backup/status   -> estado del scheduler y ultimo backup
- POST /admin/backup/run-now  -> dispara backup manual on-demand (sin esperar al cron)

Solo accesible para superadmin (Julieta).
"""

import logging
from fastapi import APIRouter, Depends

from app.models.user import User
from app.middleware.auth import require_superadmin
from app.services.backup_scheduler import estado_backup, run_backup_job

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/backup", tags=["backup"])


@router.get("/status")
def status(current_user: User = Depends(require_superadmin)):
    """Estado del scheduler: si esta activo, ultimo intento, ultimo OK, proximo run."""
    return estado_backup()


@router.post("/run-now")
def run_now(current_user: User = Depends(require_superadmin)):
    """Dispara un backup manual al instante. Util para testear que llega el email."""
    logger.info("Backup manual disparado por %s", current_user.email)
    return run_backup_job()
