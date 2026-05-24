"""Papelera de reciclaje — listar y restaurar registros soft-deleted.

Solo accesible para superadmin. Por ahora soporta:
- extractos_bancarios
- planillas

Para purgar definitivamente (borrar de verdad), usar el endpoint /purgar.
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models.extracto import ExtractoBancario, MovimientoBanco
from app.models.planilla import Planilla, PlanillaRow
from app.models.user import User
from app.middleware.auth import require_superadmin
from app.services.auditoria import registrar_log

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/papelera", tags=["papelera"])


@router.get("")
def listar_papelera(
    org_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    """Lista todos los registros borrados (soft) agrupados por tipo."""
    extractos_q = db.query(ExtractoBancario).filter(ExtractoBancario.deleted_at.isnot(None))
    planillas_q = db.query(Planilla).filter(Planilla.deleted_at.isnot(None))
    if org_id:
        extractos_q = extractos_q.filter(ExtractoBancario.organizacion_id == org_id)
        planillas_q = planillas_q.filter(Planilla.organizacion_id == org_id)

    extractos = [{
        "id": e.id,
        "tipo": "extracto",
        "nombre": e.nombre_archivo,
        "organizacion_id": e.organizacion_id,
        "fecha_creacion": e.fecha_creacion.isoformat() if e.fecha_creacion else None,
        "deleted_at": e.deleted_at.isoformat() if e.deleted_at else None,
        "movimientos": db.query(MovimientoBanco).filter(MovimientoBanco.extracto_id == e.id).count(),
    } for e in extractos_q.order_by(desc(ExtractoBancario.deleted_at)).all()]

    planillas = [{
        "id": p.id,
        "tipo": "planilla",
        "cliente_nombre": p.cliente.nombre if p.cliente else None,
        "nombre_archivo": p.nombre_archivo,
        "organizacion_id": p.organizacion_id,
        "fecha_carga": p.fecha_carga.isoformat() if p.fecha_carga else None,
        "deleted_at": p.deleted_at.isoformat() if p.deleted_at else None,
        "filas": db.query(PlanillaRow).filter(PlanillaRow.planilla_id == p.id).count(),
    } for p in planillas_q.order_by(desc(Planilla.deleted_at)).all()]

    return {
        "extractos": extractos,
        "planillas": planillas,
        "total": len(extractos) + len(planillas),
    }


@router.post("/restaurar/{tipo}/{registro_id}")
def restaurar(
    tipo: str,
    registro_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    """Restaura un registro de la papelera. tipo: 'extracto' o 'planilla'."""
    if tipo == "extracto":
        item = db.query(ExtractoBancario).filter(
            ExtractoBancario.id == registro_id,
            ExtractoBancario.deleted_at.isnot(None),
        ).first()
        if not item:
            raise HTTPException(404, "Extracto no encontrado en papelera")
        item.deleted_at = None
        db.commit()
        registrar_log(db, current_user.id, "extractos_bancarios", registro_id,
                      "RESTORE", {"nombre": item.nombre_archivo})
        return {"ok": True, "tipo": "extracto", "id": registro_id, "restaurado": True}

    if tipo == "planilla":
        item = db.query(Planilla).filter(
            Planilla.id == registro_id,
            Planilla.deleted_at.isnot(None),
        ).first()
        if not item:
            raise HTTPException(404, "Planilla no encontrada en papelera")
        item.deleted_at = None
        db.commit()
        registrar_log(db, current_user.id, "planillas", registro_id,
                      "RESTORE", {"archivo": item.nombre_archivo})
        return {"ok": True, "tipo": "planilla", "id": registro_id, "restaurado": True}

    raise HTTPException(400, "Tipo invalido. Usar 'extracto' o 'planilla'.")


@router.delete("/purgar/{tipo}/{registro_id}")
def purgar(
    tipo: str,
    registro_id: int,
    confirmar: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    """Borra DEFINITIVAMENTE un registro de la papelera. No se puede deshacer.
    Requiere query param confirmar='BORRAR' para evitar accidentes."""
    if confirmar != "BORRAR":
        raise HTTPException(400, "Para purgar requiere ?confirmar=BORRAR en la URL")

    if tipo == "extracto":
        item = db.query(ExtractoBancario).filter(
            ExtractoBancario.id == registro_id,
            ExtractoBancario.deleted_at.isnot(None),
        ).first()
        if not item:
            raise HTTPException(404, "Extracto no encontrado en papelera")
        nombre = item.nombre_archivo
        # Desligar planillas y rows
        db.query(Planilla).filter(Planilla.extracto_id == registro_id)\
          .update({"extracto_id": None}, synchronize_session="fetch")
        ids_movs = [m.id for m in item.movimientos]
        if ids_movs:
            db.query(PlanillaRow).filter(
                PlanillaRow.orden_movimiento_acreditado.in_(ids_movs)
            ).update({"orden_movimiento_acreditado": None}, synchronize_session="fetch")
        db.flush()
        db.query(MovimientoBanco).filter(
            MovimientoBanco.extracto_id == registro_id
        ).delete(synchronize_session=False)
        db.delete(item)
        db.commit()
        registrar_log(db, current_user.id, "extractos_bancarios", registro_id,
                      "PURGE", {"nombre": nombre})
        return {"ok": True, "purgado": True}

    if tipo == "planilla":
        item = db.query(Planilla).filter(
            Planilla.id == registro_id,
            Planilla.deleted_at.isnot(None),
        ).first()
        if not item:
            raise HTTPException(404, "Planilla no encontrada en papelera")
        nombre = item.nombre_archivo
        db.delete(item)
        db.commit()
        registrar_log(db, current_user.id, "planillas", registro_id,
                      "PURGE", {"archivo": nombre})
        return {"ok": True, "purgado": True}

    raise HTTPException(400, "Tipo invalido. Usar 'extracto' o 'planilla'.")
