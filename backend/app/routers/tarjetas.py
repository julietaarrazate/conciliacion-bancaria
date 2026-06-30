"""Router de liquidaciones de tarjetas de crédito (Visa / Mastercard / Amex).

Flujo:
  1. POST /tarjetas/upload — sube un archivo, lo parsea best-effort y devuelve los
     campos detectados (NO guarda nada). El usuario confirma/corrige en el UI.
  2. POST /tarjetas — crea la liquidación, valida la invariante contable y genera
     el asiento mensual agrupado (módulo `tarjeta_liq`).
  3. GET /tarjetas — lista con filtros + paginado.
  4. PATCH /tarjetas/{id}/conciliar — vincula a un movimiento del extracto.
  5. DELETE /tarjetas/{id} — soft delete + reverso del asiento.

Invariante validada antes de crear el asiento:
  neto + aranceles + iva_df + percepciones_iibb + retenciones == monto_bruto
  (tolerancia Decimal('0.01')). Si no balancea → HTTP 422.
"""

import os
import tempfile
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import require_permission, can_switch_org
from app.models.user import User
from app.models.extracto import MovimientoBanco
from app.models.liquidacion_tarjeta import LiquidacionTarjeta, MarcaTarjeta
from app.services.decimal_utils import to_decimal as _D
from app.services.motor_contable import registrar_liquidacion_tarjeta, reversar_asientos
from app.services.tarjeta_parser import parse_liquidacion
from app.services.auditoria import registrar_log

router = APIRouter(prefix="/tarjetas", tags=["tarjetas"])

_TOLERANCIA = Decimal("0.01")
_MARCAS_VALIDAS = {"visa", "mastercard", "amex"}


# ── Schemas ───────────────────────────────────────────────────────

class TarjetaIn(BaseModel):
    marca:              str
    periodo:            str
    fecha_acreditacion: date
    monto_bruto:        float = Field(..., gt=0)
    aranceles:          float = Field(0.0, ge=0)
    iva_df:             float = Field(0.0, ge=0)
    percepciones_iibb:  float = Field(0.0, ge=0)
    retenciones:        float = Field(0.0, ge=0)
    neto:               float = Field(..., ge=0)
    archivo_original:   Optional[str] = None
    notas:              Optional[str] = None


class ConciliarIn(BaseModel):
    extracto_movimiento_id: int


# ── Helpers ───────────────────────────────────────────────────────

def _org_id(current_user: User, org_id: Optional[int]) -> int:
    if can_switch_org(current_user, org_id) and org_id:
        return org_id
    return current_user.organizacion_id or 1




def _liq_dict(l: LiquidacionTarjeta) -> dict:
    marca = l.marca.value if isinstance(l.marca, MarcaTarjeta) else l.marca
    return {
        "id":                     l.id,
        "organizacion_id":        l.organizacion_id,
        "marca":                  marca,
        "periodo":                l.periodo,
        "fecha_acreditacion":     l.fecha_acreditacion,
        "monto_bruto":            l.monto_bruto,
        "aranceles":              l.aranceles,
        "iva_df":                 l.iva_df,
        "percepciones_iibb":      l.percepciones_iibb,
        "retenciones":            l.retenciones,
        "neto":                   l.neto,
        "estado":                 l.estado,
        "extracto_movimiento_id": l.extracto_movimiento_id,
        "archivo_original":       l.archivo_original,
        "asiento_id":             l.asiento_id,
        "notas":                  l.notas,
        "created_at":             l.created_at,
    }


# ── Upload + parse (no guarda) ─────────────────────────────────────

