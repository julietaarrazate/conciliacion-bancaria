"""Grilla de vencimientos impositivos por organización + calendario (ver services/vencimientos.py)."""
import re
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import require_permission
from app.models.user import User
from app.models.vencimientos import IMPUESTOS, CalendarioVencimiento, VencimientoMarcado
from app.services import vencimientos as svc
from app.services.acceso_orgs import orgs_accesibles, puede_org
from app.services.auditoria import registrar_log
from app.services.tz import hoy_art

router = APIRouter(prefix="/vencimientos", tags=["vencimientos"])

_RE_MES = r"^\d{4}-(0[1-9]|1[0-2])$"


def _validar_mes(mes: str) -> str:
    if not re.fullmatch(_RE_MES, mes or ""):
        raise HTTPException(422, "El mes debe tener formato AAAA-MM")
    return mes


@router.get("/grilla")
def get_grilla(
    mes: str = Query(..., description="Mes de vencimiento AAAA-MM"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("view_accounting")),
):
    """Obligaciones que vencen en `mes` para cada organización que ve el usuario."""
    mes = _validar_mes(mes)
    hoy = hoy_art()
    return {
        "mes": mes,
        "hoy": hoy,
        "impuestos": IMPUESTOS,
        "filas": svc.grilla(db, orgs_accesibles(db, current_user), mes, hoy),
    }


class BloqueIn(BaseModel):
    terminacion_desde: int = Field(ge=0, le=9)
    terminacion_hasta: int = Field(ge=0, le=9)
    fecha: date


class CalendarioIn(BaseModel):
    impuesto: str
    periodo: str = Field(pattern=_RE_MES)
    fuente: Optional[str] = None
    fechas: List[BloqueIn]


def _calendario_dict(c: CalendarioVencimiento) -> dict:
    return {"impuesto": c.impuesto, "periodo": c.periodo, "terminacion_desde": c.terminacion_desde,
            "terminacion_hasta": c.terminacion_hasta, "fecha": c.fecha, "fuente": c.fuente}


@router.get("/calendario")
def get_calendario(
    periodo: Optional[str] = Query(None, description="Período fiscal AAAA-MM"),
    anio: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("view_accounting")),
):
    q = db.query(CalendarioVencimiento)
    if periodo:
        q = q.filter(CalendarioVencimiento.periodo == _validar_mes(periodo))
    elif anio:
        q = q.filter(CalendarioVencimiento.periodo.like(f"{anio:04d}-%"))
    filas = q.order_by(CalendarioVencimiento.periodo, CalendarioVencimiento.impuesto,
                       CalendarioVencimiento.terminacion_desde).all()
    return [_calendario_dict(c) for c in filas]


@router.put("/calendario")
def put_calendario(
    body: CalendarioIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin_accounting")),
):
    """Carga (o reemplaza) las fechas de un impuesto y período. Es general para
    todas las organizaciones, por eso solo lo puede hacer el superadmin."""
    if not current_user.is_superadmin:
        raise HTTPException(403, "Solo el superadmin carga el calendario (vale para todas las organizaciones)")
    try:
        filas = svc.guardar_calendario(db, body.impuesto, body.periodo,
                                       [b.model_dump() for b in body.fechas], body.fuente, current_user.id)
    except svc.CalendarioInvalido as ex:
        raise HTTPException(422, str(ex))
    registrar_log(db, current_user.id, "calendario_vencimientos", 0, "CARGAR",
                  {"impuesto": body.impuesto, "periodo": body.periodo, "bloques": len(filas)})
    db.commit()
    return [_calendario_dict(c) for c in filas]


class MarcaIn(BaseModel):
    organizacion_id: int
    impuesto: str
    periodo: str = Field(pattern=_RE_MES)


def _validar_marca(body: MarcaIn, user: User) -> None:
    if body.impuesto not in IMPUESTOS:
        raise HTTPException(422, f"Impuesto desconocido: {body.impuesto}")
    if not puede_org(user, body.organizacion_id):
        raise HTTPException(403, "Sin acceso a esa organización")


@router.post("/marcar")
def marcar_presentado(
    body: MarcaIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage_finance")),
):
    """Marca una obligación como presentada/pagada (lo que no registra ningún módulo)."""
    _validar_marca(body, current_user)
    existe = db.query(VencimientoMarcado).filter_by(organizacion_id=body.organizacion_id,
                                                    impuesto=body.impuesto, periodo=body.periodo).first()
    if not existe:
        db.add(VencimientoMarcado(organizacion_id=body.organizacion_id, impuesto=body.impuesto,
                                  periodo=body.periodo, marcado_por=current_user.id))
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
        registrar_log(db, current_user.id, "vencimientos_marcados", body.organizacion_id, "MARCAR",
                      {"impuesto": body.impuesto, "periodo": body.periodo})
    db.commit()
    return {"ok": True}


@router.delete("/marcar")
def desmarcar_presentado(
    body: MarcaIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage_finance")),
):
    _validar_marca(body, current_user)
    n = db.query(VencimientoMarcado).filter_by(organizacion_id=body.organizacion_id,
                                               impuesto=body.impuesto, periodo=body.periodo).delete()
    if n:
        registrar_log(db, current_user.id, "vencimientos_marcados", body.organizacion_id, "DESMARCAR",
                      {"impuesto": body.impuesto, "periodo": body.periodo})
    db.commit()
    return {"ok": True, "borradas": n}
