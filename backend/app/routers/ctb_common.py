"""Helpers compartidos para los sub-módulos de contabilidad."""
from typing import Optional

from sqlalchemy.orm import Session

from app.middleware.auth import can_switch_org
from app.models.contabilidad import PlanCuenta
from app.models.user import User

# Código del nodo padre de cuentas de clientes en el plan de cuentas
_CLIENTE_PARENT_COD = "2-1-2-0"

# Statuses que se consideran conciliados (para backfill/reset)
_STATUS_CONCILIADO = ("ok", "OK", "PAGO_PARCIAL", "CONCILIADO_CON_DIFERENCIA")

# modulo del asiento → (categoría de filtro, etiqueta legible)
_MODULO_TIPO = {
    "um_reclass":             ("banco",   "Conciliación (TT)"),
    "um_reclass_planilla":    ("banco",   "Transferencia (TT)"),
    "cc_inicial":             ("banco",   "Acreditación (histórico)"),
    "planilla":               ("banco",   "Planilla (legacy)"),
    "planilla_comision":      ("banco",   "Comisión planilla (legacy)"),
    "cheque_carga":           ("cheques", "Cheque"),
    "cheque_rechazo":         ("cheques", "Cheque rechazado"),
    "cheque_registro":        ("cheques", "Cheque registrado"),
    "cheque_acred_banco":     ("cheques", "Cheque acreditado (banco)"),
    "cheque_acred_cliente":   ("cheques", "Cheque acreditado"),
    "cheque_rechazo_banco":   ("cheques", "Cheque rechazado (reversión)"),
    "cheque_rechazo_cliente": ("cheques", "Gastos rechazo cheque"),
    "cheque_rechazo_gasto":   ("cheques", "Débito bancario rechazo"),
    "egreso":                 ("ajustes", "Pago / Egreso"),
    "liquidacion_aprobacion": ("ajustes", "Liquidación aprobada"),
}


def _org_id(current_user: User, org_id: Optional[int]) -> int:
    if can_switch_org(current_user, org_id) and org_id:
        return org_id
    return current_user.organizacion_id or 1


def _cuenta_parent_cliente(db: Session, oid: int) -> Optional[PlanCuenta]:
    return (
        db.query(PlanCuenta)
        .filter(PlanCuenta.codigo == _CLIENTE_PARENT_COD, PlanCuenta.organizacion_id == oid)
        .first()
    )


def _norm_nombre(s: str) -> str:
    """Normaliza nombre para comparación: NFKD, sin diacríticos, minúsculas."""
    import unicodedata as _ud
    if not s:
        return ''
    s = _ud.normalize('NFKD', s)
    s = ''.join(c for c in s if not _ud.combining(c))
    return s.lower().strip()


def _tipo_de_modulo(modulo: str):
    base = modulo[:-len("_reverso")] if modulo.endswith("_reverso") else modulo
    cat, label = _MODULO_TIPO.get(base, ("ajustes", base))
    if modulo.endswith("_reverso"):
        label = f"Reverso: {label}"
    return cat, label
