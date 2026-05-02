from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from sqlalchemy.orm import Session
import tempfile
import os

from app.database import get_db
from app.models.planilla import Planilla, PlanillaRow
from app.models.cliente import Cliente
from app.models.extracto import ExtractoBancario
from app.models.user import User
from app.schemas.planilla import PlanillaResponse, PlanillaDetalleResponse, ConciliacionResultado
from app.services.excel_parser import parsear_planilla_cliente
from app.services.conciliacion import conciliar_planilla
from app.services.auditoria import registrar_log
from app.middleware.auth import get_current_user, require_permission

router = APIRouter(prefix="/planillas", tags=["planillas"])

@router.post("/upload", response_model=PlanillaResponse)
async def upload_planilla(
    cliente_nombre: str = Query(..., description="Nombre del cliente"),
    extracto_id: int = Query(..., description="ID del extracto a usar"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("upload_files"))
):
    """
    Carga una planilla de cliente y la prepara para conciliación.
    Requiere que ya exista un extracto bancario.
    """

    # Validar tipo de archivo
    if not file.filename.endswith('.xlsx'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se aceptan archivos Excel (.xlsx)"
        )

    # Verificar que el extracto existe
    extracto = db.query(ExtractoBancario).filter(
        ExtractoBancario.id == extracto_id
    ).first()
    if not extracto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Extracto bancario no encontrado"
        )

    # Obtener o crear cliente
    cliente = db.query(Cliente).filter(
        Cliente.nombre == cliente_nombre
    ).first()
    if not cliente:
        cliente = Cliente(nombre=cliente_nombre)
        db.add(cliente)
        db.flush()

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
            contents = await file.read()
            tmp.write(contents)
            tmp_path = tmp.name

        # Parsear el archivo
        parsed = parsear_planilla_cliente(tmp_path)

        # Crear planilla en BD
        planilla = Planilla(
            cliente_id=cliente.id,
            extracto_id=extracto_id,
            usuario_id=current_user.id,
            nombre_archivo=file.filename
        )
        db.add(planilla)
        db.flush()

        # Crear filas de planilla
        for fila_data in parsed["filas"]:
            fila = PlanillaRow(
                planilla_id=planilla.id,
                monto=fila_data.get("monto"),
                cuit=fila_data.get("cuit"),
                titular=fila_data.get("titular"),
                status="pendiente"
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
                "filas": len(parsed["filas"])
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
    """
    Ejecuta la conciliación de una planilla contra los movimientos bancarios.
    """

    # Obtener planilla
    planilla = db.query(Planilla).filter(Planilla.id == planilla_id).first()
    if not planilla:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Planilla no encontrada"
        )

    # Obtener movimientos del extracto
    movimientos = db.query(ExtractoBancario).filter(
        ExtractoBancario.id == planilla.extracto_id
    ).first().movimientos

    # Ejecutar conciliación
    try:
        resultado = conciliar_planilla(
            db=db,
            planilla_rows=planilla.rows,
            movimientos=movimientos,
            cliente_nombre=planilla.cliente.nombre,
            fecha_acred_str=fecha_acred
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

    # Liberar movimientos que estaban acreditados a esta planilla
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
    """Retorna planilla con stats + datos del movimiento bancario para filtrar en el panel"""
    from app.models.extracto import MovimientoBanco

    p = db.query(Planilla).filter(Planilla.id == planilla_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Planilla no encontrada")

    # Pre-cargar movimientos del extracto en un dict por id para el JOIN manual
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
