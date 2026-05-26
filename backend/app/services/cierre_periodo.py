"""Helpers para validar inmutabilidad de períodos cerrados.

Una vez que se ejecuta POST /liquidaciones/periodos/cerrar para una org,
los registros financieros con fecha dentro del período cerrado quedan
inmutables: no se pueden editar status, borrar, ni modificar montos.

El cierre aplica solo a organizaciones con requiere_cierre_periodo=true
en su configuración (Caneland tiene false → no le afecta).
"""
from datetime import date
from typing import Optional
from sqlalchemy.orm import Session
from app.models.liquidacion import CierrePeriodo
from app.models.organizacion import Organizacion


def _org_requiere_cierre(db: Session, org_id: int) -> bool:
    org = db.query(Organizacion).filter(Organizacion.id == org_id).first()
    if not org or not org.configuracion:
        return False
    return bool(org.configuracion.get("requiere_cierre_periodo", False))


def periodo_esta_cerrado(db: Session, org_id: int, fecha: Optional[date]) -> bool:
    """True si la fecha cae dentro de un periodo cerrado de la org.
    Si la fecha es None o la org no requiere cierre, retorna False (pasa)."""
    if not fecha or not _org_requiere_cierre(db, org_id):
        return False
    existe = (
        db.query(CierrePeriodo)
        .filter(
            CierrePeriodo.organizacion_id == org_id,
            CierrePeriodo.periodo_inicio <= fecha,
            CierrePeriodo.periodo_fin >= fecha,
        )
        .first()
    )
    return existe is not None
