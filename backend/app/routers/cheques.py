from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
import base64, io
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import openpyxl

from app.database import get_db
from app.middleware.auth import get_current_user, require_permission, can_switch_org
from app.models.user import User
from app.models.cheque import Cheque
from app.models.cliente import Cliente
from app.services.motor_contable import registrar_cheque, acreditar_cheque, rechazar_cheque
from app.services.auditoria import registrar_log
from app.services.storage import upload_comprobante

router = APIRouter(prefix="/cheques", tags=["cheques"])


class ChequeIn(BaseModel):
    cliente_id:          Optional[int] = None
    numero:              Optional[str] = None
    banco_origen:        Optional[str] = None
    titular:             Optional[str] = None
    monto:               float = Field(..., gt=0)
    comision:            float = Field(0.0, ge=0)
    porcentaje_comision: Optional[float] = None  # % comisión para liquidaciones
    fecha_emision:       Optional[date] = None
    fecha_deposito:      Optional[date] = None
    notas:               Optional[str] = None


class AcreditarIn(BaseModel):
    fecha_acred: Optional[date] = None


def _org_id(current_user: User, org_id: Optional[int]) -> int:
    if can_switch_org(current_user, org_id) and org_id:
        return org_id
    return current_user.organizacion_id or 1


def _cheque_dict(c: Cheque) -> dict:
    return {
        "id":             c.id,
        "organizacion_id": c.organizacion_id,
        "cliente_id":     c.cliente_id,
        "cliente_nombre": c.cliente.nombre if c.cliente else None,
        "numero":         c.numero,
        "banco_origen":   c.banco_origen,
        "titular":        c.titular,
        "monto":          c.monto,
        "comision":            c.comision,
        "porcentaje_comision": float(c.porcentaje_comision) if c.porcentaje_comision is not None else None,
        "fecha_emision":  c.fecha_emision,
        "fecha_deposito": c.fecha_deposito,
        "fecha_acred":    c.fecha_acred,
        "estado":         c.estado,
        "notas":          c.notas,
        "tiene_foto":     bool(c.foto_comprobante),
        "created_at":     c.created_at,
    }


