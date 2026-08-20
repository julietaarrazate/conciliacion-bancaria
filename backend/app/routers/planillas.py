import hashlib
import logging
import json
from datetime import datetime as _dt_now
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query, Request
from sqlalchemy import func, cast, String, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address
import os

logger = logging.getLogger(__name__)

from app.database import get_db
from app.models.planilla import Planilla, PlanillaRow
from app.models.cliente import Cliente
from app.models.extracto import ExtractoBancario
from app.models.user import User
from app.models.organizacion import Organizacion
from fastapi.responses import StreamingResponse
from app.schemas.planilla import PlanillaResponse, PlanillaDetalleResponse, ConciliacionResultado
from app.services.planilla_mapper import estandarizar_planilla
from app.services.conciliacion import conciliar_planilla, diagnostico_conciliacion
from app.services.auditoria import registrar_log
from app.services.excel_export import export_planilla_conciliada
from app.services.tz import hoy_art
from app.middleware.auth import get_current_user, require_permission, can_switch_org

router = APIRouter(prefix="/planillas", tags=["planillas"])
limiter = Limiter(key_func=get_remote_address)


def _get_org_config(db: Session, organizacion_id: int) -> dict:
    """Obtiene la config de la org. Si no existe, retorna config default."""
    from app.services.conciliacion import CONFIG_DEFAULT_ORG
    org = db.query(Organizacion).filter(Organizacion.id == organizacion_id).first()
    if org and org.configuracion:
        return org.configuracion
    return CONFIG_DEFAULT_ORG


def _motivo(e: Exception, limite: int = 240) -> str:
    """Motivo corto y seguro de una excepción, para mostrar en pantalla.

    Estos endpoints son de staff autenticado (superadmin/admin) y hoy devuelven
    un mensaje genérico que esconde la causa real — imposible de diagnosticar sin
    los logs de Render. Incluir el tipo + mensaje (truncado) hace que el error se
    vea en la UI y sea accionable. No expone secretos (son errores de parseo/DB)."""
    detalle = str(e).strip().replace("\n", " ")
    if len(detalle) > limite:
        detalle = detalle[:limite] + "…"
    return f"{type(e).__name__}: {detalle}" if detalle else type(e).__name__


def _planilla_for_user(db: Session, planilla_id: int, current_user: User,
                       include_deleted: bool = False) -> Planilla:
    """Resuelve una planilla con aislamiento multi-tenant.
    Superadmin ve cualquier org; el resto solo la propia. 404 si no existe o es de otra org."""
    q = db.query(Planilla).filter(Planilla.id == planilla_id)
    if not include_deleted:
        q = q.filter(Planilla.deleted_at.is_(None))
    if not current_user.is_superadmin:
        q = q.filter(Planilla.organizacion_id == current_user.organizacion_id)
    p = q.first()
    if not p:
        raise HTTPException(404, "Planilla no encontrada")
    return p


def _cliente_para_org(db: Session, cliente_id: int, org_id: int,
                      current_user: User) -> Cliente:
    """Resuelve un cliente con aislamiento multi-tenant. 404 si no existe o es de
    otra org (salvo superadmin)."""
    q = db.query(Cliente).filter(Cliente.id == cliente_id)
    if not current_user.is_superadmin:
        q = q.filter(Cliente.organizacion_id == org_id)
    cli = q.first()
    if not cli:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return cli


