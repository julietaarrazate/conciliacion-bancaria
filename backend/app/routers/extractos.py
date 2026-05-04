from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, or_, text, func
from datetime import date, datetime
from typing import Optional
import tempfile, os, io, hashlib

from app.database import get_db
from app.models.extracto import ExtractoBancario, MovimientoBanco
from app.models.planilla import Planilla
from app.models.user import User
from app.schemas.extracto import (
    ExtractoBancarioResponse, ExtractoListResponse,
    MergeUMResponse, MovimientosFiltradosResponse
)
from app.services.excel_parser import parsear_extracto_bancario
from app.services.extracto_merger import mergear_movimientos
from app.services.auditoria import registrar_log
from app.services.excel_export import export_movimientos, export_extracto_contador
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/extractos", tags=["extractos"])


def _fingerprint(movimientos: list) -> str:
    """Huella digital del extracto: hash de total+ordenes+suma_montos"""
    total = len(movimientos)
    if total == 0:
        return "empty"
    primer_orden = movimientos[0].get("orden") or 0
    ultimo_orden = movimientos[-1].get("orden") or 0
    suma = round(sum(m.get("monto", 0) for m in movimientos), 2)
    raw = f"{total}|{primer_orden}|{ultimo_orden}|{suma}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


@router.get("", response_model=ExtractoListResponse)
def list_extractos(skip: int = 0, limit: int = 50,
                   org_id: Optional[int] = Query(None),
                   db: Session = Depends(get_db),
                   current_user: User = Depends(get_current_user)):
    mov_count = (
        db.query(MovimientoBanco.extracto_id, func.count(MovimientoBanco.id).label("total"))
        .group_by(MovimientoBanco.extracto_id)
        .subquery()
    )
    q = (
        db.query(ExtractoBancario, mov_count.c.total)
        .outerjoin(mov_count, ExtractoBancario.id == mov_count.c.extracto_id)
    )
    if current_user.is_superadmin and org_id:
        q = q.filter(ExtractoBancario.organizacion_id == org_id)
    elif not current_user.is_superadmin:
        q = q.filter(ExtractoBancario.organizacion_id == (current_user.organizacion_id or 1))
    total = q.count()
    rows = q.order_by(desc(ExtractoBancario.fecha_creacion)).offset(skip).limit(limit).all()
    items = [{"id": e.id, "nombre_archivo": e.nombre_archivo,
              "fecha_creacion": e.fecha_creacion, "total_movimientos": int(cnt or 0)} for e, cnt in rows]
    return {"total": total, "items": items}


