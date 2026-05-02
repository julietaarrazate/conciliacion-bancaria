from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, or_
from datetime import date, datetime
from typing import Optional
import tempfile
import os
import io

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
from app.services.excel_export import export_movimientos
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/extractos", tags=["extractos"])


@router.get("", response_model=ExtractoListResponse)
def list_extractos(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user)
):
    total = db.query(ExtractoBancario).count()
    rows = (
        db.query(ExtractoBancario)
        .order_by(desc(ExtractoBancario.fecha_creacion))
        .offset(skip).limit(limit).all()
    )
    items = [
        {"id": e.id, "nombre_archivo": e.nombre_archivo,
         "fecha_creacion": e.fecha_creacion, "total_movimientos": len(e.movimientos)}
        for e in rows
    ]
    return {"total": total, "items": items}


@router.post("/upload", response_model=ExtractoBancarioResponse)
async def upload_extracto(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not file.filename.endswith('.xlsx'):
        raise HTTPException(400, "Solo se aceptan archivos Excel (.xlsx)")

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        parsed = parsear_extracto_bancario(tmp_path)
        extracto = ExtractoBancario(nombre_archivo=file.filename, creado_por=current_user.id)
        db.add(extracto)
        db.flush()

        for m in parsed["movimientos"]:
            db.add(MovimientoBanco(
                extracto_id=extracto.id,
                orden=m.get("orden"), fecha=m.get("fecha"),
                mes=m.get("mes"), titular=m.get("titular"),
                monto=m.get("monto"), saldo=m.get("saldo")
            ))

        db.commit()
        db.refresh(extracto)

        registrar_log(db, current_user.id, "extractos_bancarios", extracto.id, "INSERT",
                      {"nombre_archivo": file.filename, "movimientos": len(parsed["movimientos"])})
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
    extracto = db.query(ExtractoBancario).filter(ExtractoBancario.id == extracto_id).first()
    if not extracto:
        raise HTTPException(404, "Extracto no encontrado")
    if not file.filename.endswith('.xlsx'):
        raise HTTPException(400, "Solo se aceptan archivos Excel (.xlsx)")

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        parsed = parsear_extracto_bancario(tmp_path)
        stats = mergear_movimientos(db, extracto_id, parsed["movimientos"])

        registrar_log(db, current_user.id, "extractos_bancarios", extracto_id, "APPEND_UM",
                      {"archivo": file.filename, **stats})
        return {"extracto_id": extracto_id, **stats}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(400, f"Error al procesar UM: {str(e)}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


def _build_mov_query(db, extracto_id, cliente, cuit, titular, desde, hasta, fecha_desde, fecha_hasta, sin_acreditar):
    q = db.query(MovimientoBanco).filter(MovimientoBanco.extracto_id == extracto_id)
    if cliente:
        q = q.filter(MovimientoBanco.cliente_acreditado.ilike(f"%{cliente}%"))
    if cuit:
        q = q.filter(MovimientoBanco.titular.ilike(f"%{cuit.replace('-','').replace(' ','')}%"))
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
        q = q.filter(or_(
            MovimientoBanco.cliente_acreditado.is_(None),
            MovimientoBanco.cliente_acreditado == "",
            MovimientoBanco.cliente_acreditado.ilike("no identificado")
        ))
    elif sin_acreditar is False:
        q = q.filter(and_(
            MovimientoBanco.cliente_acreditado.isnot(None),
            MovimientoBanco.cliente_acreditado != "",
            ~MovimientoBanco.cliente_acreditado.ilike("no identificado")
        ))
    return q


@router.get("/{extracto_id}/movimientos", response_model=MovimientosFiltradosResponse)
def listar_movimientos(
    extracto_id: int,
    cliente: Optional[str] = Query(None),
    cuit: Optional[str] = Query(None),
    titular: Optional[str] = Query(None),
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
    fecha_desde: Optional[date] = Query(None),
    fecha_hasta: Optional[date] = Query(None),
    sin_acreditar: Optional[bool] = Query(None),
    skip: int = 0,
    limit: int = 500,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user)
):
    if not db.query(ExtractoBancario).filter(ExtractoBancario.id == extracto_id).first():
        raise HTTPException(404, "Extracto no encontrado")

    q = _build_mov_query(db, extracto_id, cliente, cuit, titular, desde, hasta, fecha_desde, fecha_hasta, sin_acreditar)
    total = q.count()
    items = q.order_by(desc(MovimientoBanco.fecha), desc(MovimientoBanco.id)).offset(skip).limit(limit).all()
    return {"extracto_id": extracto_id, "total": total, "items": items}


@router.get("/{extracto_id}/movimientos/export")
def export_movimientos_xlsx(
    extracto_id: int,
    cliente: Optional[str] = Query(None),
    cuit: Optional[str] = Query(None),
    titular: Optional[str] = Query(None),
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
    fecha_desde: Optional[date] = Query(None),
    fecha_hasta: Optional[date] = Query(None),
    sin_acreditar: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user)
):
    """Descarga xlsx con movimientos filtrados"""
    extracto = db.query(ExtractoBancario).filter(ExtractoBancario.id == extracto_id).first()
    if not extracto:
        raise HTTPException(404, "Extracto no encontrado")

    q = _build_mov_query(db, extracto_id, cliente, cuit, titular, desde, hasta, fecha_desde, fecha_hasta, sin_acreditar)
    rows = q.order_by(desc(MovimientoBanco.fecha)).all()

    movs = [{"orden": m.orden, "fecha": m.fecha, "mes": m.mes, "titular": m.titular,
              "monto": m.monto, "saldo": m.saldo, "cliente_acreditado": m.cliente_acreditado,
              "fecha_acred": m.fecha_acred} for m in rows]

    data = export_movimientos(extracto.nombre_archivo, movs)
    filename = f"movimientos_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return StreamingResponse(io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/{extracto_id}", response_model=ExtractoBancarioResponse)
def get_extracto(
    extracto_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user)
):
    extracto = db.query(ExtractoBancario).filter(ExtractoBancario.id == extracto_id).first()
    if not extracto:
        raise HTTPException(404, "Extracto no encontrado")
    return extracto
