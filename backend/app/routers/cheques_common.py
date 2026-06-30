"""Helpers y schemas compartidos por los sub-módulos de cheques."""
from datetime import date
from typing import Optional, List

from pydantic import BaseModel, Field

from app.middleware.auth import can_switch_org
from app.models.cheque import Cheque
from app.models.user import User


# ── Schemas ───────────────────────────────────────────────────────

class ChequeIn(BaseModel):
    cliente_id:          Optional[int]   = None
    portador_id:         Optional[int]   = None
    numero:              Optional[str]   = None
    banco_origen:        Optional[str]   = None
    librador:            Optional[str]   = None
    monto:               float           = Field(..., gt=0)
    comision:            float           = Field(0.0, ge=0)
    porcentaje_comision: Optional[float] = None
    codigo_postal:       Optional[str]   = None
    local_interior:      Optional[str]   = None
    fecha_emision:       Optional[date]  = None
    fecha_deposito:      Optional[date]  = None
    notas:               Optional[str]   = None


class AcreditarIn(BaseModel):
    fecha_acred:    Optional[date] = None
    banco_cuenta_id: int           = Field(..., description="ID de la cuenta de banco (plan_cuentas)")


class AcreditarMasivoIn(BaseModel):
    cheque_ids:     List[int]
    banco_cuenta_id: int
    fecha_acred:    Optional[date] = None


class RechazarIn(BaseModel):
    fecha_rechazo:    Optional[date] = None
    gastos_bancarios: float          = Field(0.0, ge=0)
    fisico:           bool           = False
    fecha_devolucion: Optional[date] = None


class PortadorIn(BaseModel):
    nombre: str


class BulkOcrItem(BaseModel):
    index:          int
    filename:       str
    numero:         Optional[str]   = None
    banco_origen:   Optional[str]   = None
    librador:       Optional[str]   = None
    monto:          Optional[float] = None
    fecha_emision:  Optional[str]   = None
    fecha_deposito: Optional[str]   = None
    codigo_postal:  Optional[str]   = None
    local_interior: Optional[str]   = None
    error:          bool            = False
    error_msg:      Optional[str]   = None


class BulkCrearItem(BaseModel):
    cliente_id:          Optional[int]   = None
    portador_id:         Optional[int]   = None
    numero:              Optional[str]   = None
    banco_origen:        Optional[str]   = None
    librador:            Optional[str]   = None
    monto:               float           = Field(..., gt=0)
    porcentaje_comision: Optional[float] = None
    codigo_postal:       Optional[str]   = None
    local_interior:      Optional[str]   = None
    fecha_emision:       Optional[str]   = None
    fecha_deposito:      Optional[str]   = None
    notas:               Optional[str]   = None


class BulkCrearIn(BaseModel):
    items:  List[BulkCrearItem]
    org_id: Optional[int] = None


class FotoIn(BaseModel):
    foto_base64: str


# ── Helpers ───────────────────────────────────────────────────────

def _org_id(current_user: User, org_id: Optional[int]) -> int:
    if can_switch_org(current_user, org_id) and org_id:
        return org_id
    return current_user.organizacion_id or 1


def _local_interior(codigo_postal: Optional[str]) -> Optional[str]:
    if not codigo_postal:
        return None
    try:
        return "local" if int(codigo_postal) < 2000 else "interior"
    except (ValueError, TypeError):
        return None


def _cheque_dict(c: Cheque) -> dict:
    librador = c.librador or c.titular  # fallback para registros anteriores
    return {
        "id":                  c.id,
        "organizacion_id":     c.organizacion_id,
        "cliente_id":          c.cliente_id,
        "cliente_nombre":      c.cliente.nombre if c.cliente else None,
        "portador_id":         c.portador_id,
        "portador_nombre":     c.portador.nombre if c.portador else None,
        "numero":              c.numero,
        "banco_origen":        c.banco_origen,
        "librador":            librador,
        "monto":               c.monto,
        "comision":            c.comision,
        "porcentaje_comision": float(c.porcentaje_comision) if c.porcentaje_comision is not None else None,
        "codigo_postal":       c.codigo_postal,
        "local_interior":      c.local_interior,
        "fecha_emision":       c.fecha_emision,
        "fecha_deposito":      c.fecha_deposito,
        "fecha_acred":         c.fecha_acred,
        "estado":              c.estado,
        "fecha_rechazo":       c.fecha_rechazo,
        "fisico":              c.fisico,
        "fecha_devolucion":    c.fecha_devolucion,
        "notas":               c.notas,
        "tiene_foto":          bool(c.foto_comprobante),
        "banco_cuenta_id":     c.banco_cuenta_id,
        "created_at":          c.created_at,
    }


def _parse_date(v) -> Optional[date]:
    if v is None:
        return None
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v)[:10])
    except Exception:
        return None