@router.post("/upload")
async def upload_tarjeta(
    marca: str = Query(...),
    file: UploadFile = File(...),
    current_user: User = Depends(require_permission("manage_finance")),
):
    """Sube un archivo de liquidación, lo parsea y devuelve los campos detectados.
    NO persiste nada — el usuario confirma/corrige y luego llama a POST /tarjetas."""
    marca_l = (marca or "").lower().strip()
    if marca_l not in _MARCAS_VALIDAS:
        raise HTTPException(400, f"Marca inválida: {marca}. Use visa, mastercard o amex.")

    filename = file.filename or "liquidacion"
    suffix = "." + filename.rsplit(".", 1)[-1] if "." in filename else ""
    content = await file.read()

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        parsed = parse_liquidacion(tmp_path, marca_l)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    # Serializar Decimals → float para JSON
    def _f(v):
        return float(v) if isinstance(v, Decimal) else v

    return {
        "marca":              marca_l,
        "archivo_original":   filename,
        "periodo":            parsed.get("periodo"),
        "fecha_acreditacion": parsed.get("fecha_acreditacion"),
        "monto_bruto":        _f(parsed.get("monto_bruto")),
        "aranceles":          _f(parsed.get("aranceles")),
        "iva_df":             _f(parsed.get("iva_df")),
        "percepciones_iibb":  _f(parsed.get("percepciones_iibb")),
        "retenciones":        _f(parsed.get("retenciones")),
        "neto":               _f(parsed.get("neto")),
        "parse_warnings":     parsed.get("parse_warnings", []),
    }


# ── Crear + asiento ────────────────────────────────────────────────

@router.post("", status_code=201)
def crear_tarjeta(
    body: TarjetaIn,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage_finance")),
):
    oid = _org_id(current_user, org_id)

    marca_l = (body.marca or "").lower().strip()
    if marca_l not in _MARCAS_VALIDAS:
        raise HTTPException(400, f"Marca inválida: {body.marca}")

    bruto       = _D(body.monto_bruto)
    aranceles   = _D(body.aranceles)
    iva_df      = _D(body.iva_df)
    percep      = _D(body.percepciones_iibb)
    retenciones = _D(body.retenciones)
    neto        = _D(body.neto)

    # Invariante contable
    suma = neto + aranceles + iva_df + percep + retenciones
    if abs(suma - bruto) > _TOLERANCIA:
        raise HTTPException(
            422,
            f"La liquidación no balancea: neto + aranceles + IVA + percepciones + "
            f"retenciones = {suma} ≠ monto bruto {bruto}. Diferencia: {bruto - suma}.",
        )

    liq = LiquidacionTarjeta(
        organizacion_id=oid,
        marca=marca_l,
        periodo=body.periodo,
        fecha_acreditacion=body.fecha_acreditacion,
        monto_bruto=bruto,
        aranceles=aranceles,
        iva_df=iva_df,
        percepciones_iibb=percep,
        retenciones=retenciones,
        neto=neto,
        estado="pendiente",
        archivo_original=body.archivo_original,
        notas=body.notas,
        usuario_id=current_user.id,
    )
    db.add(liq)
    db.flush()

    asiento_id = registrar_liquidacion_tarjeta(
        db=db,
        liquidacion_id=liq.id,
        org_id=oid,
        usuario_id=current_user.id,
        marca=marca_l,
        monto_bruto=bruto,
        aranceles=aranceles,
        iva_df=iva_df,
        percepciones_iibb=percep,
        retenciones=retenciones,
        neto=neto,
        fecha=body.fecha_acreditacion,
        descripcion=f"Liquidación tarjeta {marca_l.capitalize()} {body.periodo}",
    )
    if asiento_id:
        liq.asiento_id = asiento_id

    registrar_log(db, current_user.id, "tarjetas", liq.id, "INSERT",
                  {"marca": marca_l, "periodo": body.periodo,
                   "monto_bruto": float(bruto), "neto": float(neto)})
    db.commit()
    db.refresh(liq)
    return _liq_dict(liq)


# ── Listar ─────────────────────────────────────────────────────────