@router.post("/preview")
@limiter.limit("30/minute")
async def preview_planilla(
    request: Request,
    cliente_id: Optional[int] = Query(None, description="Cliente para reusar su perfil aprendido"),
    cliente_nombre: Optional[str] = Query(None, description="Alternativa a cliente_id: resuelve el cliente por nombre en la org"),
    org_id: Optional[int] = Query(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("upload_files")),
):
    """Estandariza una planilla y devuelve el ResultadoMapeo SIN persistir nada.
    Usa el perfil aprendido del cliente si el fingerprint coincide."""
    ext = os.path.splitext(file.filename or '')[1].lower()
    if ext not in ('.xlsx', '.xls', '.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formatos aceptados: .xlsx, .xls, .csv"
        )

    org_id = org_id if (org_id and can_switch_org(current_user, org_id)) else (current_user.organizacion_id or 1)

    mapeo_perfil = None
    if cliente_id:
        cliente = _cliente_para_org(db, cliente_id, org_id, current_user)
        mapeo_perfil = cliente.mapeo_planilla
    elif cliente_nombre:
        # El Dashboard identifica al cliente por nombre; resolvemos su perfil (mismo
        # org). Si no existe todavía, no pasa nada → cae a heurística.
        cli = db.query(Cliente).filter(
            Cliente.nombre.ilike(cliente_nombre.strip()),
            Cliente.organizacion_id == org_id,
        ).first()
        mapeo_perfil = cli.mapeo_planilla if cli else None

    contents = await file.read()
    try:
        resultado = estandarizar_planilla(contents, mapeo=mapeo_perfil)
    except Exception as e:
        logger.exception("preview error")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se pudo leer la planilla ({_motivo(e)})."
        )

    return {
        "origen": resultado["origen"],
        "confianza": resultado["confianza"],
        "header_row": resultado["header_row"],
        "columnas": resultado["columnas"],
        "columnas_disponibles": resultado["columnas_disponibles"],
        "preview": resultado["preview"],
        "fingerprint": resultado["fingerprint"],
        "filas_totales": resultado["filas_totales"],
        "filas_descartadas": resultado["filas_descartadas"],
        "total_movimientos": resultado["total_movimientos"],
        "total_declarado": resultado["total_declarado"],
        "total_cuadra": resultado["total_cuadra"],
        "filas_resumen": resultado["filas_resumen"],
        "deteccion": {
            "origen": resultado["origen"],
            "confianza": resultado["confianza"],
            "filas_totales": resultado["filas_totales"],
            "filas_descartadas": resultado["filas_descartadas"],
            "total_movimientos": resultado["total_movimientos"],
            "total_declarado": resultado["total_declarado"],
            "total_cuadra": resultado["total_cuadra"],
            "filas_resumen": resultado["filas_resumen"],
        },
    }


