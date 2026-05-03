from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from sqlalchemy.orm import Session
import tempfile
import os

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
    """Obtiene la config de la org. Si no existe, retorna config default (Caneland)."""
    from app.services.conciliacion import CONFIG_CANELAND
    org = db.query(Organizacion).filter(Organizacion.id == organizacion_id).first()
    if org and org.configuracion:
        return org.configuracion
    return CONFIG_CANELAND


@router.post("/upload", response_model=PlanillaResponse)
async def upload_planilla(
    cliente_nombre: str = Query(..., description="Nombre del cliente"),
    extracto_id: int = Query(..., description="ID del extracto a usar"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("upload_files"))
):
    if not file.filename.endswith('.xlsx'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se aceptan archivos Excel (.xlsx)"
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

    cliente = db.query(Cliente).filter(
        Cliente.nombre == cliente_nombre,
        Cliente.organizacion_id == org_id
    ).first()
    if not cliente:
        cliente = Cliente(nombre=cliente_nombre, organizacion_id=org_id)
        db.add(cliente)
        db.flush()

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
            contents = await file.read()
            tmp.write(contents)
            tmp_path = tmp.name

        parsed = parsear_planilla_cliente(tmp_path)

        planilla = Planilla(
            cliente_id=cliente.id,
            extracto_id=extracto_id,
            usuario_id=current_user.id,
            nombre_archivo=file.filename,
            organizacion_id=org_id
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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al procesar planilla: {str(e)}"
        )
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@router.post("/{planilla_id}/conciliar", response_model=ConciliacionResultado)
def conciliar(
    planilla_id: int,
    fecha_acred: str = Query("hoy", description="Fecha de acreditación: 'hoy', 'ayer', o fecha ISO"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("reconcile"))
):
    planilla = db.query(Planilla).filter(Planilla.id == planilla_id).first()
    if not planilla:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Planilla no encontrada"
        )

    movimientos = db.query(ExtractoBancario).filter(
        ExtractoBancario.id == planilla.extracto_id
    ).first().movimientos

    org_id = planilla.organizacion_id or 1
    org_config = _get_org_config(db, org_id)

    try:
        resultado = conciliar_planilla(
            db=db,
            planilla_rows=planilla.rows,
            movimientos=movimientos,
            cliente_nombre=planilla.cliente.nombre,
            fecha_acred_str=fecha_acred,
            org_config=org_config
        )

        registrar_log(
            db=db,
            usuario_id=current_user.id,
            tabla="planillas",
            registro_id=planilla_id,
            accion="CONCILIAR",
            cambios=resultado
        )

        return {
            "planilla_id": planilla_id,
            **resultado
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en conciliación: {str(e)}"
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
    planilla = db.query(Planilla).filter(Planilla.id == planilla_id).first()
    if not planilla:
        raise HTTPException(status_code=404, detail="Planilla no encontrada")

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
    planilla = db.query(Planilla).filter(Planilla.id == planilla_id).first()
    if not planilla:
        raise HTTPException(status_code=404, detail="Planilla no encontrada")

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


# ── Endpoints existentes ──────────────────────────────────────────────────────

@router.get("/{planilla_id}/download")
def download_planilla_conciliada(
    planilla_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user)
):
    """Descarga xlsx con Hoja1=planilla+estado y Hoja2=movimientos acreditados"""
    import io
    from datetime import datetime
    from app.models.extracto import MovimientoBanco

    p = db.query(Planilla).filter(Planilla.id == planilla_id).first()
    if not p:
        raise HTTPException(404, "Planilla no encontrada")

    mov_ids = [r.orden_movimiento_acreditado for r in p.rows if r.orden_movimiento_acreditado]
    movs_map = {}
    if mov_ids:
        movs_map = {m.id: m for m in db.query(MovimientoBanco).filter(MovimientoBanco.id.in_(mov_ids)).all()}

    rows_data = []
    movimientos_acreditados = []
    ids_acred_vistos = set()

    for r in p.rows:
        mov = movs_map.get(r.orden_movimiento_acreditado) if r.orden_movimiento_acreditado else None
        rows_data.append({
            "monto": r.monto, "cuit": r.cuit, "titular": r.titular, "status": r.status,
            "orden_movimiento_acreditado": r.orden_movimiento_acreditado,
            "mov_titular": mov.titular if mov else None,
            "mov_fecha": mov.fecha if mov else None,
            "mov_fecha_acred": mov.fecha_acred if mov else None,
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
    nombre_base = p.nombre_archivo.replace('.xlsx', '').replace('.XLSX', '')
    fname = f"{nombre_base}_acreditado_{datetime.now().strftime('%d.%m')}.xlsx"
    return StreamingResponse(
        io.BytesIO(xlsx),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'}
    )


@router.delete("/{planilla_id}")
def delete_planilla(
    planilla_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Elimina una planilla y sus filas. Libera los movimientos bancarios que había acreditado."""
    planilla = db.query(Planilla).filter(Planilla.id == planilla_id).first()
    if not planilla:
        raise HTTPException(status_code=404, detail="Planilla no encontrada")

    from app.models.extracto import MovimientoBanco
    for row in planilla.rows:
        if row.orden_movimiento_acreditado:
            mov = db.query(MovimientoBanco).filter(
                MovimientoBanco.id == row.orden_movimiento_acreditado
            ).first()
            if mov and mov.cliente_acreditado == planilla.cliente.nombre:
                mov.cliente_acreditado = None
                mov.fecha_acred = None

    cliente = planilla.cliente.nombre
    nombre_archivo = planilla.nombre_archivo
    db.delete(planilla)
    db.commit()

    registrar_log(db, current_user.id, "planillas", planilla_id, "DELETE",
                  {"cliente": cliente, "archivo": nombre_archivo})
    return {"ok": True, "mensaje": f"Planilla #{planilla_id} eliminada y movimientos liberados"}


@router.get("/{planilla_id}/detalle", response_model=PlanillaDetalleResponse)
def get_planilla_detalle(
    planilla_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user)
):
    from app.models.extracto import MovimientoBanco

    p = db.query(Planilla).filter(Planilla.id == planilla_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Planilla no encontrada")

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
            "mov_fecha_acred": mov.fecha_acred if mov else None,
        })

    statuses = [r.status for r in p.rows]
    return {
        "id": p.id,
        "nombre_archivo": p.nombre_archivo,
        "cliente_nombre": p.cliente.nombre,
        "extracto_nombre": p.extracto.nombre_archivo,
        "fecha_carga": p.fecha_carga,
        "usuario_nombre": p.usuario.full_name,
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
    planilla = db.query(Planilla).filter(Planilla.id == planilla_id).first()
    if not planilla:
        raise HTTPException(status_code=404, detail="Planilla no encontrada")
    return planilla
