from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from sqlalchemy.orm import Session
import tempfile
import os

from app.database import get_db
from app.models.planilla import Planilla, PlanillaRow
from app.models.cliente import Cliente
from app.models.extracto import ExtractoBancario
from app.models.user import User
from app.schemas.planilla import PlanillaResponse, ConciliacionResultado
from app.services.excel_parser import parsear_planilla_cliente
from app.services.conciliacion import conciliar_planilla
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

@router.get("/{planilla_id}", response_model=PlanillaResponse)
def get_planilla(
    planilla_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtiene una planilla y su estado de conciliación"""
    planilla = db.query(Planilla).filter(
        Planilla.id == planilla_id
    ).first()

    if not planilla:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Planilla no encontrada"
        )

    return planilla