@router.post("/upload", response_model=PlanillaResponse)
@limiter.limit("20/minute")
async def upload_planilla(
    request: Request,
    cliente_nombre: str = Query(..., description="Nombre del cliente"),
    extracto_id: int = Query(..., description="ID del extracto a usar"),
    org_id: Optional[int] = Query(None),
    file: UploadFile = File(...),
    mapeo: Optional[str] = Form(None, description="JSON con {header_row, columnas} — corrección manual del usuario"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("upload_files"))
):
    ext = os.path.splitext(file.filename or '')[1].lower()
    if ext not in ('.xlsx', '.xls', '.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formatos aceptados: .xlsx, .xls, .csv"
        )

    # Misma org activa que el extracto elegido (no la home org del usuario):
    # ver fix análogo en extractos.py upload_extracto.
    org_id = org_id if (org_id and can_switch_org(current_user, org_id)) else (current_user.organizacion_id or 1)

    extracto = db.query(ExtractoBancario).filter(
        ExtractoBancario.id == extracto_id,
        ExtractoBancario.organizacion_id == org_id,
    ).first()
    if not extracto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Extracto bancario no encontrado"
        )

    # Normalize: first letter uppercase, preserve rest
    cliente_nombre = cliente_nombre[:1].upper() + cliente_nombre[1:] if cliente_nombre else cliente_nombre

    cliente = db.query(Cliente).filter(
        Cliente.nombre.ilike(cliente_nombre),
        Cliente.organizacion_id == org_id
    ).first()
    if not cliente:
        cliente = Cliente(nombre=cliente_nombre, organizacion_id=org_id)
        db.add(cliente)
        db.flush()
    else:
        # Use canonical name from DB (avoids writing "green" when DB has "Green")
        cliente_nombre = cliente.nombre

    try:
        contents = await file.read()

        # Bloquea re-subir la MISMA planilla (mismo contenido de archivo) para el
        # mismo cliente mientras la anterior siga activa (no borrada). Evita el
        # duplicado clásico: el contador reenvía el archivo (para corregir algo
        # que se hace en el paso de conciliar, como el % de comisión) y termina
        # con dos planillas idénticas conciliadas contra el mismo extracto.
        fingerprint = hashlib.sha1(contents).hexdigest()
        existente = db.query(Planilla).filter(
            Planilla.cliente_id == cliente.id,
            Planilla.organizacion_id == org_id,
            Planilla.fingerprint == fingerprint,
            Planilla.deleted_at.is_(None),
        ).first()
        if existente:
            fecha_s = existente.fecha_carga.strftime('%d/%m %H:%M') if existente.fecha_carga else '?'
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Esta planilla ya fue cargada para {cliente_nombre} el {fecha_s} "
                    f"(planilla #{existente.id}, archivo \"{existente.nombre_archivo}\"). "
                    "Si necesitás cambiar el % de comisión, no hace falta volver a subir el "
                    "archivo: buscá la planilla en Conciliaciones/Historial y re-conciliala con "
                    "el % correcto. Si de verdad es una carga distinta, borrá primero la anterior."
                )
            )

        # Elegir el mapeo: 1) corrección manual del usuario (form `mapeo`);
        # 2) perfil aprendido del cliente. Sin ninguno → pipeline heurística/IA.
        mapeo_manual = None
        if mapeo:
            try:
                mapeo_manual = json.loads(mapeo)
            except (ValueError, TypeError):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El campo 'mapeo' no es un JSON válido."
                )
        mapeo_arg = mapeo_manual if mapeo_manual is not None else cliente.mapeo_planilla

        resultado = estandarizar_planilla(contents, mapeo=mapeo_arg)

        planilla = Planilla(
            cliente_id=cliente.id,
            extracto_id=extracto_id,
            usuario_id=current_user.id,
            nombre_archivo=file.filename,
            organizacion_id=org_id,
            porcentaje_comision=None,
            total_declarado=resultado.get("total_declarado"),
            fingerprint=fingerprint,
        )
        db.add(planilla)
        try:
            db.flush()
        except IntegrityError:
            # Carrera: dos requests concurrentes con el mismo archivo pasaron el
            # chequeo de arriba a la vez. El índice único parcial (migración 026)
            # es la garantía real; esto solo da un mensaje claro en vez de un 500.
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Esta planilla ya fue cargada para {cliente_nombre}."
            )

        for fila_data in resultado["filas"]:
            fila = PlanillaRow(
                planilla_id=planilla.id,
                monto=fila_data.get("monto"),
                cuit=fila_data.get("cuit"),
                titular=fila_data.get("titular"),
                referencia=fila_data.get("referencia"),
                fecha=fila_data.get("fecha"),  # fecha de pago declarada (para diagnóstico de período)
                status="pendiente",
                organizacion_id=org_id
            )
            db.add(fila)

        # Aprender el perfil cuando el usuario corrigió el mapeo manualmente.
        if mapeo_manual is not None:
            cliente.mapeo_planilla = {
                "fingerprint": resultado["fingerprint"],
                "header_row": resultado["header_row"],
                "columnas": resultado["columnas"],
                "actualizado": _dt_now.utcnow().isoformat(),
            }

        db.commit()
        db.refresh(planilla)

        registrar_log(
            db=db,
            usuario_id=current_user.id,
            tabla="planillas",
            registro_id=planilla.id,
            accion="INSERT",
            cambios={
                "cliente": cliente_nombre,
                "extracto_id": extracto_id,
                "filas": len(resultado["filas"]),
                "organizacion_id": org_id,
                "origen_deteccion": resultado["origen"],
            }
        )

        planilla.deteccion = {
            "origen": resultado["origen"],
            "confianza": resultado["confianza"],
            "filas_totales": resultado["filas_totales"],
            "filas_descartadas": resultado["filas_descartadas"],
            "total_movimientos": resultado["total_movimientos"],
            "total_declarado": resultado["total_declarado"],
            "total_cuadra": resultado["total_cuadra"],
            "filas_resumen": resultado["filas_resumen"],
        }
        return planilla

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.exception("upload error")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al procesar la planilla ({_motivo(e)})."
        )


