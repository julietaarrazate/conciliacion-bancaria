from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from typing import Optional
from datetime import datetime, timedelta
from collections import defaultdict

from app.database import get_db
from app.models.auditoria import AuditoriaLog
from app.models.planilla import Planilla, PlanillaRow
from app.models.cliente import Cliente
from app.models.user import User
from app.schemas.auditoria import AuditoriaListResponse, AuditoriaLogResponse
from app.middleware.auth import require_permission, get_current_user

router = APIRouter(prefix="/auditoria", tags=["auditoria"])


@router.get("", response_model=AuditoriaListResponse)
def list_auditoria(
    skip: int = 0,
    limit: int = 100,
    tabla: Optional[str] = Query(None),
    accion: Optional[str] = Query(None),
    usuario_id: Optional[int] = Query(None),
    desde: Optional[datetime] = Query(None),
    hasta: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("view_audit"))
):
    """
    Lista logs de auditoría con filtros opcionales.
    Requiere permiso 'view_audit' (admin o auditor).
    """
    q = db.query(AuditoriaLog)

    if tabla:
        q = q.filter(AuditoriaLog.tabla == tabla)
    if accion:
        q = q.filter(AuditoriaLog.accion == accion)
    if usuario_id is not None:
        q = q.filter(AuditoriaLog.usuario_id == usuario_id)
    if desde:
        q = q.filter(AuditoriaLog.timestamp >= desde)
    if hasta:
        q = q.filter(AuditoriaLog.timestamp <= hasta)

    total = q.count()

    rows = (
        q.order_by(desc(AuditoriaLog.timestamp))
        .offset(skip)
        .limit(limit)
        .all()
    )

    items = []
    for log in rows:
        items.append(
            AuditoriaLogResponse(
                id=log.id,
                usuario_id=log.usuario_id,
                usuario_nombre=log.usuario.full_name if log.usuario else None,
                usuario_email=log.usuario.email if log.usuario else None,
                tabla=log.tabla,
                registro_id=log.registro_id,
                accion=log.accion,
                cambios=log.cambios,
                timestamp=log.timestamp
            )
        )

    return {"total": total, "items": items}


@router.get("/insights")
def get_insights(
    dias: int = Query(30, description="Ventana de analisis en dias"),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Analiza el historial para producir estadísticas inteligentes:
    - Tasa de auto-conciliacion vs correcciones manuales
    - Clientes con mas 'faltan datos'
    - Montos mas problematicos
    - Patrones aprendidos de correcciones (base para futura IA)
    """
    desde = datetime.utcnow() - timedelta(days=dias)
    oid = org_id if current_user.is_superadmin and org_id else (current_user.organizacion_id or 1)

    # ── 1. Stats de conciliacion desde planilla_rows ──────────────────────
    planillas_org = db.query(Planilla).filter(
        Planilla.organizacion_id == oid,
        Planilla.fecha_carga >= desde
    ).all()

    total_filas = 0
    auto_ok = 0
    faltan_datos = 0
    no_encontradas = 0
    duplicadas = 0
    correcciones_manuales = 0

    clientes_problemas: dict = defaultdict(lambda: {"total": 0, "faltan": 0, "ok": 0})

    for p in planillas_org:
        nombre_cliente = p.cliente.nombre
        for r in p.rows:
            total_filas += 1
            clientes_problemas[nombre_cliente]["total"] += 1
            s = r.status
            if s == "ok":
                auto_ok += 1
                clientes_problemas[nombre_cliente]["ok"] += 1
            elif s and ("faltan datos" in s or "EN_REVISION" in s):
                faltan_datos += 1
                clientes_problemas[nombre_cliente]["faltan"] += 1
            elif s == "no está":
                no_encontradas += 1
            elif s == "duplicado" or (isinstance(s, str) and s.startswith("acreditado")):
                duplicadas += 1

    # ── 2. Correcciones manuales (UPDATE_STATUS en audit log) ─────────────
    correcciones = db.query(AuditoriaLog).filter(
        AuditoriaLog.accion == "UPDATE_STATUS",
        AuditoriaLog.timestamp >= desde
    ).all()
    correcciones_manuales = len(correcciones)

    # Patrones de correcciones: que se cambio y desde que estado
    patrones_correccion: dict = defaultdict(int)
    for c in correcciones:
        if c.cambios:
            antes = c.cambios.get("antes", "?")
            despues = c.cambios.get("despues", "?")
            patrones_correccion[f"{antes} → {despues}"] += 1

    # ── 3. Clientes mas problematicos ─────────────────────────────────────
    ranking_problemas = sorted(
        [
            {
                "cliente": k,
                "total": v["total"],
                "faltan": v["faltan"],
                "ok": v["ok"],
                "pct_problema": round(v["faltan"] / v["total"] * 100, 1) if v["total"] > 0 else 0
            }
            for k, v in clientes_problemas.items()
            if v["faltan"] > 0
        ],
        key=lambda x: x["pct_problema"],
        reverse=True
    )[:10]

    # ── 4. Actividad reciente (logs ultimos N dias) ───────────────────────
    actividad = db.query(
        AuditoriaLog.accion,
        func.count(AuditoriaLog.id).label("cantidad")
    ).filter(
        AuditoriaLog.timestamp >= desde
    ).group_by(AuditoriaLog.accion).all()

    actividad_dict = {a.accion: a.cantidad for a in actividad}

    tasa_auto = round(auto_ok / total_filas * 100, 1) if total_filas > 0 else 0

    return {
        "periodo_dias": dias,
        "resumen": {
            "total_filas_procesadas": total_filas,
            "auto_conciliadas": auto_ok,
            "correcciones_manuales": correcciones_manuales,
            "faltan_datos": faltan_datos,
            "no_encontradas": no_encontradas,
            "duplicadas": duplicadas,
            "tasa_auto_conciliacion": tasa_auto,
        },
        "clientes_problematicos": ranking_problemas,
        "patrones_correcciones": dict(patrones_correccion),
        "actividad_por_accion": actividad_dict,
        "aprendizaje": {
            "descripcion": "Cada corrección manual entrena al sistema. Con más correcciones, el match mejora automáticamente.",
            "total_correcciones_historicas": db.query(AuditoriaLog).filter(AuditoriaLog.accion == "UPDATE_STATUS").count(),
            "patrones_frecuentes": [
                {"patron": k, "veces": v}
                for k, v in sorted(patrones_correccion.items(), key=lambda x: x[1], reverse=True)[:5]
            ]
        }
    }