@router.get("")
def list_cheques(
    org_id:     Optional[int] = Query(None),
    estado:     Optional[str] = Query(None),
    cliente_id: Optional[int] = Query(None),
    desde:      Optional[str] = Query(None),
    hasta:      Optional[str] = Query(None),
    skip:       int = 0,
    limit:      int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    oid = _org_id(current_user, org_id)
    q = db.query(Cheque).filter(Cheque.organizacion_id == oid)
    if estado:
        q = q.filter(Cheque.estado == estado)
    if cliente_id:
        q = q.filter(Cheque.cliente_id == cliente_id)
    if desde:
        q = q.filter(Cheque.fecha_deposito >= desde)
    if hasta:
        q = q.filter(Cheque.fecha_deposito <= hasta)
    total = q.count()
    items = q.order_by(Cheque.created_at.desc()).offset(skip).limit(limit).all()
    return {"total": total, "items": [_cheque_dict(c) for c in items]}


@router.post("")
def crear_cheque(
    body: ChequeIn,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    oid = _org_id(current_user, org_id)
    if body.cliente_id:
        cli = db.query(Cliente).filter(Cliente.id == body.cliente_id, Cliente.organizacion_id == oid).first()
        if not cli:
            raise HTTPException(404, "Cliente no encontrado")

    c = Cheque(
        organizacion_id=oid,
        cliente_id=body.cliente_id,
        numero=body.numero,
        banco_origen=body.banco_origen,
        titular=body.titular,
        monto=body.monto,
        comision=body.comision,
        porcentaje_comision=Decimal(str(body.porcentaje_comision)) if body.porcentaje_comision is not None else None,
        fecha_emision=body.fecha_emision,
        fecha_deposito=body.fecha_deposito or date.today(),
        estado="pendiente",
        notas=body.notas,
        usuario_id=current_user.id,
    )
    db.add(c)
    db.flush()

    registrar_cheque(
        db=db,
        cheque_id=c.id,
        org_id=oid,
        usuario_id=current_user.id,
        titular=c.titular or "",
        monto=c.monto,
        comision=c.comision,
        fecha=c.fecha_deposito or date.today(),
    )
    registrar_log(db, current_user.id, "cheques", c.id, "INSERT",
                  {"monto": c.monto, "titular": c.titular, "cliente_id": c.cliente_id,
                   "fecha_deposito": str(c.fecha_deposito) if c.fecha_deposito else None})
    db.commit()
    db.refresh(c)
    return _cheque_dict(c)


@router.get("/{cheque_id}")
def get_cheque(
    cheque_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    oid = current_user.organizacion_id or 1
    c = db.query(Cheque).filter(Cheque.id == cheque_id).first()
    if not c:
        raise HTTPException(404, "Cheque no encontrado")
    if not current_user.is_superadmin and c.organizacion_id != oid:
        raise HTTPException(403, "Sin acceso")
    return _cheque_dict(c)


@router.patch("/{cheque_id}")
def editar_cheque(
    cheque_id: int,
    body: ChequeIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    oid = current_user.organizacion_id or 1
    c = db.query(Cheque).filter(Cheque.id == cheque_id).first()
    if not c:
        raise HTTPException(404, "Cheque no encontrado")
    if not current_user.is_superadmin and c.organizacion_id != oid:
        raise HTTPException(403, "Sin acceso")
    if c.estado != "pendiente":
        raise HTTPException(400, "Solo se pueden editar cheques pendientes")
    cambios = {}
    for field in ("cliente_id", "numero", "banco_origen", "titular", "monto",
                  "comision", "fecha_emision", "fecha_deposito", "notas"):
        val = getattr(body, field, None)
        if val is not None:
            cambios[field] = {"de": str(getattr(c, field)), "a": str(val)}
            setattr(c, field, val)
    if body.porcentaje_comision is not None:
        c.porcentaje_comision = Decimal(str(body.porcentaje_comision))
    if cambios:
        registrar_log(db, current_user.id, "cheques", c.id, "UPDATE", cambios)
    db.commit()
    db.refresh(c)
    return _cheque_dict(c)


@router.post("/{cheque_id}/acreditar")
def acreditar(
    cheque_id: int,
    body: AcreditarIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    oid = current_user.organizacion_id or 1
    c = db.query(Cheque).filter(Cheque.id == cheque_id).first()
    if not c:
        raise HTTPException(404, "Cheque no encontrado")
    if not current_user.is_superadmin and c.organizacion_id != oid:
        raise HTTPException(403, "Sin acceso")
    if c.estado != "pendiente":
        raise HTTPException(400, f"Cheque ya está {c.estado}")

    c.estado = "acreditado"
    c.fecha_acred = body.fecha_acred or date.today()
    db.flush()

    acreditar_cheque(
        db=db,
        cheque_id=c.id,
        org_id=c.organizacion_id,
        usuario_id=current_user.id,
        titular=c.titular or "",
        monto=c.monto,
        fecha=c.fecha_acred,
    )
    registrar_log(db, current_user.id, "cheques", c.id, "ACREDITAR",
                  {"monto": c.monto, "fecha_acred": str(c.fecha_acred)})
    db.commit()
    db.refresh(c)
    return _cheque_dict(c)


@router.post("/{cheque_id}/rechazar")
def rechazar(
    cheque_id: int,
    body: AcreditarIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    oid = current_user.organizacion_id or 1
    c = db.query(Cheque).filter(Cheque.id == cheque_id).first()
    if not c:
        raise HTTPException(404, "Cheque no encontrado")
    if not current_user.is_superadmin and c.organizacion_id != oid:
        raise HTTPException(403, "Sin acceso")
    if c.estado != "pendiente":
        raise HTTPException(400, f"Cheque ya está {c.estado}")

    c.estado = "rechazado"
    c.fecha_acred = body.fecha_acred or date.today()
    db.flush()

    rechazar_cheque(
        db=db,
        cheque_id=c.id,
        org_id=c.organizacion_id,
        usuario_id=current_user.id,
        titular=c.titular or "",
        monto=c.monto,
        fecha=c.fecha_acred,
    )
    registrar_log(db, current_user.id, "cheques", c.id, "RECHAZAR",
                  {"monto": c.monto, "fecha_acred": str(c.fecha_acred)})
    db.commit()
    db.refresh(c)
    return _cheque_dict(c)


@router.delete("/{cheque_id}")
def eliminar_cheque(
    cheque_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("delete_records")),
):
    oid = current_user.organizacion_id or 1
    c = db.query(Cheque).filter(Cheque.id == cheque_id).first()
    if not c:
        raise HTTPException(404, "Cheque no encontrado")
    if not current_user.is_superadmin and c.organizacion_id != oid:
        raise HTTPException(403, "Sin acceso")
    if c.estado != "pendiente":
        raise HTTPException(400, "Solo se pueden eliminar cheques pendientes")

    # Reverso contable ANTES de borrar (preserva trazabilidad de la carga)
    from app.services.motor_contable import reversar_asientos
    reversar_asientos(db, modulo="cheque_carga", referencia_id=cheque_id,
                      org_id=c.organizacion_id, usuario_id=current_user.id,
                      motivo=f"Cheque #{cheque_id} eliminado por {current_user.email}")
    reversar_asientos(db, modulo="cheque_comision", referencia_id=cheque_id,
                      org_id=c.organizacion_id, usuario_id=current_user.id,
                      motivo=f"Cheque #{cheque_id} eliminado por {current_user.email}")

    registrar_log(db, current_user.id, "cheques", cheque_id, "DELETE",
                  {"monto": c.monto, "titular": c.titular, "estado": c.estado})
    db.delete(c)
    db.commit()
    return {"ok": True}


# ── Foto comprobante ─────────────────────────────────────────────

class FotoIn(BaseModel):
    foto_base64: str


@router.post("/{cheque_id}/foto")
def subir_foto(
    cheque_id: int,
    body: FotoIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    oid = current_user.organizacion_id or 1
    c = db.query(Cheque).filter(Cheque.id == cheque_id).first()
    if not c:
        raise HTTPException(404, "Cheque no encontrado")
    if not current_user.is_superadmin and c.organizacion_id != oid:
        raise HTTPException(403, "Sin acceso")
    c.foto_comprobante = upload_comprobante(body.foto_base64, prefix=f"cheque/{c.organizacion_id}")
    db.commit()
    return {"ok": True, "tiene_foto": True}


@router.get("/{cheque_id}/foto")
def ver_foto(
    cheque_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    oid = current_user.organizacion_id or 1
    c = db.query(Cheque).filter(Cheque.id == cheque_id).first()
    if not c:
        raise HTTPException(404, "Cheque no encontrado")
    if not current_user.is_superadmin and c.organizacion_id != oid:
        raise HTTPException(403, "Sin acceso")
    if not c.foto_comprobante:
        raise HTTPException(404, "Sin foto")
    return {"cheque_id": cheque_id, "foto_base64": c.foto_comprobante}


@router.delete("/{cheque_id}/foto")
def eliminar_foto(
    cheque_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("delete_records")),
):
    oid = current_user.organizacion_id or 1
    c = db.query(Cheque).filter(Cheque.id == cheque_id).first()
    if not c:
        raise HTTPException(404, "Cheque no encontrado")
    if not current_user.is_superadmin and c.organizacion_id != oid:
        raise HTTPException(403, "Sin acceso")
    c.foto_comprobante = None
    db.commit()
    return {"ok": True}


# ── Importación masiva por Excel ─────────────────────────────────
# Columnas esperadas (case-insensitive, cualquier orden):
# titular | banco_origen | numero | monto | comision | fecha_emision | fecha_deposito | cliente | notas

def _parse_date(v) -> Optional[date]:
    if v is None:
        return None
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v)[:10])
    except Exception:
        return None


@router.post("/importar")
async def importar_excel(
    file: UploadFile = File(...),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Importa cheques desde un Excel. Columnas: titular, banco_origen, numero,
    monto, comision (opcional), fecha_emision (opcional), fecha_deposito (opcional),
    cliente (nombre o id, opcional), notas (opcional)."""
    oid = _org_id(current_user, org_id)
    ext = (file.filename or '').lower().split('.')[-1]
    if ext not in ('xlsx', 'xls'):
        raise HTTPException(400, "Solo se aceptan archivos .xlsx o .xls")

    content = await file.read()
    try:
        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
    except Exception as e:
        raise HTTPException(400, f"No se pudo leer el archivo: {e}")

    if not rows:
        raise HTTPException(400, "El archivo está vacío")

    # Mapear encabezados
    headers = [str(h).strip().lower() if h is not None else '' for h in rows[0]]
    COL = {
        'titular':        next((i for i, h in enumerate(headers) if 'titular' in h), None),
        'banco_origen':   next((i for i, h in enumerate(headers) if 'banco' in h), None),
        'numero':         next((i for i, h in enumerate(headers) if 'numer' in h or 'cheque' in h), None),
        'monto':          next((i for i, h in enumerate(headers) if 'monto' in h or 'importe' in h), None),
        'comision':       next((i for i, h in enumerate(headers) if 'comis' in h), None),
        'fecha_emision':  next((i for i, h in enumerate(headers) if 'emisi' in h), None),
        'fecha_deposito': next((i for i, h in enumerate(headers) if 'deposito' in h or 'depósito' in h or 'dep' in h), None),
        'cliente':        next((i for i, h in enumerate(headers) if 'cliente' in h), None),
        'notas':          next((i for i, h in enumerate(headers) if 'nota' in h or 'observ' in h), None),
    }
    if COL['monto'] is None:
        raise HTTPException(400, "Columna 'monto' requerida no encontrada")

    # Cache de clientes
    clientes_cache: dict[str, int] = {
        c.nombre.lower(): c.id
        for c in db.query(Cliente).filter(Cliente.organizacion_id == oid).all()
    }

    importados, errores = 0, []
    for i, row in enumerate(rows[1:], start=2):
        try:
            monto_raw = row[COL['monto']] if COL['monto'] is not None else None
            if not monto_raw:
                continue
            monto = Decimal(str(monto_raw).replace(',', '.').replace('$', '').strip())
            if monto <= 0:
                continue

            cliente_id = None
            if COL['cliente'] is not None and row[COL['cliente']]:
                cv = str(row[COL['cliente']]).strip()
                if cv.isdigit():
                    cliente_id = int(cv)
                else:
                    cliente_id = clientes_cache.get(cv.lower())

            comision = Decimal("0")
            if COL['comision'] is not None and row[COL['comision']]:
                try:
                    comision = Decimal(str(row[COL['comision']]).replace(',', '.').replace('$', '').strip())
                except Exception:
                    pass

            c = Cheque(
                organizacion_id=oid,
                cliente_id=cliente_id,
                titular=str(row[COL['titular']]).strip() if COL['titular'] is not None and row[COL['titular']] else None,
                banco_origen=str(row[COL['banco_origen']]).strip() if COL['banco_origen'] is not None and row[COL['banco_origen']] else None,
                numero=str(row[COL['numero']]).strip() if COL['numero'] is not None and row[COL['numero']] else None,
                monto=monto,
                comision=comision,
                fecha_emision=_parse_date(row[COL['fecha_emision']]) if COL['fecha_emision'] is not None else None,
                fecha_deposito=_parse_date(row[COL['fecha_deposito']]) if COL['fecha_deposito'] is not None else date.today(),
                notas=str(row[COL['notas']]).strip() if COL['notas'] is not None and row[COL['notas']] else None,
                estado="pendiente",
                usuario_id=current_user.id,
            )
            db.add(c)
            db.flush()
            registrar_cheque(
                db=db, cheque_id=c.id, org_id=oid,
                usuario_id=current_user.id,
                titular=c.titular or "",
                monto=c.monto, comision=c.comision,
                fecha=c.fecha_deposito or date.today(),
            )
            importados += 1
        except Exception as ex:
            errores.append(f"Fila {i}: {ex}")

    db.commit()
    return {"importados": importados, "errores": errores}
