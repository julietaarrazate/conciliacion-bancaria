from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, or_
from datetime import date
from typing import Optional
import tempfile
import os

from app.database import get_db
from app.models.extracto import ExtractoBancario, MovimientoBanco
from app.models.user import User
from app.schemas.extracto import (
    ExtractoBancarioResponse,
    ExtractoListResponse,
    MergeUMResponse,
    MovimientosFiltradosResponse
)
from app.services.excel_parser import parsear_extracto_bancario
from app.services.extracto_merger import mergear_movimientos
from app.services.auditoria import registrar_log
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/extractos", tags=["extractos"])


@router.get("", response_model=ExtractoListResponse)
def list_extractos(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user)
):
    """Lista todos los extractos con conteo de movimientos"""
    total = db.query(ExtractoBancario).count()
    rows = (
        db.query(ExtractoBancario)
        .order_by(desc(ExtractoBancario.fecha_creacion))
        .offset(skip)
        .limit(limit)
        .all()
    )
    items = [
        {
            "id": e.id,
            "nombre_archivo": e.nombre_archivo,
            "fecha_creacion": e.fecha_creacion,
            "total_movimientos": len(e.movimientos)
        }
        for e in rows
    ]
    return {"total": total, "items": items}


@router.post("/upload", response_model=ExtractoBancarioResponse)
async def upload_extracto(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Carga un nuevo extracto bancario completo (no es UM)"""
    if not file.filename.endswith('.xlsx'):
        raise HTTPException(400, "Solo se aceptan archivos Excel (.xlsx)")

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
            contents = await file.read()
            tmp.write(contents)
            tmp_path = tmp.name

        parsed = parsear_extracto_bancario(tmp_path)

        extracto = ExtractoBancario(
            nombre_archivo=file.filename,
            creado_por=current_user.id
        )
        db.add(extracto)
        db.flush()

        for mov_data in parsed["movimientos"]:
            db.add(MovimientoBanco(
                extracto_id=extracto.id,
                orden=mov_data.get("orden"),
                fecha=mov_data.get("fecha"),
                mes=mov_data.get("mes"),
                titular=mov_data.get("titular"),
                monto=mov_data.get("monto"),
                saldo=mov_data.get("saldo")
            ))

        db.commit()
        db.refresh(extracto)

        registrar_log(
            db=db,
            usuario_id=current_user.id,
            tabla="extractos_bancarios",
            registro_id=extracto.id,
            accion="INSERT",
            cambios={"nombre_archivo": file.filename, "movimientos": len(parsed["movimientos"])}
        )

        return extracto
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(400, f"Error al procesar archivo: {str(e)}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


@router.post("/{extracto_id}/agregar-um", response_model=MergeUMResponse)
async def agregar_ultimos_movimientos(
    extracto_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Agrega Ultimos Movimientos (UM) a un extracto existente, detectando
    duplicados por (fecha, mes, importe, saldo). Solo se suman los movimientos
    que no esten ya en el extracto.
    """
    extracto = db.query(ExtractoBancario).filter(ExtractoBancario.id == extracto_id).first()
    if not extracto:
        raise HTTPException(404, "Extracto no encontrado")

    if not file.filename.endswith('.xlsx'):
        raise HTTPException(400, "Solo se aceptan archivos Excel (.xlsx)")

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
            contents = await file.read()
            tmp.write(contents)
            tmp_path = tmp.name

        parsed = parsear_extracto_bancario(tmp_path)
        stats = mergear_movimientos(db, extracto_id, parsed["movimientos"])

        registrar_log(
            db=db,
            usuario_id=current_user.id,
            tabla="extractos_bancarios",
            registro_id=extracto_id,
            accion="APPEND_UM",
            cambios={
                "archivo": file.filename,
                "agregados": stats["agregados"],
                "duplicados": stats["duplicados"],
                "total_recibido": stats["total_recibido"]
            }
        )

        return {"extracto_id": extracto_id, **stats}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(400, f"Error al procesar UM: {str(e)}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


@router.get("/{extracto_id}/movimientos", response_model=MovimientosFiltradosResponse)
def listar_movimientos(
    extracto_id: int,
    cliente: Optional[str] = Query(None, description="Filtrar por cliente acreditado"),
    cuit: Optional[str] = Query(None, description="Filtrar por CUIT en titular"),
    titular: Optional[str] = Query(None, description="Filtrar por texto en titular"),
    desde: Optional[date] = Query(None, description="Fecha de acreditacion desde"),
    hasta: Optional[date] = Query(None, description="Fecha de acreditacion hasta"),
    fecha_desde: Optional[date] = Query(None, description="Fecha del movimiento desde"),
    fecha_hasta: Optional[date] = Query(None, description="Fecha del movimiento hasta"),
    sin_acreditar: Optional[bool] = Query(None, description="True = solo no acreditados"),
    skip: int = 0,
    limit: int = 500,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user)
):
    """
    Lista movimientos del extracto con filtros tipo Excel:
    - cliente: nombre del cliente acreditado (busca parcial, case-insensitive)
    - cuit: matchea texto en titular (donde suele estar el CUIT)
    - titular: matchea texto en titular
    - desde/hasta: rango de fecha de acreditacion
    - fecha_desde/fecha_hasta: rango de fecha del movimiento
    - sin_acreditar: True para ver solo los que aun no estan acreditados
    """
    extracto = db.query(ExtractoBancario).filter(ExtractoBancario.id == extracto_id).first()
    if not extracto:
        raise HTTPException(404, "Extracto no encontrado")

    q = db.query(MovimientoBanco).filter(MovimientoBanco.extracto_id == extracto_id)

    if cliente:
        q = q.filter(MovimientoBanco.cliente_acreditado.ilike(f"%{cliente}%"))

    if cuit:
        # CUIT esta dentro del campo titular del extracto
        cuit_clean = cuit.replace("-", "").replace(" ", "")
        q = q.filter(MovimientoBanco.titular.ilike(f"%{cuit_clean}%"))

    if titular:
        q = q.filter(MovimientoBanco.titular.ilike(f"%{titular}%"))

    if desde:
        q = q.filter(MovimientoBanco.fecha_acred >= desde)
    if hasta:
        q = q.filter(MovimientoBanco.fecha_acred <= hasta)

    if fecha_desde:
        q = q.filter(MovimientoBanco.fecha >= fecha_desde)
    if fecha_hasta:
        q = q.filter(MovimientoBanco.fecha <= fecha_hasta)

    if sin_acreditar is True:
        q = q.filter(
            or_(
                MovimientoBanco.cliente_acreditado.is_(None),
                MovimientoBanco.cliente_acreditado == "",
                MovimientoBanco.cliente_acreditado.ilike("no identificado")
            )
        )
    elif sin_acreditar is False:
        q = q.filter(
            and_(
                MovimientoBanco.cliente_acreditado.isnot(None),
                MovimientoBanco.cliente_acreditado != "",
                ~MovimientoBanco.cliente_acreditado.ilike("no identificado")
            )
        )

    total = q.count()
    items = (
        q.order_by(desc(MovimientoBanco.fecha), desc(MovimientoBanco.id))
        .offset(skip)
        .limit(limit)
        .all()
    )

    return {"extracto_id": extracto_id, "total": total, "items": items}


@router.get("/{extracto_id}", response_model=ExtractoBancarioResponse)
def get_extracto(
    extracto_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user)
):
    """Obtiene un extracto completo con todos sus movimientos"""
    extracto = db.query(ExtractoBancario).filter(ExtractoBancario.id == extracto_id).first()
    if not extracto:
        raise HTTPException(404, "Extracto no encontrado")
    return extracto