@router.get("")
def list_tarjetas(
    org_id:  Optional[int] = Query(None),
    marca:   Optional[str] = Query(None),
    estado:  Optional[str] = Query(None),
    periodo: Optional[str] = Query(None),
    skip:    int = 0,
    limit:   int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("view_accounting")),
):
    oid = _org_id(current_user, org_id)
    q = db.query(LiquidacionTarjeta).filter(
        LiquidacionTarjeta.organizacion_id == oid,
        LiquidacionTarjeta.deleted_at.is_(None),
    )
    if marca:
        q = q.filter(LiquidacionTarjeta.marca == marca.lower().strip())
    if estado:
        q = q.filter(LiquidacionTarjeta.estado == estado)
    if periodo:
        q = q.filter(LiquidacionTarjeta.periodo == periodo)
    total = q.count()
    items = (
        q.order_by(LiquidacionTarjeta.fecha_acreditacion.desc(), LiquidacionTarjeta.id.desc())
        .offset(skip).limit(limit).all()
    )
    return {"total": total, "items": [_liq_dict(l) for l in items]}


# ── Detalle ────────────────────────────────────────────────────────

@router.get("/{liq_id}")
def get_tarjeta(
    liq_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("view_accounting")),
):
    l = db.query(LiquidacionTarjeta).filter(
        LiquidacionTarjeta.id == liq_id,
        LiquidacionTarjeta.deleted_at.is_(None),
    ).first()
    if not l:
        raise HTTPException(404, "Liquidación no encontrada")
    if not current_user.is_superadmin and not can_switch_org(current_user, l.organizacion_id) \
            and l.organizacion_id != (current_user.organizacion_id or 1):
        raise HTTPException(403, "Sin acceso")
    return _liq_dict(l)


# ── Conciliar con movimiento del extracto ──────────────────────────

@router.patch("/{liq_id}/conciliar")
def conciliar_tarjeta(
    liq_id: int,
    body: ConciliarIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage_finance")),
):
    l = db.query(LiquidacionTarjeta).filter(
        LiquidacionTarjeta.id == liq_id,
        LiquidacionTarjeta.deleted_at.is_(None),
    ).first()
    if not l:
        raise HTTPException(404, "Liquidación no encontrada")
    if not current_user.is_superadmin and not can_switch_org(current_user, l.organizacion_id) \
            and l.organizacion_id != (current_user.organizacion_id or 1):
        raise HTTPException(403, "Sin acceso")

    mov = db.query(MovimientoBanco).filter(
        MovimientoBanco.id == body.extracto_movimiento_id,
        MovimientoBanco.organizacion_id == l.organizacion_id,
    ).first()
    if not mov:
        raise HTTPException(404, "Movimiento del extracto no encontrado")

    l.extracto_movimiento_id = mov.id
    l.estado = "conciliada"
    registrar_log(db, current_user.id, "tarjetas", l.id, "CONCILIAR",
                  {"movimiento_id": mov.id})
    db.commit()
    db.refresh(l)
    return _liq_dict(l)


# ── Eliminar (soft delete + reverso) ───────────────────────────────

@router.delete("/{liq_id}")
def eliminar_tarjeta(
    liq_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("delete_records")),
):
    l = db.query(LiquidacionTarjeta).filter(
        LiquidacionTarjeta.id == liq_id,
        LiquidacionTarjeta.deleted_at.is_(None),
    ).first()
    if not l:
        raise HTTPException(404, "Liquidación no encontrada")
    if not current_user.is_superadmin and l.organizacion_id != (current_user.organizacion_id or 1):
        raise HTTPException(403, "Sin acceso")

    motivo = f"Liquidación tarjeta #{liq_id} eliminada por {current_user.email}"
    reversar_asientos(db, modulo="tarjeta_liq", referencia_id=liq_id,
                      org_id=l.organizacion_id, usuario_id=current_user.id, motivo=motivo)

    l.deleted_at = datetime.utcnow()
    l.estado = "anulada"
    registrar_log(db, current_user.id, "tarjetas", liq_id, "DELETE",
                  {"marca": l.marca.value if isinstance(l.marca, MarcaTarjeta) else l.marca,
                   "monto_bruto": float(l.monto_bruto)})
    db.commit()
    return {"ok": True}