@router.post("/upload", response_model=ExtractoBancarioResponse)
async def upload_extracto(file: UploadFile = File(...),
                          db: Session = Depends(get_db),
                          current_user: User = Depends(get_current_user)):
    if not file.filename.endswith('.xlsx'):
        raise HTTPException(400, "Solo se aceptan archivos Excel (.xlsx)")
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        parsed = parsear_extracto_bancario(tmp_path)
        movs = parsed["movimientos"]
        fp = _fingerprint(movs)

        # Detectar duplicado
        existente = db.query(ExtractoBancario).filter(ExtractoBancario.fingerprint == fp).first()
        if existente:
            raise HTTPException(409, {
                "message": f"Este extracto ya fue cargado (#{existente.id} — {existente.nombre_archivo}, {len(existente.movimientos)} movimientos). "
                           f"Si querés agregar movimientos nuevos, usá 'Agregar UM'.",
                "extracto_id": existente.id,
                "nombre": existente.nombre_archivo
            })

        extracto = ExtractoBancario(nombre_archivo=file.filename, creado_por=current_user.id, fingerprint=fp)
        db.add(extracto)
        db.flush()
        for m in movs:
            db.add(MovimientoBanco(extracto_id=extracto.id, orden=m.get("orden"),
                                   fecha=m.get("fecha"), mes=m.get("mes"),
                                   titular=m.get("titular"), monto=m.get("monto"), saldo=m.get("saldo")))
        db.commit()
        db.refresh(extracto)
        registrar_log(db, current_user.id, "extractos_bancarios", extracto.id, "INSERT",
                      {"nombre_archivo": file.filename, "movimientos": len(movs)})
        return extracto
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(400, f"Error al procesar archivo: {str(e)}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


@router.delete("/{extracto_id}")
def delete_extracto(extracto_id: int, db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    """Elimina extracto, sus planillas y movimientos usando ORM (compatible SQLite+Postgres)."""
    from app.models.planilla import PlanillaRow

    extracto = db.query(ExtractoBancario).filter(ExtractoBancario.id == extracto_id).first()
    if not extracto:
        raise HTTPException(404, "Extracto no encontrado")

    nombre  = extracto.nombre_archivo

    try:
        n_movs = db.query(func.count(MovimientoBanco.id)).filter(
            MovimientoBanco.extracto_id == extracto_id
        ).scalar() or 0

        planilla_ids = [p.id for p in db.query(Planilla.id).filter(
            Planilla.extracto_id == extracto_id
        ).all()]

        if planilla_ids:
            db.query(PlanillaRow).filter(
                PlanillaRow.planilla_id.in_(planilla_ids)
            ).delete(synchronize_session=False)

        db.query(PlanillaRow).filter(
            PlanillaRow.orden_movimiento_acreditado.in_(
                db.query(MovimientoBanco.id).filter(MovimientoBanco.extracto_id == extracto_id)
            )
        ).update({"orden_movimiento_acreditado": None}, synchronize_session=False)

        if planilla_ids:
            db.query(Planilla).filter(Planilla.id.in_(planilla_ids)).delete(synchronize_session=False)

        db.query(MovimientoBanco).filter(
            MovimientoBanco.extracto_id == extracto_id
        ).delete(synchronize_session=False)

        db.delete(extracto)
        db.commit()

        registrar_log(db, current_user.id, "extractos_bancarios", extracto_id, "DELETE",
                      {"nombre": nombre, "movimientos": n_movs})
        return {"ok": True, "mensaje": f"Extracto #{extracto_id} eliminado ({nombre})"}
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Error al eliminar: {str(e)}")


@router.delete("")
def delete_todos_extractos(db: Session = Depends(get_db),
                           current_user: User = Depends(get_current_user)):
    """Elimina TODOS los extractos, planillas y movimientos. Limpia la BD para empezar de cero."""
    from app.models.planilla import PlanillaRow, Planilla

    try:
        db.query(PlanillaRow).update({"orden_movimiento_acreditado": None}, synchronize_session=False)
        n_rows = db.query(PlanillaRow).delete(synchronize_session=False)
        n_planillas = db.query(Planilla).delete(synchronize_session=False)
        n_movs = db.query(MovimientoBanco).delete(synchronize_session=False)
        n_extractos = db.query(ExtractoBancario).delete(synchronize_session=False)
        db.commit()

        registrar_log(db, current_user.id, "extractos_bancarios", 0, "DELETE_ALL",
                      {"extractos": n_extractos, "movimientos": n_movs, "planillas": n_planillas})
        return {"ok": True, "mensaje": f"Limpieza completa: {n_extractos} extractos, {n_planillas} planillas, {n_movs} movimientos eliminados"}
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Error al limpiar: {str(e)}")


@router.post("/{extracto_id}/agregar-um", response_model=MergeUMResponse)
async def agregar_ultimos_movimientos(extracto_id: int, file: UploadFile = File(...),
                                      db: Session = Depends(get_db),
                                      current_user: User = Depends(get_current_user)):
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
    if cliente: q = q.filter(MovimientoBanco.cliente_acreditado.ilike(f"%{cliente}%"))
    if cuit: q = q.filter(MovimientoBanco.titular.ilike(f"%{cuit.replace('-','').replace(' ','')}%"))
    if titular: q = q.filter(MovimientoBanco.titular.ilike(f"%{titular}%"))
    if desde: q = q.filter(MovimientoBanco.fecha_acred >= desde)
    if hasta: q = q.filter(MovimientoBanco.fecha_acred <= hasta)
    if fecha_desde: q = q.filter(MovimientoBanco.fecha >= fecha_desde)
    if fecha_hasta: q = q.filter(MovimientoBanco.fecha <= fecha_hasta)
    if sin_acreditar is True:
        q = q.filter(or_(MovimientoBanco.cliente_acreditado.is_(None),
                         MovimientoBanco.cliente_acreditado == "",
                         MovimientoBanco.cliente_acreditado.ilike("no identificado")))
    elif sin_acreditar is False:
        q = q.filter(and_(MovimientoBanco.cliente_acreditado.isnot(None),
                          MovimientoBanco.cliente_acreditado != "",
                          ~MovimientoBanco.cliente_acreditado.ilike("no identificado")))
    return q


@router.get("/{extracto_id}/movimientos", response_model=MovimientosFiltradosResponse)
def listar_movimientos(extracto_id: int,
                       cliente: Optional[str] = Query(None), cuit: Optional[str] = Query(None),
                       titular: Optional[str] = Query(None), desde: Optional[date] = Query(None),
                       hasta: Optional[date] = Query(None), fecha_desde: Optional[date] = Query(None),
                       fecha_hasta: Optional[date] = Query(None), sin_acreditar: Optional[bool] = Query(None),
                       skip: int = 0, limit: int = 0,
                       db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    if not db.query(ExtractoBancario).filter(ExtractoBancario.id == extracto_id).first():
        raise HTTPException(404, "Extracto no encontrado")
    q = _build_mov_query(db, extracto_id, cliente, cuit, titular, desde, hasta, fecha_desde, fecha_hasta, sin_acreditar)
    total = q.count()
    q = q.order_by(desc(MovimientoBanco.fecha), desc(MovimientoBanco.id)).offset(skip)
    if limit > 0:
        q = q.limit(limit)
    items = q.all()
    return {"extracto_id": extracto_id, "total": total, "items": items}


@router.get("/{extracto_id}/movimientos/export")
def export_movimientos_xlsx(extracto_id: int,
                            cliente: Optional[str] = Query(None), cuit: Optional[str] = Query(None),
                            titular: Optional[str] = Query(None), desde: Optional[date] = Query(None),
                            hasta: Optional[date] = Query(None), fecha_desde: Optional[date] = Query(None),
                            fecha_hasta: Optional[date] = Query(None), sin_acreditar: Optional[bool] = Query(None),
                            db: Session = Depends(get_db), _: User = Depends(get_current_user)):
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


@router.get("/{extracto_id}/export-contador")
def export_para_contador(
    extracto_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user)
):
    """
    Descarga el extracto completo conciliado en Excel profesional para el contador.
    Hoja 1: todos los movimientos con acreditaciones coloreadas en verde.
    Hoja 2: resumen estadístico y detalle por cliente.
    """
    extracto = db.query(ExtractoBancario).filter(ExtractoBancario.id == extracto_id).first()
    if not extracto:
        raise HTTPException(404, "Extracto no encontrado")

    movs = sorted(extracto.movimientos, key=lambda m: (m.fecha or "", m.orden or 0))
    data = [
        {
            "orden": m.orden,
            "fecha": m.fecha,
            "mes": m.mes,
            "titular": m.titular,
            "monto": m.monto,
            "saldo": m.saldo,
            "cliente_acreditado": m.cliente_acreditado,
            "fecha_acred": m.fecha_acred,
        }
        for m in movs
    ]

    xlsx = export_extracto_contador(extracto.nombre_archivo, data)
    fecha_str = datetime.now().strftime('%Y%m%d')
    nombre_base = extracto.nombre_archivo.replace('.xlsx', '').replace('.XLSX', '')
    filename = f"{nombre_base}_conciliado_{fecha_str}.xlsx"

    return StreamingResponse(
        io.BytesIO(xlsx),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.patch("/{extracto_id}/movimientos/{mov_id}")
def update_movimiento(
    extracto_id: int,
    mov_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Edita un movimiento bancario (titular, monto, fecha, etc.) — para correcciones manuales."""
    mov = db.query(MovimientoBanco).filter(
        MovimientoBanco.id == mov_id,
        MovimientoBanco.extracto_id == extracto_id
    ).first()
    if not mov:
        raise HTTPException(404, "Movimiento no encontrado")

    campos_editables = {"titular", "monto", "fecha", "mes", "saldo", "orden"}
    for campo, valor in payload.items():
        if campo in campos_editables and valor is not None:
            setattr(mov, campo, valor)

    db.commit()
    db.refresh(mov)
    registrar_log(db, current_user.id, "movimientos_banco", mov_id, "UPDATE",
                  {"campos": list(payload.keys())})
    return {"ok": True, "id": mov_id}


@router.get("/{extracto_id}", response_model=ExtractoBancarioResponse)
def get_extracto(extracto_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    extracto = db.query(ExtractoBancario).filter(ExtractoBancario.id == extracto_id).first()
    if not extracto:
        raise HTTPException(404, "Extracto no encontrado")
    return extracto
