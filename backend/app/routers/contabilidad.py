from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from typing import Optional
from pydantic import BaseModel
import logging

from app.database import get_db
from app.middleware.auth import get_current_user, require_permission
from app.models.user import User
from app.models.cliente import Cliente
from app.models.contabilidad import PlanCuenta, ReglaContable, Asiento, AsientoDetalle

router = APIRouter(prefix="/contabilidad", tags=["contabilidad"])
logger = logging.getLogger(__name__)


@router.get("/stats")
def get_stats(
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Conteos del módulo contable."""
    oid = _org_id(current_user, org_id)
    return {
        "plan_cuentas":    db.query(PlanCuenta).filter(PlanCuenta.organizacion_id == oid).count(),
        "reglas":          db.query(ReglaContable).filter(ReglaContable.organizacion_id == oid).count(),
        "asientos":        db.query(Asiento).filter(Asiento.organizacion_id == oid).count(),
        "asiento_detalle": db.query(AsientoDetalle).join(Asiento).filter(Asiento.organizacion_id == oid).count(),
    }


def _org_id(current_user: User, org_id: Optional[int]) -> int:
    if current_user.is_superadmin and org_id:
        return org_id
    return current_user.organizacion_id or 1


@router.get("/plan-cuentas")
def get_plan_cuentas(
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    oid = _org_id(current_user, org_id)
    cuentas = (
        db.query(PlanCuenta)
        .filter(PlanCuenta.organizacion_id == oid, PlanCuenta.activo == True)
        .order_by(PlanCuenta.codigo)
        .all()
    )
    return [
        {
            "id": c.id,
            "codigo": c.codigo,
            "nombre": c.nombre,
            "tipo": c.tipo,
            "parent_id": c.parent_id,
            "nivel": c.nivel,
            "activo": c.activo,
        }
        for c in cuentas
    ]


@router.get("/reglas")
def get_reglas(
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    oid = _org_id(current_user, org_id)
    reglas = (
        db.query(ReglaContable)
        .filter(ReglaContable.organizacion_id == oid, ReglaContable.activo == True)
        .order_by(ReglaContable.evento)
        .all()
    )
    return [
        {
            "id": r.id,
            "evento": r.evento,
            "descripcion": r.descripcion,
            "debe": {
                "id": r.cuenta_debe.id,
                "codigo": r.cuenta_debe.codigo,
                "nombre": r.cuenta_debe.nombre,
            },
            "haber": {
                "id": r.cuenta_haber.id,
                "codigo": r.cuenta_haber.codigo,
                "nombre": r.cuenta_haber.nombre,
            },
        }
        for r in reglas
    ]


@router.get("/asientos")
def get_asientos(
    org_id: Optional[int] = Query(None),
    desde: Optional[str] = Query(None),
    hasta: Optional[str] = Query(None),
    modulo: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    oid = _org_id(current_user, org_id)
    q = db.query(Asiento).filter(Asiento.organizacion_id == oid)
    if desde:
        q = q.filter(Asiento.fecha >= desde)
    if hasta:
        q = q.filter(Asiento.fecha <= hasta)
    if modulo:
        q = q.filter(Asiento.modulo == modulo)
    total = q.count()
    items = q.order_by(Asiento.fecha.desc(), Asiento.id.desc()).offset(skip).limit(limit).all()
    return {
        "total": total,
        "items": [
            {
                "id": a.id,
                "fecha": a.fecha,
                "descripcion": a.descripcion,
                "modulo": a.modulo,
                "referencia_id": a.referencia_id,
                "created_at": a.created_at,
            }
            for a in items
        ],
    }


@router.get("/asientos/{asiento_id}")
def get_asiento_detalle(
    asiento_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    oid = current_user.organizacion_id or 1
    a = db.query(Asiento).filter(Asiento.id == asiento_id).first()
    if not a:
        raise HTTPException(404, "Asiento no encontrado")
    if not current_user.is_superadmin and a.organizacion_id != oid:
        raise HTTPException(403, "Sin acceso")
    return {
        "id": a.id,
        "fecha": a.fecha,
        "descripcion": a.descripcion,
        "modulo": a.modulo,
        "referencia_id": a.referencia_id,
        "created_at": a.created_at,
        "lineas": [
            {
                "id": l.id,
                "cuenta": {
                    "id": l.cuenta.id,
                    "codigo": l.cuenta.codigo,
                    "nombre": l.cuenta.nombre,
                },
                "debe": l.debe,
                "haber": l.haber,
            }
            for l in a.lineas
        ],
    }


# ── Fase 3: Reportes contables ────────────────────────────────────────────────

@router.get("/libro-mayor")
def get_libro_mayor(
    cuenta_id: int = Query(..., description="ID de la cuenta a consultar"),
    desde: Optional[str] = Query(None),
    hasta: Optional[str] = Query(None),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Movimientos de una cuenta con saldo acumulado (libro mayor)."""
    oid = _org_id(current_user, org_id)
    cuenta = db.query(PlanCuenta).filter(PlanCuenta.id == cuenta_id).first()
    if not cuenta:
        raise HTTPException(404, "Cuenta no encontrada")
    if cuenta.organizacion_id != oid:
        raise HTTPException(403, "Cuenta no pertenece a la organización")

    q = (
        db.query(AsientoDetalle, Asiento)
        .join(Asiento, AsientoDetalle.asiento_id == Asiento.id)
        .filter(
            AsientoDetalle.cuenta_id == cuenta_id,
            Asiento.organizacion_id == oid,
        )
    )
    if desde:
        q = q.filter(Asiento.fecha >= desde)
    if hasta:
        q = q.filter(Asiento.fecha <= hasta)
    q = q.order_by(Asiento.fecha, Asiento.id)

    movimientos = []
    saldo = 0.0
    for detalle, asiento in q.all():
        saldo += detalle.debe - detalle.haber
        movimientos.append({
            "fecha":       asiento.fecha,
            "descripcion": asiento.descripcion,
            "modulo":      asiento.modulo,
            "debe":        detalle.debe,
            "haber":       detalle.haber,
            "saldo":       round(saldo, 2),
        })

    return {
        "cuenta": {"id": cuenta.id, "codigo": cuenta.codigo, "nombre": cuenta.nombre, "tipo": cuenta.tipo},
        "movimientos": movimientos,
        "total_debe":  round(sum(m["debe"]  for m in movimientos), 2),
        "total_haber": round(sum(m["haber"] for m in movimientos), 2),
        "saldo_final": round(saldo, 2),
    }


@router.get("/sumas-saldo")
def get_sumas_saldo(
    desde: Optional[str] = Query(None),
    hasta: Optional[str] = Query(None),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sumas y saldo: total debe/haber por cuenta."""
    oid = _org_id(current_user, org_id)

    q = (
        db.query(
            PlanCuenta.id,
            PlanCuenta.codigo,
            PlanCuenta.nombre,
            PlanCuenta.tipo,
            PlanCuenta.nivel,
            func.coalesce(func.sum(AsientoDetalle.debe),  0.0).label("total_debe"),
            func.coalesce(func.sum(AsientoDetalle.haber), 0.0).label("total_haber"),
        )
        .join(AsientoDetalle, AsientoDetalle.cuenta_id == PlanCuenta.id)
        .join(Asiento, AsientoDetalle.asiento_id == Asiento.id)
        .filter(Asiento.organizacion_id == oid)
    )
    if desde:
        q = q.filter(Asiento.fecha >= desde)
    if hasta:
        q = q.filter(Asiento.fecha <= hasta)
    q = q.group_by(
        PlanCuenta.id, PlanCuenta.codigo, PlanCuenta.nombre,
        PlanCuenta.tipo, PlanCuenta.nivel,
    ).order_by(PlanCuenta.codigo)

    rows = []
    for r in q.all():
        debe  = round(r.total_debe or 0,  2)
        haber = round(r.total_haber or 0, 2)
        saldo = round(debe - haber, 2)
        rows.append({
            "id":     r.id,
            "codigo": r.codigo,
            "nombre": r.nombre,
            "tipo":   r.tipo,
            "nivel":  r.nivel,
            "total_debe":    debe,
            "total_haber":   haber,
            "saldo_deudor":  max(saldo, 0),
            "saldo_acreedor": max(-saldo, 0),
        })
    return rows


@router.get("/balance")
def get_balance(
    desde: Optional[str] = Query(None),
    hasta: Optional[str] = Query(None),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Balance simplificado: totales por tipo de cuenta."""
    oid = _org_id(current_user, org_id)

    q = (
        db.query(
            PlanCuenta.tipo,
            func.coalesce(func.sum(AsientoDetalle.debe),  0.0).label("total_debe"),
            func.coalesce(func.sum(AsientoDetalle.haber), 0.0).label("total_haber"),
        )
        .join(AsientoDetalle, AsientoDetalle.cuenta_id == PlanCuenta.id)
        .join(Asiento, AsientoDetalle.asiento_id == Asiento.id)
        .filter(Asiento.organizacion_id == oid, PlanCuenta.tipo.isnot(None))
    )
    if desde:
        q = q.filter(Asiento.fecha >= desde)
    if hasta:
        q = q.filter(Asiento.fecha <= hasta)
    q = q.group_by(PlanCuenta.tipo)

    totales: dict = {}
    for r in q.all():
        debe  = round(r.total_debe or 0,  2)
        haber = round(r.total_haber or 0, 2)
        totales[r.tipo] = {
            "total_debe":  debe,
            "total_haber": haber,
            "saldo":       round(debe - haber, 2),
        }

    activo    = totales.get("activo",    {}).get("saldo", 0)
    pasivo    = totales.get("pasivo",    {}).get("saldo", 0)
    resultado = totales.get("resultado", {}).get("saldo", 0)

    return {
        "activo":    totales.get("activo",    {"total_debe": 0, "total_haber": 0, "saldo": 0}),
        "pasivo":    totales.get("pasivo",    {"total_debe": 0, "total_haber": 0, "saldo": 0}),
        "resultado": totales.get("resultado", {"total_debe": 0, "total_haber": 0, "saldo": 0}),
        "ecuacion_ok": round(activo, 2) == round(abs(pasivo) + abs(resultado), 2),
    }


# ── Vinculación manual Cliente → cuenta contable ──────────────────────────────

_CLIENTE_PARENT_COD = "2-1-2-0"


def _cuenta_parent_cliente(db: Session, oid: int) -> Optional[PlanCuenta]:
    return (
        db.query(PlanCuenta)
        .filter(PlanCuenta.codigo == _CLIENTE_PARENT_COD, PlanCuenta.organizacion_id == oid)
        .first()
    )


@router.get("/clientes-cuentas")
def get_clientes_cuentas(
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lista clientes con su cuenta contable vinculada (o NULL) + las cuentas
    disponibles bajo 2-1-2-0 para asignación manual."""
    oid = _org_id(current_user, org_id)
    padre = _cuenta_parent_cliente(db, oid)
    cuentas_cliente = []
    if padre:
        cuentas_cliente = (
            db.query(PlanCuenta)
            .filter(PlanCuenta.parent_id == padre.id, PlanCuenta.organizacion_id == oid)
            .order_by(PlanCuenta.codigo)
            .all()
        )
    cuentas_by_id = {c.id: c for c in cuentas_cliente}

    clientes = (
        db.query(Cliente)
        .filter(Cliente.organizacion_id == oid)
        .order_by(Cliente.nombre)
        .all()
    )
    items = []
    for cli in clientes:
        cuenta = cuentas_by_id.get(cli.cuenta_contable_id)
        if cli.cuenta_contable_id and not cuenta:
            cuenta = db.query(PlanCuenta).filter(PlanCuenta.id == cli.cuenta_contable_id).first()
        items.append({
            "cliente_id": cli.id,
            "cliente_nombre": cli.nombre,
            "cuenta": {"id": cuenta.id, "codigo": cuenta.codigo, "nombre": cuenta.nombre} if cuenta else None,
        })

    return {
        "clientes": items,
        "cuentas_disponibles": [
            {"id": c.id, "codigo": c.codigo, "nombre": c.nombre} for c in cuentas_cliente
        ],
    }


class VincularCuentaBody(BaseModel):
    cuenta_id: Optional[int] = None  # None = desvincular


@router.put("/clientes/{cliente_id}/cuenta")
def vincular_cuenta_cliente(
    cliente_id: int,
    body: VincularCuentaBody,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin_accounting")),
):
    """Asigna una cuenta existente a un cliente, corrige una vinculación o
    desvincula (cuenta_id=null). La cuenta debe colgar de 2-1-2-0 y no estar
    ya tomada por otro cliente (vínculo 1:1)."""
    oid = _org_id(current_user, org_id)
    cli = db.query(Cliente).filter(Cliente.id == cliente_id, Cliente.organizacion_id == oid).first()
    if not cli:
        raise HTTPException(404, "Cliente no encontrado")

    if body.cuenta_id is None:
        cli.cuenta_contable_id = None
        db.commit()
        return {"ok": True, "cliente_id": cliente_id, "cuenta": None}

    padre = _cuenta_parent_cliente(db, oid)
    cuenta = db.query(PlanCuenta).filter(PlanCuenta.id == body.cuenta_id, PlanCuenta.organizacion_id == oid).first()
    if not cuenta:
        raise HTTPException(404, "Cuenta no encontrada")
    if not padre or cuenta.parent_id != padre.id:
        raise HTTPException(400, "La cuenta debe ser una subcuenta de Cliente (2-1-2-0)")

    ocupada_por = (
        db.query(Cliente)
        .filter(Cliente.cuenta_contable_id == cuenta.id, Cliente.id != cliente_id, Cliente.organizacion_id == oid)
        .first()
    )
    if ocupada_por:
        raise HTTPException(409, f"La cuenta {cuenta.codigo} ya está vinculada a '{ocupada_por.nombre}'")

    cli.cuenta_contable_id = cuenta.id
    db.commit()
    return {"ok": True, "cliente_id": cliente_id, "cuenta": {"id": cuenta.id, "codigo": cuenta.codigo, "nombre": cuenta.nombre}}


class CrearCuentaBody(BaseModel):
    nombre: Optional[str] = None  # default: nombre del cliente


@router.post("/clientes/{cliente_id}/cuenta/crear")
def crear_y_vincular_cuenta(
    cliente_id: int,
    body: CrearCuentaBody,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin_accounting")),
):
    """Crea una cuenta nueva bajo 2-1-2-0 con el próximo código y la vincula al
    cliente. El cliente no debe tener cuenta previa (usar PUT para corregir)."""
    oid = _org_id(current_user, org_id)
    cli = db.query(Cliente).filter(Cliente.id == cliente_id, Cliente.organizacion_id == oid).first()
    if not cli:
        raise HTTPException(404, "Cliente no encontrado")
    if cli.cuenta_contable_id:
        raise HTTPException(409, "El cliente ya tiene cuenta vinculada; usá corregir/desvincular primero")

    padre = _cuenta_parent_cliente(db, oid)
    if not padre:
        raise HTTPException(400, "No existe la cuenta padre Cliente (2-1-2-0)")

    nombre = (body.nombre or cli.nombre or "").strip().title()
    if not nombre:
        raise HTTPException(400, "Nombre de cuenta requerido")

    hijos = db.query(PlanCuenta).filter(PlanCuenta.parent_id == padre.id, PlanCuenta.organizacion_id == oid).all()
    max_n = 0
    for h in hijos:
        try:
            max_n = max(max_n, int(h.codigo.rsplit("-", 1)[-1]))
        except (ValueError, IndexError):
            pass
    nuevo_codigo = f"2-1-2-{max_n + 1}"
    cuenta = PlanCuenta(
        codigo=nuevo_codigo, nombre=nombre, tipo="pasivo",
        parent_id=padre.id, nivel=(padre.nivel or 3) + 1,
        activo=True, organizacion_id=oid,
    )
    db.add(cuenta)
    db.flush()
    cli.cuenta_contable_id = cuenta.id
    db.commit()
    return {"ok": True, "cliente_id": cliente_id, "cuenta": {"id": cuenta.id, "codigo": cuenta.codigo, "nombre": cuenta.nombre}}


# ── Cuenta corriente del cliente (vista derivada de asientos) ─────────────────

# modulo del asiento → (categoría de filtro, etiqueta legible)
_MODULO_TIPO = {
    "um_reclass":        ("banco",   "Conciliación bancaria (UM)"),
    "planilla":          ("tt",      "Transferencia (TT)"),
    "planilla_comision": ("tt",      "Comisión TT"),
    "cheque_carga":      ("cheques", "Cheque"),
    "cheque_rechazo":    ("cheques", "Cheque rechazado"),
    "pago":              ("ajustes", "Cobranza / Pago"),
}


def _tipo_de_modulo(modulo: str):
    base = modulo[:-len("_reverso")] if modulo.endswith("_reverso") else modulo
    cat, label = _MODULO_TIPO.get(base, ("ajustes", base))
    if modulo.endswith("_reverso"):
        label = f"Reverso: {label}"
    return cat, label


@router.get("/cuenta-corriente")
def get_cuenta_corriente(
    cliente_id: int = Query(..., description="ID del cliente"),
    desde: Optional[str] = Query(None),
    hasta: Optional[str] = Query(None),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage_finance")),
):
    """Cuenta corriente del cliente: línea de tiempo financiera unificada,
    derivada de los asientos que impactan su cuenta contable. NO genera asientos."""
    oid = _org_id(current_user, org_id)
    cli = db.query(Cliente).filter(Cliente.id == cliente_id, Cliente.organizacion_id == oid).first()
    if not cli:
        raise HTTPException(404, "Cliente no encontrado")
    if not cli.cuenta_contable_id:
        return {
            "cliente": {"id": cli.id, "nombre": cli.nombre},
            "cuenta": None, "sin_cuenta": True, "movimientos": [],
            "total_debito": 0, "total_credito": 0, "saldo_final": 0,
        }
    cuenta = db.query(PlanCuenta).filter(PlanCuenta.id == cli.cuenta_contable_id).first()

    q = (
        db.query(AsientoDetalle, Asiento)
        .join(Asiento, AsientoDetalle.asiento_id == Asiento.id)
        .filter(AsientoDetalle.cuenta_id == cli.cuenta_contable_id, Asiento.organizacion_id == oid)
    )
    if desde:
        q = q.filter(Asiento.fecha >= desde)
    if hasta:
        q = q.filter(Asiento.fecha <= hasta)
    filas = q.order_by(Asiento.fecha, Asiento.id).all()

    # Set de asientos revertidos (existe un *_reverso que los referencia)
    asiento_ids = [a.id for _, a in filas]
    reversados = set()
    if asiento_ids:
        for (ref,) in (
            db.query(Asiento.referencia_id)
            .filter(Asiento.organizacion_id == oid, Asiento.modulo.like("%_reverso"),
                    Asiento.referencia_id.in_(asiento_ids))
            .all()
        ):
            reversados.add(ref)

    # Batch: PlanillaRow para um_reclass (referencia_id = planilla_row_id)
    row_ids = [a.referencia_id for _, a in filas if (a.modulo or "").startswith("um_reclass") and a.referencia_id]
    row_map = {}
    if row_ids:
        from app.models.planilla import PlanillaRow
        for r in db.query(PlanillaRow).filter(PlanillaRow.id.in_(row_ids)).all():
            row_map[r.id] = {"planilla_id": r.planilla_id, "movimiento_id": r.orden_movimiento_acreditado}

    # Batch: extracto_id de los movimientos referidos
    mov_ids = [v["movimiento_id"] for v in row_map.values() if v["movimiento_id"]]
    mov_map = {}
    if mov_ids:
        from app.models.extracto import MovimientoBanco
        for m in db.query(MovimientoBanco.id, MovimientoBanco.extracto_id).filter(MovimientoBanco.id.in_(mov_ids)).all():
            mov_map[m.id] = m.extracto_id

    movimientos = []
    saldo = 0.0
    for det, a in filas:
        debe = float(det.debe or 0)
        haber = float(det.haber or 0)
        saldo += debe - haber
        modulo = a.modulo or ""
        cat, label = _tipo_de_modulo(modulo)

        # Estado operativo de imputación (NO refleja errores de integridad)
        es_reverso = modulo.endswith("_reverso")
        origen = {"asiento_id": a.id}
        estado = "Conciliado"
        if es_reverso or a.id in reversados:
            estado = "Revertido"
        elif modulo.startswith("um_reclass"):
            info = row_map.get(a.referencia_id)
            if not info or not info.get("movimiento_id"):
                # Trazabilidad rota → validación/log, NO un estado operativo
                logger.warning(
                    "Cta.cte. cliente %s: asiento %s (um_reclass) sin movimiento bancario vinculado",
                    cliente_id, a.id,
                )
            else:
                origen["planilla_id"] = info["planilla_id"]
                origen["movimiento_id"] = info["movimiento_id"]
                origen["extracto_id"] = mov_map.get(info["movimiento_id"])
        elif modulo.startswith("planilla"):
            origen["planilla_id"] = a.referencia_id
        elif modulo.startswith("cheque"):
            origen["cheque_id"] = a.referencia_id
        elif modulo.startswith("pago"):
            origen["pago_id"] = a.referencia_id

        movimientos.append({
            "fecha": a.fecha,
            "tipo_cat": cat,
            "tipo_label": label,
            "referencia": a.descripcion or "—",
            "debito": round(debe, 2),
            "credito": round(haber, 2),
            "saldo": round(saldo, 2),
            "estado": estado,
            "origen": origen,
        })

    return {
        "cliente": {"id": cli.id, "nombre": cli.nombre},
        "cuenta": {"id": cuenta.id, "codigo": cuenta.codigo, "nombre": cuenta.nombre} if cuenta else None,
        "sin_cuenta": False,
        "movimientos": movimientos,
        "total_debito": round(sum(m["debito"] for m in movimientos), 2),
        "total_credito": round(sum(m["credito"] for m in movimientos), 2),
        "saldo_final": round(saldo, 2),
    }


@router.get("/cuentas-corrientes")
def get_cuentas_corrientes(
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage_finance")),
):
    """Vista global de cartera: saldo, último movimiento y estado por cliente.
    Vista derivada de los asientos sobre cada cuenta 2-1-2-X. No genera asientos."""
    oid = _org_id(current_user, org_id)
    clientes = (
        db.query(Cliente)
        .filter(Cliente.organizacion_id == oid, Cliente.cuenta_contable_id.isnot(None))
        .order_by(Cliente.nombre)
        .all()
    )
    cuenta_ids = [c.cuenta_contable_id for c in clientes]

    cuentas_by_id = {}
    agg = {}      # cuenta_id → {debe, haber}
    ult = {}      # cuenta_id → fecha último movimiento
    if cuenta_ids:
        for c in db.query(PlanCuenta).filter(PlanCuenta.id.in_(cuenta_ids)).all():
            cuentas_by_id[c.id] = c
        rows = (
            db.query(
                AsientoDetalle.cuenta_id,
                func.coalesce(func.sum(AsientoDetalle.debe), 0.0),
                func.coalesce(func.sum(AsientoDetalle.haber), 0.0),
                func.max(Asiento.fecha),
            )
            .join(Asiento, AsientoDetalle.asiento_id == Asiento.id)
            .filter(AsientoDetalle.cuenta_id.in_(cuenta_ids), Asiento.organizacion_id == oid)
            .group_by(AsientoDetalle.cuenta_id)
            .all()
        )
        for cuenta_id, debe, haber, fecha_max in rows:
            agg[cuenta_id] = {"debe": float(debe or 0), "haber": float(haber or 0)}
            ult[cuenta_id] = fecha_max

    items = []
    for cli in clientes:
        cuenta = cuentas_by_id.get(cli.cuenta_contable_id)
        a = agg.get(cli.cuenta_contable_id)
        debe = a["debe"] if a else 0.0
        haber = a["haber"] if a else 0.0
        saldo = round(debe - haber, 2)
        tiene_actividad = a is not None
        if not tiene_actividad:
            estado_general = "sin_actividad"
        elif saldo > 0:
            estado_general = "deudor"
        elif saldo < 0:
            estado_general = "acreedor"
        else:
            estado_general = "equilibrado"
        items.append({
            "cliente_id": cli.id,
            "cliente_nombre": cli.nombre,
            "cuenta": {"id": cuenta.id, "codigo": cuenta.codigo, "nombre": cuenta.nombre} if cuenta else None,
            "saldo": saldo,
            "ultimo_movimiento": ult.get(cli.cuenta_contable_id),
            "estado_general": estado_general,
            "conciliacion": "sin_actividad" if not tiene_actividad else "conciliado",
        })

    return {
        "items": items,
        "total_deudor": round(sum(i["saldo"] for i in items if i["saldo"] > 0), 2),
        "total_acreedor": round(sum(-i["saldo"] for i in items if i["saldo"] < 0), 2),
    }
