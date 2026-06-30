from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload, selectinload
from typing import List
from datetime import datetime
import io
from app.services.tz import now_art

from app.database import get_db
from app.models.organizacion import Organizacion, CONFIG_DEFAULT
from app.models.user import User
from app.models.planilla import Planilla
from app.models.extracto import ExtractoBancario
from app.schemas.organizacion import OrganizacionCreate, OrganizacionUpdate, OrganizacionResponse
from app.middleware.auth import require_superadmin
from app.services.auditoria import registrar_log
from app.services.excel_export import export_backup_completo
from app.services.auth import get_password_hash
from app.services.backup_service import export_org_backup

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

    # Sembrar plan de cuentas + reglas + categorías para la nueva org, así puede
    # llevar contabilidad (asientos automáticos) desde el primer movimiento.
    try:
        from app.services.seed_contable import seed_contabilidad_org, seed_categorias_egreso_org
        from app.services.monotributo_service import seed_monotributo_categorias
        seed_contabilidad_org(db, org.id)
        seed_categorias_egreso_org(db, org.id)
        seed_monotributo_categorias(db, org.id)
    except Exception as ex:
        db.rollback()
        import logging
        logging.getLogger(__name__).warning("No se pudo sembrar contabilidad para org %s: %s", org.id, ex)

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

    # Planillas (eager: cliente, usuario y rows en pocas queries)
    planillas_db = (
        db.query(Planilla)
        .options(
            joinedload(Planilla.cliente),
            joinedload(Planilla.usuario),
            selectinload(Planilla.rows),
        )
        .filter(Planilla.organizacion_id == org_id, Planilla.deleted_at.is_(None))
        .all()
    )
    planillas = []
    for p in planillas_db:
        statuses = [r.status for r in p.rows]
        planillas.append({
            "id": p.id,
            "cliente_nombre": p.cliente.nombre if p.cliente else None,
            "nombre_archivo": p.nombre_archivo,
            "fecha_carga": p.fecha_carga,
            "usuario_nombre": p.usuario.full_name if p.usuario else None,
            "total_filas": len(statuses),
            "acreditadas": sum(1 for s in statuses if s == "ok"),
            "no_encontradas": sum(1 for s in statuses if s == "no está"),
            "duplicadas": sum(1 for s in statuses if s == "duplicado" or (isinstance(s, str) and s.startswith("acreditado"))),
            "sin_datos": sum(1 for s in statuses if s == "faltan datos"),
        })

    # Extractos (eager: movimientos para el count)
    extractos_db = (
        db.query(ExtractoBancario)
        .options(selectinload(ExtractoBancario.movimientos))
        .filter(ExtractoBancario.organizacion_id == org_id, ExtractoBancario.deleted_at.is_(None))
        .all()
    )
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


@router.get("/{org_id}/backup-completo")
def backup_completo_json(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin)
):
    """Descarga backup JSON COMPLETO de la organización.

    Incluye TODO: extractos, planillas, cheques, pagos, gastos, caja,
    liquidaciones, contabilidad (asientos), auditoría, patrones IA.
    Las contraseñas NO se incluyen. Es la fuente de verdad para restore.
    """
    import json
    org = db.query(Organizacion).filter(Organizacion.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organización no encontrada")

    data = export_org_backup(db, org_id)
    payload = json.dumps(data, ensure_ascii=False, indent=2, default=str)

    registrar_log(db, current_user.id, "organizaciones", org_id, "BACKUP_JSON",
                  {"resumen": data["resumen"]})

    fecha_str = datetime.now().strftime('%Y%m%d_%H%M')
    filename = f"backup_completo_{org.nombre.replace(' ', '_')}_{fecha_str}.json"
    return StreamingResponse(
        io.BytesIO(payload.encode("utf-8")),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/backup-completo-todo")
def backup_completo_todas_las_orgs(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin)
):
    """Descarga backup JSON de TODAS las organizaciones en un solo archivo.
    Solo para superadmin (Julieta). Útil antes de cambios grandes en el sistema."""
    import json
    orgs = db.query(Organizacion).all()
    todo = {
        "exportado_at": datetime.now().isoformat(),
        "total_orgs": len(orgs),
        "organizaciones": [export_org_backup(db, o.id) for o in orgs],
    }
    payload = json.dumps(todo, ensure_ascii=False, indent=2, default=str)

    fecha_str = datetime.now().strftime('%Y%m%d_%H%M')
    filename = f"backup_sistema_completo_{fecha_str}.json"
    return StreamingResponse(
        io.BytesIO(payload.encode("utf-8")),
        media_type="application/json",
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


@router.get("/actividad")
def panel_actividad(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin)
):
    """
    Panel de actividad por org para superadmin.
    Muestra estado actual de cada org: ultima conciliacion, planillas del mes,
    tasa de exito, casos pendientes, usuarios activos.
    """
    from datetime import timedelta
    from sqlalchemy import func
    from app.models.planilla import Planilla
    from app.models.user import User as U

    orgs = db.query(Organizacion).filter(Organizacion.activo == True).all()
    hoy = now_art()
    inicio_mes = hoy.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    hoy - timedelta(days=7)

    resultado = []
    for org in orgs:
        # Planillas del mes (eager: rows para los counts, evita N+1)
        planillas_mes = (
            db.query(Planilla)
            .options(selectinload(Planilla.rows))
            .filter(
                Planilla.organizacion_id == org.id,
                Planilla.deleted_at.is_(None),
                Planilla.fecha_carga >= inicio_mes,
            )
            .all()
        )

        # Stats de filas del mes
        filas_mes = []
        for p in planillas_mes:
            filas_mes.extend(p.rows)

        total_filas = len(filas_mes)
        ok = sum(1 for r in filas_mes if r.status == "ok")
        sin_datos = sum(1 for r in filas_mes if "faltan" in str(r.status) or "sin datos" in str(r.status))
        en_revision = sum(1 for r in filas_mes if r.status == "EN_REVISION")

        # Ultima conciliacion
        ultima_planilla = db.query(Planilla).filter(
            Planilla.organizacion_id == org.id,
            Planilla.deleted_at.is_(None),
        ).order_by(Planilla.fecha_carga.desc()).first()

        # Usuarios de la org
        usuarios = db.query(U).filter(
            U.organizacion_id == org.id,
            U.is_active == True,
            U.is_superadmin == False
        ).count()

        # Clientes activos (con planillas en los ultimos 30 dias)
        clientes_activos = db.query(func.count(func.distinct(Planilla.cliente_id))).filter(
            Planilla.organizacion_id == org.id,
            Planilla.fecha_carga >= hoy - timedelta(days=30)
        ).scalar() or 0

        tasa = round(ok / total_filas * 100, 1) if total_filas > 0 else None

        resultado.append({
            "id": org.id,
            "nombre": org.nombre,
            "plan": org.plan,
            "planillas_mes": len(planillas_mes),
            "filas_mes": total_filas,
            "ok_mes": ok,
            "sin_datos_mes": sin_datos,
            "en_revision_mes": en_revision,
            "tasa_exito": tasa,
            "ultima_conciliacion": ultima_planilla.fecha_carga.isoformat() if ultima_planilla else None,
            "usuarios_activos": usuarios,
            "clientes_activos": clientes_activos,
            "alerta": en_revision > 0 or (tasa is not None and tasa < 70),
        })

    # Ordenar: alertas primero, luego por actividad
    resultado.sort(key=lambda x: (-int(x["alerta"]), -(x["planillas_mes"])))
    return resultado
