from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
import io

from app.database import get_db
from app.models.organizacion import Organizacion, CONFIG_DEFAULT
from app.models.user import User
from app.models.planilla import Planilla
from app.models.extracto import ExtractoBancario
from app.models.cliente import Cliente
from app.schemas.organizacion import OrganizacionCreate, OrganizacionUpdate, OrganizacionResponse
from app.middleware.auth import get_current_user, require_superadmin
from app.services.auditoria import registrar_log
from app.services.excel_export import export_backup_completo
from app.services.auth import get_password_hash

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


@router.get("/{org_id}/backup")
def backup_organizacion(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin)
):
    """Descarga backup Excel completo de una organización (planillas + extractos)."""
    org = db.query(Organizacion).filter(Organizacion.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organización no encontrada")

    # Planillas
    planillas_db = db.query(Planilla).filter(Planilla.organizacion_id == org_id).all()
    planillas = []
    for p in planillas_db:
        statuses = [r.status for r in p.rows]
        planillas.append({
            "id": p.id,
            "cliente_nombre": p.cliente.nombre,
            "nombre_archivo": p.nombre_archivo,
            "fecha_carga": p.fecha_carga,
            "usuario_nombre": p.usuario.full_name,
            "total_filas": len(statuses),
            "acreditadas": sum(1 for s in statuses if s == "ok"),
            "no_encontradas": sum(1 for s in statuses if s == "no está"),
            "duplicadas": sum(1 for s in statuses if s == "duplicado" or (isinstance(s, str) and s.startswith("acreditado"))),
            "sin_datos": sum(1 for s in statuses if s == "faltan datos"),
        })

    # Extractos
    extractos_db = db.query(ExtractoBancario).filter(ExtractoBancario.organizacion_id == org_id).all()
    extractos = [{"id": e.id, "nombre_archivo": e.nombre_archivo,
                  "fecha_creacion": e.fecha_creacion, "total_movimientos": len(e.movimientos)} for e in extractos_db]

    xlsx = export_backup_completo(org.nombre, planillas, extractos)
    fecha_str = datetime.now().strftime('%Y%m%d_%H%M')
    filename = f"backup_{org.nombre.replace(' ', '_')}_{fecha_str}.xlsx"

    return StreamingResponse(
        io.BytesIO(xlsx),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.post("/{org_id}/primer-usuario", status_code=status.HTTP_201_CREATED)
def crear_primer_usuario(
    org_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin)
):
    """Crea el primer usuario admin de una organización nueva."""
    from app.models.user import User as U, RoleEnum

    org = db.query(Organizacion).filter(Organizacion.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organización no encontrada")

    email = payload.get("email", "").strip()
    password = payload.get("password", "").strip()
    full_name = payload.get("full_name", "").strip()

    if not email or not password or not full_name:
        raise HTTPException(status_code=400, detail="email, password y full_name son requeridos")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 6 caracteres")
    if db.query(U).filter(U.email == email).first():
        raise HTTPException(status_code=400, detail="Ya existe un usuario con ese email")

    user = U(
        email=email,
        full_name=full_name,
        hashed_password=get_password_hash(password),
        role=RoleEnum.ADMIN.value,
        is_active=True,
        is_superadmin=False,
        organizacion_id=org_id
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    registrar_log(db, current_user.id, "users", user.id, "INSERT",
                  {"email": email, "org": org.nombre, "rol": "admin"})

    return {"ok": True, "user_id": user.id, "email": email, "organizacion": org.nombre}