@router.post("/{planilla_id}/conciliar", response_model=ConciliacionResultado)
@limiter.limit("30/minute")
def conciliar(
    request: Request,
    planilla_id: int,
    fecha_acred: str = Query("hoy", description="Fecha de acreditación: 'hoy', 'ayer', o fecha ISO"),
    solo_pendientes: bool = Query(False, description="Si True, solo re-procesa filas no-ok (preserva correcciones manuales)"),
    comision_pct: float = Query(0.0, description="Porcentaje de comisión sobre el total acreditado (ej: 1.5 = 1.5%)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("reconcile"))
):
    planilla = _planilla_for_user(db, planilla_id, current_user)

    # Si la planilla no tiene extracto (fue borrado), usar el más reciente de la org
    if not planilla.extracto_id:
        extracto = (
            db.query(ExtractoBancario)
            .filter(ExtractoBancario.organizacion_id == (planilla.organizacion_id or 1))
            .order_by(ExtractoBancario.fecha_creacion.desc())
            .first()
        )
        if not extracto:
            raise HTTPException(status_code=400, detail="No hay extractos cargados para esta organización. Cargá un extracto primero.")
        # Re-vincular la planilla al extracto activo
        planilla.extracto_id = extracto.id
        db.flush()
    else:
        extracto = db.query(ExtractoBancario).filter(ExtractoBancario.id == planilla.extracto_id).first()
        if not extracto:
            # extracto_id apunta a algo borrado → buscar el más reciente
            extracto = (
                db.query(ExtractoBancario)
                .filter(ExtractoBancario.organizacion_id == (planilla.organizacion_id or 1))
                .order_by(ExtractoBancario.fecha_creacion.desc())
                .first()
            )
            if not extracto:
                raise HTTPException(status_code=400, detail="El extracto ya no existe y no hay otros cargados.")
            planilla.extracto_id = extracto.id
            db.flush()

    movimientos = extracto.movimientos

    org_id = planilla.organizacion_id or 1
    org_config = _get_org_config(db, org_id)

    try:
        resultado = conciliar_planilla(
            db=db,
            planilla_rows=planilla.rows,
            movimientos=movimientos,
            cliente_nombre=planilla.cliente.nombre,
            fecha_acred_str=fecha_acred,
            org_config=org_config,
            org_id=org_id,
            solo_pendientes=solo_pendientes,
            cliente_id=planilla.cliente_id,
        )

        # Save commission %: explicit param only (no fallback to client default)
        if comision_pct > 0:
            planilla.porcentaje_comision = Decimal(str(comision_pct))
            db.flush()

        registrar_log(
            db=db,
            usuario_id=current_user.id,
            tabla="planillas",
            registro_id=planilla_id,
            accion="CONCILIAR",
            cambios=resultado
        )

        # La planilla NO genera asiento propio: la reclasificación ya la maneja
        # um_reclass (No identificado D / Cliente X H con cuentas hoja correctas).
        # registrar_planilla() usaba cuentas madre y duplicaba con um_reclass.

        # Diagnóstico read-only (aditivo): calculado DESPUÉS de conciliar para
        # explicar en la UI por qué pueden quedar filas sin conciliar. No altera
        # el flujo de conciliación ni los status.
        diagnostico = diagnostico_conciliacion(planilla.rows, movimientos)

        return {
            "planilla_id": planilla_id,
            **resultado,
            "diagnostico": diagnostico,
        }

    except Exception as e:
        db.rollback()
        logger.exception("conciliar error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en la conciliación ({_motivo(e)}). Revisá los datos e intentá de nuevo."
        )


# ── Cola de revisión manual ───────────────────────────────────────────────────

@router.get("/{planilla_id}/revision")
def get_revision(
    planilla_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lista filas EN_REVISION de la planilla.
    Solo disponible para orgs con requiere_cierre_periodo: true.
    """
    planilla = _planilla_for_user(db, planilla_id, current_user)
    org_id = planilla.organizacion_id or 1
    org_config = _get_org_config(db, org_id)

    if not org_config.get("requiere_cierre_periodo", False):
        raise HTTPException(
            status_code=400,
            detail="Esta organización no tiene habilitada la cola de revisión"
        )

    filas_revision = [r for r in planilla.rows if r.status == "EN_REVISION"]
    return {
        "planilla_id": planilla_id,
        "total_en_revision": len(filas_revision),
        "filas": [
            {
                "id": r.id,
                "monto": r.monto,
                "cuit": r.cuit,
                "titular": r.titular,
                "referencia": r.referencia,
                "comentario_revision": r.comentario_revision,
            }
            for r in filas_revision
        ]
    }


@router.post("/{planilla_id}/revision/{row_id}/resolver")
def resolver_revision(
    planilla_id: int,
    row_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Resuelve una fila EN_REVISION.
    Body: {"accion": "aprobar|rechazar|pago_parcial", "comentario": "..."}
    """
    planilla = _planilla_for_user(db, planilla_id, current_user)
    org_id = planilla.organizacion_id or 1
    org_config = _get_org_config(db, org_id)

    if not org_config.get("requiere_cierre_periodo", False):
        raise HTTPException(
            status_code=400,
            detail="Esta organización no tiene habilitada la cola de revisión"
        )

    row = db.query(PlanillaRow).filter(
        PlanillaRow.id == row_id,
        PlanillaRow.planilla_id == planilla_id
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Fila no encontrada")

    if row.status != "EN_REVISION":
        raise HTTPException(status_code=400, detail="La fila no está en estado EN_REVISION")

    accion = payload.get("accion", "")
    comentario = payload.get("comentario", "")

    if accion == "aprobar":
        row.status = "ok"
    elif accion == "rechazar":
        row.status = "no está"
    elif accion == "pago_parcial":
        row.status = "PAGO_PARCIAL"
        row.monto_acreditado = payload.get("monto_acreditado")
    elif accion == "diferencia":
        row.status = "CONCILIADO_CON_DIFERENCIA"
        row.monto_acreditado = payload.get("monto_acreditado")
    elif accion == "vencido":
        row.status = "VENCIDO"
    else:
        raise HTTPException(
            status_code=400,
            detail="Acción inválida. Use: aprobar, rechazar, pago_parcial, diferencia, vencido"
        )

    row.comentario_revision = comentario
    db.commit()

    registrar_log(
        db=db,
        usuario_id=current_user.id,
        tabla="planilla_rows",
        registro_id=row.id,
        accion="RESOLVER_REVISION",
        cambios={"accion": accion, "comentario": comentario, "nuevo_status": row.status}
    )

    return {"ok": True, "row_id": row_id, "nuevo_status": row.status}


# ── Editar estado de una fila ────────────────────────────────────────────────

@router.patch("/rows/{row_id}")
def patch_row_status(
    row_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Modifica el estado de una fila de planilla manualmente.
    Útil cuando se obtienen más datos después de la conciliación.
    Body: {status: string, comentario?: string}
    """
    row = db.query(PlanillaRow).filter(PlanillaRow.id == row_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Fila no encontrada")
    # Validacion multi-tenant: la planilla padre debe ser de la org del usuario
    planilla = _planilla_for_user(db, row.planilla_id, current_user, include_deleted=True)

    # Inmutabilidad: no permitir cambios en filas de periodos cerrados
    from app.services.cierre_periodo import periodo_esta_cerrado
    fecha_check = row.fecha_acred or (planilla.fecha_carga.date() if planilla.fecha_carga else None)
    if periodo_esta_cerrado(db, planilla.organizacion_id or 1, fecha_check):
        raise HTTPException(409, "El periodo ya está cerrado — esta fila no se puede modificar")

    status_anterior = row.status
    nuevo_status = payload.get("status", "").strip()
    if not nuevo_status:
        raise HTTPException(status_code=400, detail="El campo status es requerido")

    row.status = nuevo_status
    if "comentario" in payload:
        row.comentario_revision = payload["comentario"]
    # Guardar fecha_acred directamente en la fila (independiente del movimiento)
    if "fecha_acred" in payload and payload["fecha_acred"]:
        from datetime import date as _date
        try:
            row.fecha_acred = _date.fromisoformat(payload["fecha_acred"])
        except Exception:
            pass
    elif nuevo_status in ("no está", "duplicado", "faltan datos", "pendiente"):
        row.fecha_acred = None

    # ── Aprendizaje: registrar toda correccion manual para alimentar IA ──
    if status_anterior != nuevo_status and row.orden_movimiento_acreditado:
        try:
            from app.services.aprendizaje import registrar_correccion
            planilla = db.query(Planilla).filter(Planilla.id == row.planilla_id).first()
            if planilla:
                registrar_correccion(
                    db=db,
                    row=row,
                    cliente_nombre=planilla.cliente.nombre,
                    org_id=planilla.organizacion_id or 1
                )
        except Exception:
            pass

    # Sync con el movimiento vinculado en el extracto
    if row.orden_movimiento_acreditado:
        from app.models.extracto import MovimientoBanco as MB
        from datetime import date as date_type, datetime
        from zoneinfo import ZoneInfo
        mov = db.query(MB).filter(MB.id == row.orden_movimiento_acreditado).first()
        if mov:
            if nuevo_status == "ok":
                # Acreditar en el extracto
                planilla = db.query(Planilla).filter(Planilla.id == row.planilla_id).first()
                if planilla and planilla.cliente:
                    mov.cliente_acreditado = planilla.cliente.nombre
                if "fecha_acred" in payload:
                    try:
                        mov.fecha_acred = date_type.fromisoformat(payload["fecha_acred"])
                    except Exception:
                        pass
                elif not mov.fecha_acred:
                    mov.fecha_acred = datetime.now(ZoneInfo('America/Argentina/Buenos_Aires')).date()
            elif nuevo_status in ("no está", "duplicado", "faltan datos", "pendiente"):
                # Desacreditar en el extracto solo si este row era el que lo acreditó
                if mov.cliente_acreditado:
                    mov.cliente_acreditado = None
                    mov.fecha_acred = None
            elif "fecha_acred" in payload:
                try:
                    mov.fecha_acred = date_type.fromisoformat(payload["fecha_acred"])
                except Exception:
                    pass

    db.commit()

    registrar_log(
        db=db,
        usuario_id=current_user.id,
        tabla="planilla_rows",
        registro_id=row.id,
        accion="UPDATE_STATUS",
        cambios={"antes": status_anterior, "despues": nuevo_status,
                 "comentario": payload.get("comentario")}
    )

    return {"ok": True, "row_id": row_id, "status": row.status}


@router.delete("/rows/{row_id}")
def delete_row(
    row_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("delete_records"))
):
    row = db.query(PlanillaRow).filter(PlanillaRow.id == row_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Fila no encontrada")
    # Validacion multi-tenant
    planilla = _planilla_for_user(db, row.planilla_id, current_user, include_deleted=True)
    # Inmutabilidad de periodo cerrado
    from app.services.cierre_periodo import periodo_esta_cerrado
    fecha_check = row.fecha_acred or (planilla.fecha_carga.date() if planilla.fecha_carga else None)
    if periodo_esta_cerrado(db, planilla.organizacion_id or 1, fecha_check):
        raise HTTPException(409, "El periodo ya está cerrado — esta fila no se puede borrar")

    registrar_log(
        db=db,
        usuario_id=current_user.id,
        tabla="planilla_rows",
        registro_id=row.id,
        accion="DELETE_ROW",
        cambios={"monto": str(row.monto or 0), "status": row.status, "titular": row.titular}
    )

    db.delete(row)
    db.commit()
    return {"ok": True, "row_id": row_id}


# ── Endpoints existentes ──────────────────────────────────────────────────────

def _build_planilla_export_data(db: Session, p: Planilla) -> tuple[dict, list, object]:
    """Arma la data de export (Excel y PDF comparten exactamente el mismo contenido).

    Devuelve (planilla_data, movimientos_acreditados, fecha_ref) donde fecha_ref
    es la fecha de acreditación más reciente (o hoy si no hay ninguna), usada
    para el nombre de archivo.
    """
    from app.models.extracto import MovimientoBanco

    mov_ids = [r.orden_movimiento_acreditado for r in p.rows if r.orden_movimiento_acreditado]
    movs_map = {}
    if mov_ids:
        movs_map = {m.id: m for m in db.query(MovimientoBanco).filter(MovimientoBanco.id.in_(mov_ids)).all()}

    # Fallback: filas "ok" sin FK → buscar por monto + cliente en el extracto
    fallback_map: dict = {}
    ok_sin_link = [r for r in p.rows if r.status == "ok" and not r.orden_movimiento_acreditado]
    if ok_sin_link and p.extracto_id:
        ya_usados = set(movs_map.keys())
        candidatos = (
            db.query(MovimientoBanco)
            .filter(
                MovimientoBanco.extracto_id == p.extracto_id,
                MovimientoBanco.cliente_acreditado == p.cliente.nombre,
            )
            .order_by(MovimientoBanco.orden)
            .all()
        )
        for c in candidatos:
            if c.id not in ya_usados:
                key = float(c.monto) if c.monto is not None else None
                if key is not None and key not in fallback_map:
                    fallback_map[key] = c
                    ya_usados.add(c.id)

    rows_data = []
    movimientos_acreditados = []
    ids_acred_vistos = set()

    for r in p.rows:
        mov = movs_map.get(r.orden_movimiento_acreditado) if r.orden_movimiento_acreditado else None
        if mov is None and r.status == "ok":
            monto_key = float(r.monto) if r.monto is not None else None
            mov = fallback_map.get(monto_key) if monto_key is not None else None
        fecha_acred_fallback = r.fecha_acred
        rows_data.append({
            "monto": r.monto, "cuit": r.cuit, "titular": r.titular, "status": r.status,
            "orden_movimiento_acreditado": mov.orden if mov else None,
            "mov_titular": mov.titular if mov else None,
            "mov_fecha": mov.fecha if mov else None,
            "mov_fecha_acred": (mov.fecha_acred if mov else None) or fecha_acred_fallback,
        })
        if mov and mov.id not in ids_acred_vistos:
            ids_acred_vistos.add(mov.id)
            movimientos_acreditados.append({
                "orden": mov.orden, "fecha": mov.fecha, "mes": mov.mes,
                "titular": mov.titular, "monto": mov.monto, "saldo": mov.saldo,
                "cliente_acreditado": mov.cliente_acreditado, "fecha_acred": mov.fecha_acred,
            })

    planilla_data = {
        "cliente_nombre": p.cliente.nombre,
        "nombre_archivo": p.nombre_archivo,
        "rows": rows_data,
        "total_declarado": p.total_declarado,
    }

    fechas_acred = [mov.fecha_acred for mov in movs_map.values() if mov.fecha_acred]
    fecha_ref = max(fechas_acred) if fechas_acred else hoy_art()

    return planilla_data, movimientos_acreditados, fecha_ref


@router.get("/{planilla_id}/download")
def download_planilla_conciliada(
    planilla_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Descarga xlsx con Hoja1=planilla+estado y Hoja2=movimientos acreditados"""
    import io

    p = _planilla_for_user(db, planilla_id, current_user, include_deleted=True)
    planilla_data, movimientos_acreditados, fecha_ref = _build_planilla_export_data(db, p)

    xlsx = export_planilla_conciliada(planilla_data, movimientos_acreditados)

    # Nombre: "{cliente} acreditado {d.m}.xlsx" — ej "alojando acreditado 8.5.xlsx"
    # Fecha = la mas reciente de las acreditaciones; si no hay, fecha de hoy
    fecha_str = f"{fecha_ref.day}.{fecha_ref.month}"
    cliente_slug = (p.cliente.nombre or "cliente").strip().lower()
    fname = f"{cliente_slug} acreditado {fecha_str}.xlsx"
    return StreamingResponse(
        io.BytesIO(xlsx),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'}
    )


@router.get("/{planilla_id}/export-pdf")
def export_planilla_conciliada_pdf_endpoint(
    planilla_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Descarga PDF con la misma data que el Excel de /download: título, detalle
    de filas y bloque de totales/cuadre (incluyendo total declarado si existe)."""
    import io
    from app.services.pdf_export import export_planilla_conciliada_pdf

    p = _planilla_for_user(db, planilla_id, current_user, include_deleted=True)
    planilla_data, _movimientos_acreditados, fecha_ref = _build_planilla_export_data(db, p)

    pdf = export_planilla_conciliada_pdf(planilla_data, generado_por=current_user.full_name or current_user.email)

    cliente_slug = (p.cliente.nombre or "cliente").strip().lower().replace(" ", "_")
    fname = f"planilla_{cliente_slug}_{fecha_ref.strftime('%Y-%m-%d')}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'}
    )


@router.put("/{planilla_id}/comision")
def actualizar_comision_planilla(
    planilla_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Setea o borra el % de comisión propio de esta planilla para liquidaciones."""
    planilla = _planilla_for_user(db, planilla_id, current_user)
    pct_raw = payload.get("porcentaje_comision")
    if pct_raw is None or pct_raw == "":
        planilla.porcentaje_comision = None
    else:
        try:
            pct = Decimal(str(pct_raw))
            if pct < 0 or pct > 100:
                raise HTTPException(400, "Porcentaje debe ser entre 0 y 100")
            planilla.porcentaje_comision = pct
        except Exception:
            raise HTTPException(400, "Porcentaje inválido")
    db.commit()
    return {
        "id": planilla.id,
        "porcentaje_comision": float(planilla.porcentaje_comision) if planilla.porcentaje_comision is not None else None,
    }


@router.delete("/{planilla_id}")
def delete_planilla(
    planilla_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("delete_records"))
):
    """Soft delete: marca la planilla como eliminada (deleted_at = now()).
    Las filas y acreditaciones se conservan, así si se restaura vuelve completa."""
    from datetime import datetime as _dt
    planilla = _planilla_for_user(db, planilla_id, current_user)

    planilla.deleted_at = _dt.utcnow()
    db.commit()

    registrar_log(db, current_user.id, "planillas", planilla_id, "SOFT_DELETE",
                  {"cliente": planilla.cliente.nombre if planilla.cliente else None,
                   "archivo": planilla.nombre_archivo})
    return {
        "ok": True,
        "mensaje": f"Planilla #{planilla_id} enviada a papelera. Restaurable desde /admin/papelera.",
        "soft_deleted": True,
    }


@router.get("/{planilla_id}/detalle", response_model=PlanillaDetalleResponse)
def get_planilla_detalle(
    planilla_id: int,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    status: Optional[str] = None,
    importe: Optional[str] = None,
    cuit: Optional[str] = None,
    titular: Optional[str] = None,
    mov_titular: Optional[str] = None,
    mov_fecha: Optional[str] = None,
    mov_fecha_acred: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from app.models.extracto import MovimientoBanco

    p = _planilla_for_user(db, planilla_id, current_user, include_deleted=True)

    # Stats from ALL rows (unfiltered) — single GROUP BY query
    stats_rows = (
        db.query(PlanillaRow.status, func.count(PlanillaRow.id))
        .filter(PlanillaRow.planilla_id == p.id)
        .group_by(PlanillaRow.status)
        .all()
    )
    stats: dict[str, int] = {s: c for s, c in stats_rows}
    total = sum(stats.values())
    acreditadas = stats.get("ok", 0)
    no_encontradas = stats.get("no está", 0)
    sin_datos = stats.get("faltan datos", 0)
    duplicadas = sum(c for s, c in stats.items() if s == "duplicado" or (isinstance(s, str) and s.startswith("acreditado")))

    # Filtered query
    rows_q = db.query(PlanillaRow).filter(PlanillaRow.planilla_id == p.id)

    if status:
        rows_q = rows_q.filter(PlanillaRow.status == status)
    if cuit:
        rows_q = rows_q.filter(PlanillaRow.cuit.ilike(f"%{cuit}%"))
    if titular:
        rows_q = rows_q.filter(PlanillaRow.titular.ilike(f"%{titular}%"))
    if importe:
        importe_clean = importe.replace(".", "").replace(",", ".")
        rows_q = rows_q.filter(cast(PlanillaRow.monto, String).contains(importe_clean))
    if mov_titular:
        matching = db.query(MovimientoBanco.id).filter(
            MovimientoBanco.titular.ilike(f"%{mov_titular}%")
        ).subquery()
        rows_q = rows_q.filter(PlanillaRow.orden_movimiento_acreditado.in_(matching))
    if mov_fecha:
        matching = db.query(MovimientoBanco.id).filter(
            cast(MovimientoBanco.fecha, String).contains(mov_fecha)
        ).subquery()
        rows_q = rows_q.filter(PlanillaRow.orden_movimiento_acreditado.in_(matching))
    if mov_fecha_acred:
        matching_mov = db.query(MovimientoBanco.id).filter(
            cast(MovimientoBanco.fecha_acred, String).contains(mov_fecha_acred)
        ).subquery()
        rows_q = rows_q.filter(or_(
            cast(PlanillaRow.fecha_acred, String).contains(mov_fecha_acred),
            PlanillaRow.orden_movimiento_acreditado.in_(matching_mov)
        ))

    total_filtered = rows_q.count()
    fetched_rows = rows_q.order_by(PlanillaRow.id).offset(offset).limit(limit).all()

    # Enrich with movement data
    mov_ids = [r.orden_movimiento_acreditado for r in fetched_rows if r.orden_movimiento_acreditado]
    movs_map: dict[int, MovimientoBanco] = {}
    if mov_ids:
        movs = db.query(MovimientoBanco).filter(MovimientoBanco.id.in_(mov_ids)).all()
        movs_map = {m.id: m for m in movs}

    rows_enriched = []
    for r in fetched_rows:
        mov = movs_map.get(r.orden_movimiento_acreditado) if r.orden_movimiento_acreditado else None
        rows_enriched.append({
            "id": r.id,
            "monto": r.monto,
            "cuit": r.cuit,
            "titular": r.titular,
            "status": r.status,
            "orden_movimiento_acreditado": r.orden_movimiento_acreditado,
            "mov_titular": mov.titular if mov else None,
            "mov_fecha": mov.fecha if mov else None,
            "mov_fecha_acred": (mov.fecha_acred if mov else None) or r.fecha_acred,
        })

    return {
        "id": p.id,
        "nombre_archivo": p.nombre_archivo,
        "cliente_nombre": p.cliente.nombre if p.cliente else "—",
        "extracto_nombre": p.extracto.nombre_archivo if p.extracto else "Sin extracto",
        "fecha_carga": p.fecha_carga,
        "usuario_nombre": p.usuario.full_name if p.usuario else "—",
        "rows": rows_enriched,
        "total": total,
        "total_filtered": total_filtered,
        "acreditadas": acreditadas,
        "no_encontradas": no_encontradas,
        "duplicadas": duplicadas,
        "sin_datos": sin_datos,
    }


@router.get("/{planilla_id}", response_model=PlanillaResponse)
def get_planilla(
    planilla_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return _planilla_for_user(db, planilla_id, current_user, include_deleted=True)
