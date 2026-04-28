from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from datetime import datetime
import tempfile
import os

from app.database import get_db
from app.models.extracto import ExtractoBancario, MovimientoBanco
from app.models.user import User
from app.schemas.extracto import ExtractoBancarioResponse
from app.services.excel_parser import parsear_extracto_bancario
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/extractos", tags=["extractos"])

@router.post("/upload", response_model=ExtractoBancarioResponse)
async def upload_extracto(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Carga un archivo de extracto bancario.
    Parsea automáticamente el archivo Excel y lo almacena en BD.
    """

    # Validar tipo de archivo
    if not file.filename.endswith('.xlsx'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se aceptan archivos Excel (.xlsx)"
        )

    # Guardar archivo temporalmente
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
            contents = await file.read()
            tmp.write(contents)
            tmp_path = tmp.name

        # Parsear el archivo
        parsed = parsear_extracto_bancario(tmp_path)

        # Crear extracto en BD
        extracto = ExtractoBancario(
            nombre_archivo=file.filename,
            creado_por=current_user.id
        )
        db.add(extracto)
        db.flush()  # Para obtener el ID

        # Crear movimientos
        for mov_data in parsed["movimientos"]:
            mov = MovimientoBanco(
                extracto_id=extracto.id,
                orden=mov_data.get("orden"),
                fecha=mov_data.get("fecha"),
                mes=mov_data.get("mes"),
                titular=mov_data.get("titular"),
                monto=mov_data.get("monto"),
                saldo=mov_data.get("saldo")
            )
            db.add(mov)

        db.commit()
        db.refresh(extracto)

        return extracto

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al procesar archivo: {str(e)}"
        )
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

@router.get("/{extracto_id}", response_model=ExtractoBancarioResponse)
def get_extracto(
    extracto_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtiene un extracto por ID"""
    extracto = db.query(ExtractoBancario).filter(
        ExtractoBancario.id == extracto_id
    ).first()

    if not extracto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Extracto no encontrado"
        )

    return extracto
