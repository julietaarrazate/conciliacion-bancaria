import logging
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from sqlalchemy.orm import Session
import tempfile
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
from app.services.excel_parser import parsear_planilla_cliente
from app.services.conciliacion import conciliar_planilla
from app.services.auditoria import registrar_log
from app.services.excel_export import export_planilla_conciliada
from app.middleware.auth import get_current_user, require_permission

router = APIRouter(prefix="/planillas", tags=["planillas"])


def _get_org_config(db: Session, organizacion_id: int) -> dict:
    """Obtiene la config de la org. Si no existe, retorna config default."""
    from app.services.conciliacion import CONFIG_DEFAULT_ORG
    org = db.query(Organizacion).filter(Organizacion.id == organizacion_id).first()
    if org and org.configuracion:
        return org.configuracion
    return CONFIG_DEFAULT_ORG


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


@router.post("/upload", response_model=PlanillaResponse)
async def upload_planilla(
    cliente_nombre: str = Query(..., description="Nombre del cliente"),
    extracto_id: int = Query(..., description="ID del extracto a usar"),
    file: UploadFile = File(...),
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

    extracto = db.query(ExtractoBancario).filter(
        ExtractoBancario.id == extracto_id
    ).first()
    if not extracto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Extracto bancario no encontrado"
        )

    org_id = current_user.organizacion_id or 1

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
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            contents = await file.read()
            tmp.write(contents)
            tmp_path = tmp.name

        parsed = parsear_planilla_cliente(tmp_path)

        planilla = Planilla(
            cliente_id=cliente.id,
            extracto_id=extracto_id,
            usuario_id=current_user.id,
            nombre_archivo=file.filename,
            organizacion_id=org_id,
            porcentaje_comision=cliente.porcentaje_comision if cliente.porcentaje_comision else None,
        )
        db.add(planilla)
        db.flush()

        for fila_data in parsed["filas"]:
            fila = PlanillaRow(
                planilla_id=planilla.id,
                monto=fila_data.get("monto"),
                cuit=fila_data.get("cuit"),
                titular=fila_data.get("titular"),
                referencia=fila_data.get("referencia"),
                status="pendiente",
                organizacion_id=org_id
            )
            db.add(fila)

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
                "filas": len(parsed["filas"]),
                "organizacion_id": org_id
            }
        )

        return planilla

    except Exception as e:
        db.rollback()
        logger.error("upload error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Error al procesar la planilla. Verificá el formato del archivo."
        )
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@router.post("/{planilla_id}/conciliar", response_model=ConciliacionResultado)
def conciliar(
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

        # Save commission %: explicit param > existing planilla % > client's default %
        if comision_pct > 0:
            planilla.porcentaje_comision = Decimal(str(comision_pct))
            db.flush()
        elif planilla.porcentaje_comision is None and planilla.cliente and planilla.cliente.porcentaje_comision:
            planilla.porcentaje_comision = planilla.cliente.porcentaje_comision
            db.flush()

        registrar_log(
            db=db,
            usuario_id=current_user.id,
            tabla="planillas",
            registro_id=planilla_id,
            accion="CONCILIAR",
            cambios=resultado
        )

        # Motor contable — asiento automático (fault-tolerant)
        try:
            from app.services.motor_contable import registrar_planilla
            from datetime import datetime as _dt, timedelta as _td
            from zoneinfo import ZoneInfo as _ZI
            _ARG = _ZI('America/Argentina/Buenos_Aires')
            if fecha_acred.lower() == 'hoy':
                _fecha = _dt.now(_ARG).date()
            elif fecha_acred.lower() == 'ayer':
                _fecha = (_dt.now(_ARG) - _td(days=1)).date()
            else:
                try:
                    _fecha = _dt.fromisoformat(fecha_acred).date()
                except Exception:
                    _fecha = _dt.now(_ARG).date()
            registrar_planilla(
                db=db,
                planilla_id=planilla_id,
                org_id=org_id,
                usuario_id=current_user.id,
                cliente_nombre=planilla.cliente.nombre if planilla.cliente else "",
                nombre_archivo=planilla.nombre_archivo or "",
                rows=planilla.rows,
                fecha_acred=_fecha,
                solo_pendientes=solo_pendientes,
                comision_pct=Decimal(str(comision_pct)),
            )
        except Exception as _mc_ex:
            logger.warning("motor_contable planilla: %s", _mc_ex)

        return {
            "planilla_id": planilla_id,
            **resultado
        }

    except Exception as e:
        db.rollback()
        logger.error("conciliar error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error en la conciliación. Revisá los datos e intentá de nuevo."
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
    current_user: User = Depends(get_current_user)
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

@router.get("/{planilla_id}/download")
def download_planilla_conciliada(
    planilla_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Descarga xlsx con Hoja1=planilla+estado y Hoja2=movimientos acreditados"""
    import io
    from datetime import datetime
    from app.models.extracto import MovimientoBanco

    p = _planilla_for_user(db, planilla_id, current_user, include_deleted=True)

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
    }

    xlsx = export_planilla_conciliada(planilla_data, movimientos_acreditados)

    # Nombre: "{cliente} acreditado {d.m}.xlsx" — ej "alojando acreditado 8.5.xlsx"
    # Fecha = la mas reciente de las acreditaciones; si no hay, fecha de hoy
    fechas_acred = [mov.fecha_acred for mov in movs_map.values() if mov.fecha_acred]
    fecha_ref = max(fechas_acred) if fechas_acred else datetime.now().date()
    fecha_str = f"{fecha_ref.day}.{fecha_ref.month}"
    cliente_slug = (p.cliente.nombre or "cliente").strip().lower()
    fname = f"{cliente_slug} acreditado {fecha_str}.xlsx"
    return StreamingResponse(
        io.BytesIO(xlsx),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
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
    current_user: User = Depends(get_current_user)
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from app.models.extracto import MovimientoBanco

    p = _planilla_for_user(db, planilla_id, current_user, include_deleted=True)

    mov_ids = [r.orden_movimiento_acreditado for r in p.rows if r.orden_movimiento_acreditado]
    movs_map = {}
    if mov_ids:
        movs = db.query(MovimientoBanco).filter(MovimientoBanco.id.in_(mov_ids)).all()
        movs_map = {m.id: m for m in movs}

    rows_enriched = []
    for r in p.rows:
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

    statuses = [r.status for r in p.rows]
    return {
        "id": p.id,
        "nombre_archivo": p.nombre_archivo,
        "cliente_nombre": p.cliente.nombre if p.cliente else "—",
        "extracto_nombre": p.extracto.nombre_archivo if p.extracto else "Sin extracto",
        "fecha_carga": p.fecha_carga,
        "usuario_nombre": p.usuario.full_name if p.usuario else "—",
        "rows": rows_enriched,
        "total": len(statuses),
        "acreditadas": sum(1 for s in statuses if s == "ok"),
        "no_encontradas": sum(1 for s in statuses if s == "no está"),
        "duplicadas": sum(1 for s in statuses if s == "duplicado" or (isinstance(s, str) and s.startswith("acreditado"))),
        "sin_datos": sum(1 for s in statuses if s == "faltan datos"),
    }


@router.get("/{planilla_id}", response_model=PlanillaResponse)
def get_planilla(
    planilla_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return _planilla_for_user(db, planilla_id, current_user, include_deleted=True)
