from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models.organizacion import Organizacion, CONFIG_DEFAULT
from app.models.user import User
from app.schemas.organizacion import OrganizacionCreate, OrganizacionUpdate, OrganizacionResponse
from app.middleware.auth import get_current_user, require_superadmin
from app.services.auditoria import registrar_log

router = APIRouter(prefix="/admin/organizaciones", tags=["organizaciones"])


@router.get("", response_model=List[OrganizacionResponse])
def list_organizaciones(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin)
):
    return db.query(Organizacion).order_by(Organizacion.id).all()


@router.post("", response_model=OrganizacionResponse, status_code=status.HTTP_201_CREATED)
def create_organizacion(
    payload: OrganizacionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin)
):
    existing = db.query(Organizacion).filter(Organizacion.nombre == payload.nombre).first()
    if existing:
        raise HTTPException(status_code=400, detail="Ya existe una organización con ese nombre")

    config = payload.configuracion or CONFIG_DEFAULT.copy()
    org = Organizacion(
        nombre=payload.nombre,
        plan=payload.plan,
        configuracion=config,
        activo=payload.activo
    )
    db.add(org)
    db.commit()
    db.refresh(org)

    registrar_log(db, current_user.id, "organizaciones", org.id, "INSERT",
                  {"nombre": org.nombre, "plan": org.plan})
    return org


@router.put("/{org_id}", response_model=OrganizacionResponse)
def update_organizacion(
    org_id: int,
    payload: OrganizacionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin)
):
    org = db.query(Organizacion).filter(Organizacion.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organización no encontrada")

    antes = {"nombre": org.nombre, "plan": org.plan, "activo": org.activo}

    if payload.nombre is not None:
        org.nombre = payload.nombre
    if payload.plan is not None:
        org.plan = payload.plan
    if payload.configuracion is not None:
        org.configuracion = payload.configuracion
    if payload.activo is not None:
        org.activo = payload.activo

    db.commit()
    db.refresh(org)

    registrar_log(db, current_user.id, "organizaciones", org.id, "UPDATE",
                  {"antes": antes, "despues": {"nombre": org.nombre, "plan": org.plan, "activo": org.activo}})
    return org


@router.get("/{org_id}", response_model=OrganizacionResponse)
def get_organizacion(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin)
):
    org = db.query(Organizacion).filter(Organizacion.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organización no encontrada")
    return org
