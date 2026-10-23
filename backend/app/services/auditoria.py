"""Servicio para registrar logs de auditoría automáticamente"""

import logging
from contextvars import ContextVar
from decimal import Decimal
from typing import Any, Optional
from sqlalchemy.orm import Session
from app.models.auditoria import AuditoriaLog

logger = logging.getLogger(__name__)

# Org activa del request en curso. La setea `get_current_user` (middleware/auth.py) después
# de aplicar el override de `?org_id=`. Fuera de un request (schedulers, arranque) queda en
# None. `registrar_log` la usa cuando no puede saber la org del registro afectado.
org_activa: ContextVar[Optional[int]] = ContextVar("auditoria_org_activa", default=None)

_MODELOS_POR_TABLA: dict = {}


def _modelo_de_tabla(tabla: str):
    """Clase del modelo cuyo __tablename__ es `tabla` (None si `tabla` es un nombre propio)."""
    if not _MODELOS_POR_TABLA:
        from app.database import Base
        for mapper in Base.registry.mappers:
            nombre = getattr(mapper.class_, "__tablename__", None)
            if nombre:
                _MODELOS_POR_TABLA[nombre] = mapper.class_
    return _MODELOS_POR_TABLA.get(tabla)


def _org_del_registro(db: Session, tabla: str, registro_id: Any) -> Optional[int]:
    """Org del registro afectado, si `tabla` es una tabla real con `organizacion_id`.

    Casi siempre el registro ya está en la sesión (el endpoint lo acaba de tocar) y no hay
    query extra. Nunca rompe el log: ante cualquier problema devuelve None.
    """
    if not isinstance(registro_id, int) or registro_id <= 0:
        return None
    try:
        modelo = _modelo_de_tabla(tabla)
        if modelo is None:
            return None
        with db.no_autoflush:
            obj = db.get(modelo, registro_id)
            if obj is None:
                return None
            if tabla == "organizaciones":
                return obj.id
            org = getattr(obj, "organizacion_id", None)
        return org if isinstance(org, int) else None
    except Exception:  # noqa: BLE001 — el log de auditoría no puede tirar el request
        logger.debug("No se pudo resolver la org de %s#%s", tabla, registro_id, exc_info=True)
        return None


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
    autocommit: bool = True,
    organizacion_id: Optional[int] = None,
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
        organizacion_id: org de la acción. Si no se pasa: la org del registro afectado (si
            `tabla` es una tabla con `organizacion_id`) y si no, la org activa del request.
            Sin ninguna de las dos queda en NULL (el listado la filtra por la org del usuario).
    """
    if organizacion_id is None:
        organizacion_id = _org_del_registro(db, tabla, registro_id)
    if organizacion_id is None:
        organizacion_id = org_activa.get()
    log = AuditoriaLog(
        usuario_id=usuario_id,
        organizacion_id=organizacion_id,
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
