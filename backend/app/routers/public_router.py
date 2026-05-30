"""Endpoints públicos (sin autenticación) — estado de cuenta compartido."""
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload, joinedload
from jose import jwt as jose_jwt, JWTError

from app.config import get_settings
from app.database import get_db
from app.models.cliente import Cliente
from app.models.planilla import Planilla, PlanillaRow
from app.models.cheque import Cheque
from app.models.egreso import Egreso

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/public", tags=["public"])


@router.get("/cliente/{token}")
def estado_cuenta_publico(token: str, db: Session = Depends(get_db)):
    """Estado de cuenta de un cliente — link compartido, no requiere autenticación."""
    settings = get_settings()
    try:
        payload = jose_jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError:
        raise HTTPException(status_code=401, detail="Link inválido o expirado")
    if payload.get("type") != "share_cliente":
        raise HTTPException(status_code=401, detail="Token inválido")

    client_id = payload.get("client_id")
    org_id = payload.get("org_id")
    cliente = db.query(Cliente).filter(Cliente.id == client_id, Cliente.organizacion_id == org_id).first()
    if not cliente:
        raise HTTPException(404, "Cliente no encontrado")

    planillas = (
        db.query(Planilla)
        .options(selectinload(Planilla.rows))
        .filter(Planilla.cliente_id == client_id, Planilla.deleted_at.is_(None))
        .order_by(Planilla.fecha_carga.desc())
        .limit(10)
        .all()
    )
    cheques = (
        db.query(Cheque)
        .filter(Cheque.organizacion_id == org_id, Cheque.cliente_id == client_id)
        .order_by(Cheque.fecha_deposito.desc())
        .limit(20)
        .all()
    )
    pagos = (
        db.query(Egreso)
        .filter(
            Egreso.organizacion_id == org_id,
            Egreso.cliente_id == client_id,
            Egreso.tipo == "pago_cliente",
        )
        .order_by(Egreso.fecha.desc())
        .limit(20)
        .all()
    )

    return {
        "cliente_nombre": cliente.nombre,
        "cliente_cuit": cliente.cuit,
        "planillas": [
            {
                "id": p.id,
                "nombre_archivo": p.nombre_archivo,
                "fecha_carga": str(p.fecha_carga)[:10] if p.fecha_carga else None,
                "total": len(p.rows),
                "acreditadas": sum(1 for r in p.rows if r.status in ('ok', 'OK', 'PAGO_PARCIAL')),
                "rows": [
                    {"monto": r.monto or 0, "titular": r.titular, "status": r.status}
                    for r in p.rows
                ],
            }
            for p in planillas
        ],
        "cheques": [
            {
                "numero": c.numero,
                "monto": c.monto or 0,
                "estado": c.estado,
                "fecha_deposito": str(c.fecha_deposito) if c.fecha_deposito else None,
            }
            for c in cheques
        ],
        "pagos": [
            {
                "monto": p.monto or 0,
                "fecha": str(p.fecha) if p.fecha else None,
                "descripcion": p.concepto,
            }
            for p in pagos
        ],
    }
