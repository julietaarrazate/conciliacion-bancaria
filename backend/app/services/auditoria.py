"""Servicio para registrar logs de auditoría automáticamente"""

from decimal import Decimal
from typing import Any, Optional
from sqlalchemy.orm import Session
from app.models.auditoria import AuditoriaLog


def _serializable(obj: Any) -> Any:
    """Convierte recursivamente Decimal→float para que el dict sea JSON-serializable."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serializable(v) for v in obj]
    return obj


def registrar_log(
    db: Session,
    usuario_id: int,
    tabla: str,
    registro_id: int,
    accion: str,
    cambios: Optional[dict] = None,
    autocommit: bool = True
) -> AuditoriaLog:
    """
    Registra una entrada en el log de auditoría.

    Args:
        db: sesión de BD
        usuario_id: id del usuario que hace la acción
        tabla: nombre de tabla afectada (ej: "planillas", "extractos_bancarios")
        registro_id: id del registro afectado
        accion: "INSERT", "UPDATE", "DELETE", o acción custom como "CONCILIAR"
        cambios: dict con detalles del cambio
        autocommit: si True, hace commit automático
    """
    log = AuditoriaLog(
        usuario_id=usuario_id,
        tabla=tabla,
        registro_id=registro_id,
        accion=accion,
        cambios=_serializable(cambios) if cambios else cambios,
    )
    db.add(log)
    if autocommit:
        db.commit()
        db.refresh(log)
    return log
