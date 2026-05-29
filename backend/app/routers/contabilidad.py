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


@router.post("/clientes/cuentas/crear-faltantes")
def crear_cuentas_faltantes(
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin_accounting")),
):
    """Crea/vincula la cuenta contable (2-1-2-X) de todos los clientes que aún
    no tienen una. Reutiliza una cuenta existente con el mismo nombre si la hay
    (no duplica); si no, crea la próxima. Acción explícita, idempotente."""
    oid = _org_id(current_user, org_id)
    padre = _cuenta_parent_cliente(db, oid)
    if not padre:
        raise HTTPException(400, "No existe la cuenta padre Cliente (2-1-2-0)")

    from app.services.motor_contable import _get_o_crear_cuenta_cliente

    sin_cuenta = (
        db.query(Cliente)
        .filter(Cliente.organizacion_id == oid, Cliente.cuenta_contable_id.is_(None))
        .order_by(Cliente.nombre)
        .all()
    )
    creados = []
    for cli in sin_cuenta:
        try:
            cuenta = _get_o_crear_cuenta_cliente(db, cli.id, oid)
            if cuenta:
                creados.append({"cliente": cli.nombre, "codigo": cuenta.codigo})
        except Exception as ex:
            logger.warning("crear cuenta cliente %s: %s", cli.id, ex)
    db.commit()
    return {"ok": True, "creados": creados, "total": len(creados), "sin_cuenta_previa": len(sin_cuenta)}


_STATUS_CONCILIADO = ("ok", "OK", "PAGO_PARCIAL", "CONCILIADO_CON_DIFERENCIA")


@router.post("/backfill-cuentas-corrientes")
def backfill_cuentas_corrientes(
    dry_run: bool = Query(False, description="Solo cuenta cuántas filas se procesarían, sin escribir"),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin_accounting")),
):
    """Reconstruye las cuentas corrientes desde las conciliaciones ya cargadas.
    Por cada fila de planilla conciliada (status ok) de un cliente con cuenta,
    genera un asiento neto Banco Macro (D) / Cliente (H). Idempotente: saltea las
    filas que ya tienen asiento del flujo normal (um_reclass) o un cc_inicial previo."""
    from decimal import Decimal as _D
    from datetime import date as _date
    from app.models.planilla import Planilla, PlanillaRow
    from app.services.motor_contable import _get_cuenta_por_codigo, _get_o_crear_cuenta_cliente, _monto

    oid = _org_id(current_user, org_id)

    # Filas conciliadas de clientes CON cuenta contable
    rows = (
        db.query(PlanillaRow, Planilla, Cliente)
        .join(Planilla, PlanillaRow.planilla_id == Planilla.id)
        .join(Cliente, Planilla.cliente_id == Cliente.id)
        .filter(
            Planilla.organizacion_id == oid,
            Planilla.deleted_at.is_(None),
            PlanillaRow.status.in_(list(_STATUS_CONCILIADO)),
            Cliente.cuenta_contable_id.isnot(None),
        )
        .all()
    )

    # Filas conciliadas de clientes SIN cuenta (excluidas del backfill)
    sin_cuenta_count = (
        db.query(PlanillaRow)
        .join(Planilla, PlanillaRow.planilla_id == Planilla.id)
        .join(Cliente, Planilla.cliente_id == Cliente.id)
        .filter(
            Planilla.organizacion_id == oid,
            Planilla.deleted_at.is_(None),
            PlanillaRow.status.in_(list(_STATUS_CONCILIADO)),
            Cliente.cuenta_contable_id.is_(None),
        )
        .count()
    )

    # Idempotencia en batch: filas que ya tienen asiento (normal o backfill previo)
    ya = set(
        r[0] for r in db.query(Asiento.referencia_id)
        .filter(Asiento.organizacion_id == oid, Asiento.modulo.in_(["um_reclass", "cc_inicial"]))
        .all()
    )
    pendientes = [(row, pl, cli) for (row, pl, cli) in rows if row.id not in ya]

    if dry_run:
        monto_est = sum((row.monto or _D(0)) for row, _, _ in pendientes)
        return {
            "dry_run": True,
            "total_filas_ok": len(rows),
            "ya_cubiertas": len(rows) - len(pendientes),
            "pendientes": len(pendientes),
            "monto_estimado": monto_est,
            "clientes": len({pl.cliente_id for _, pl, _ in pendientes}),
            "sin_cuenta_cliente": sin_cuenta_count,
        }

    # Extraer datos escalares antes de cualquier commit (evita expire-on-commit)
    pendiente_data = [
        {
            "row_id": row.id,
            "monto": row.monto,
            "fecha_acred": row.fecha_acred,
            "fecha_carga": pl.fecha_carga,
            "nombre_archivo": pl.nombre_archivo,
            "cliente_id": pl.cliente_id,
            "cliente_nombre": cli.nombre,
        }
        for row, pl, cli in pendientes
    ]

    # Pre-cachear cuenta Banco Macro (1 query en lugar de 1 por fila)
    banco = _get_cuenta_por_codigo(db, "1-1-1-3-1", oid)
    if not banco:
        raise HTTPException(400, "No existe la cuenta Banco Macro (1-1-1-3-1). Verificá el plan de cuentas.")
    banco_id = banco.id

    # Pre-cachear/crear cuentas de clientes únicos (M queries en lugar de N queries)
    clientes_ids = {d["cliente_id"] for d in pendiente_data}
    cuenta_por_cliente: dict = {}
    for cli_id in clientes_ids:
        c = _get_o_crear_cuenta_cliente(db, cli_id, oid)
        if c:
            cuenta_por_cliente[cli_id] = c.id
    db.commit()  # commit de cuentas nuevas si se crearon

    # Crear todos los asientos en una sola transacción (N flushes + 1 commit)
    creados = 0
    clientes_tocados: set = set()
    for d in pendiente_data:
        cuenta_cliente_id = cuenta_por_cliente.get(d["cliente_id"])
        if not cuenta_cliente_id:
            continue
        monto_d = abs(_monto(d["monto"]))
        if monto_d <= 0:
            continue
        fecha_acred = d["fecha_acred"]
        fecha_carga = d["fecha_carga"]
        fecha_asiento = fecha_acred or (fecha_carga.date() if fecha_carga else _date.today())
        desc = f"Acreditación histórica — {d['cliente_nombre']}"
        if d["nombre_archivo"]:
            desc += f" ({d['nombre_archivo']})"
        a = Asiento(
            fecha=fecha_asiento,
            descripcion=desc,
            modulo="cc_inicial",
            referencia_id=d["row_id"],
            organizacion_id=oid,
            usuario_id=current_user.id,
        )
        db.add(a)
        db.flush()  # necesario para obtener a.id
        db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=banco_id, debe=monto_d, haber=_D("0")))
        db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=cuenta_cliente_id, debe=_D("0"), haber=monto_d))
        creados += 1
        clientes_tocados.add(d["cliente_id"])

    db.commit()  # un solo commit para todos los asientos

    return {
        "ok": True,
        "creados": creados,
        "clientes": len(clientes_tocados),
        "total_filas_ok": len(rows),
        "ya_cubiertas": len(rows) - len(pendientes),
    }


# ── Recuperación de planillas desde extracto ──────────────────────────────────

def _norm_nombre(s: str) -> str:
    """Normaliza nombre para comparación: NFKD, sin diacríticos, minúsculas."""
    import unicodedata as _ud
    if not s:
        return ''
    s = _ud.normalize('NFKD', s)
    s = ''.join(c for c in s if not _ud.combining(c))
    return s.lower().strip()


@router.post("/planillas-desde-extracto")
def planillas_desde_extracto(
    dry_run: bool = Query(False, description="Solo previsualiza, no crea nada"),
    crear_clientes: bool = Query(False, description="Crear clientes nuevos para movimientos no identificados"),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin_accounting")),
):
    """Recupera planillas faltantes a partir de los movimientos del extracto bancario.
    Por cada movimiento positivo sin planilla vinculada:
      - Si coincide con cliente conocido (nombre normalizado): crea Planilla + PlanillaRow (status=ok).
      - Si crear_clientes=True: crea el cliente del nombre del extracto y luego la planilla.
    Agrupa por cliente × día. Idempotente: el outerjoin garantiza que no se tocan
    movimientos que ya tienen planilla vinculada."""
    from decimal import Decimal as _D
    from datetime import datetime as _dt
    from app.models.extracto import MovimientoBanco, ExtractoBancario
    from app.models.planilla import Planilla, PlanillaRow

    oid = _org_id(current_user, org_id)

    # Movimientos positivos del extracto activo sin planilla row vinculada
    orphaned = (
        db.query(MovimientoBanco)
        .join(ExtractoBancario, MovimientoBanco.extracto_id == ExtractoBancario.id)
        .outerjoin(PlanillaRow, PlanillaRow.orden_movimiento_acreditado == MovimientoBanco.id)
        .filter(
            MovimientoBanco.organizacion_id == oid,
            ExtractoBancario.deleted_at.is_(None),
            MovimientoBanco.monto > 0,
            PlanillaRow.id.is_(None),
        )
        .all()
    )

    # Mapa clientes existentes por nombre normalizado
    cli_by_norm = {
        _norm_nombre(c.nombre): c
        for c in db.query(Cliente).filter(Cliente.organizacion_id == oid).all()
    }

    # Separar movimientos matched (cliente conocido) y unmatched
    matched: list = []   # (mov, cliente)
    nuevos: dict = {}    # norm_nombre -> {nombre_titulo, movs}

    for mov in orphaned:
        cliente = None
        for field in [mov.cliente_acreditado, mov.titular]:
            n = _norm_nombre(field or '')
            if n and n in cli_by_norm:
                cliente = cli_by_norm[n]
                break
        if cliente:
            matched.append((mov, cliente))
        else:
            # Colectar nombre para posible creación de cliente nuevo
            for field in [mov.cliente_acreditado, mov.titular]:
                n = _norm_nombre(field or '')
                if n:
                    if n not in nuevos:
                        nuevos[n] = {"nombre": (field or '').strip().title(), "movs": []}
                    nuevos[n]["movs"].append(mov)
                    break

    def _make_grupos(pairs):
        """Agrupa (mov, cliente) por (cliente_id, fecha_acred) → una planilla por cliente × día.
        Usa fecha_acred preferentemente (fecha real de crédito); fallback a fecha de movimiento."""
        g: dict = {}
        for mov, cli in pairs:
            fecha_cred = mov.fecha_acred or mov.fecha  # fecha real de acreditación
            key = (cli.id, fecha_cred)
            if key not in g:
                g[key] = {"cliente": cli, "movs": [], "extracto_id": mov.extracto_id, "comision": cli.porcentaje_comision}
            g[key]["movs"].append(mov)
        return g

    grupos = _make_grupos(matched)

    # Nombres nuevos ordenados por frecuencia (para el preview)
    nuevos_sorted = sorted(nuevos.items(), key=lambda x: -len(x[1]["movs"]))
    clientes_nuevos_names = [v["nombre"] for _, v in nuevos_sorted[:30]]
    filas_nuevos = sum(len(v["movs"]) for v in nuevos.values())

    if dry_run:
        grupos_list = [
            {
                "cliente_nombre": v["cliente"].nombre,
                "fecha": str(k[1]) if k[1] else "sin-fecha",  # k[1] = fecha_acred or fecha
                "count": len(v["movs"]),
                "monto_total": round(sum(float(m.monto or 0) for m in v["movs"]), 2),
            }
            for k, v in sorted(grupos.items(), key=lambda x: (x[1]["cliente"].nombre, str(x[0][1] or '')))
        ]
        return {
            "dry_run": True,
            "huerfanos": len(orphaned),
            "identificados": len(matched),
            "no_identificados": len(orphaned) - len(matched),
            "clientes": len({m[1].id for m in matched}),
            "planillas_a_crear": len(grupos),
            "filas_a_crear": len(matched),
            "grupos": grupos_list,
            # Info sobre nombres desconocidos (para que el frontend ofrezca crear clientes)
            "clientes_nuevos_count": len(nuevos),
            "clientes_nuevos": clientes_nuevos_names,
            "filas_nuevos": filas_nuevos,
        }

    # Si crear_clientes=True: crear los clientes nuevos primero
    clientes_creados = 0
    if crear_clientes and nuevos:
        for norm, data in nuevos_sorted:
            cli = Cliente(nombre=data["nombre"], organizacion_id=oid)
            db.add(cli)
            db.flush()
            cli_by_norm[norm] = cli
            for mov in data["movs"]:
                matched.append((mov, cli))
            clientes_creados += 1
        grupos = _make_grupos(matched)

    # Crear planillas y rows (una planilla por cliente × día)
    planillas_creadas = 0
    filas_creadas = 0
    clientes_tocados: set = set()

    for (cli_id, fecha_cred), g in grupos.items():
        fecha_str = str(fecha_cred) if fecha_cred else "sin-fecha"
        pl = Planilla(
            cliente_id=cli_id,
            extracto_id=g["extracto_id"],
            usuario_id=current_user.id,
            organizacion_id=oid,
            nombre_archivo=f"Extracto auto-recuperado {fecha_str}",
            fecha_carga=_dt(fecha_cred.year, fecha_cred.month, fecha_cred.day) if fecha_cred else _dt.utcnow(),
            porcentaje_comision=g["comision"],
        )
        db.add(pl)
        db.flush()

        for mov in g["movs"]:
            monto = abs(mov.monto) if mov.monto else _D("0")
            db.add(PlanillaRow(
                planilla_id=pl.id,
                organizacion_id=oid,
                monto=monto,
                titular=mov.titular,
                status='ok',
                fecha_acred=mov.fecha_acred or mov.fecha,  # fecha real de crédito
                monto_acreditado=monto,
                orden_movimiento_acreditado=mov.id,
            ))
            filas_creadas += 1

        planillas_creadas += 1
        clientes_tocados.add(cli_id)

    db.commit()

    logger.info(
        "planillas-desde-extracto: %d planillas, %d filas, %d clientes (%d nuevos) (org %d)",
        planillas_creadas, filas_creadas, len(clientes_tocados), clientes_creados, oid,
    )

    return {
        "ok": True,
        "planillas_creadas": planillas_creadas,
        "filas_creadas": filas_creadas,
        "clientes": len(clientes_tocados),
        "clientes_creados": clientes_creados,
    }


@router.post("/revertir-planillas-extracto")
def revertir_planillas_extracto(
    dry_run: bool = Query(False, description="Solo previsualiza, no borra nada"),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin_accounting")),
):
    """Revierte las planillas creadas automáticamente desde el extracto:
    soft-delete de las planillas 'Extracto auto-recuperado' + reverso de los
    asientos cc_inicial vinculados a sus filas. Deja trazabilidad completa."""
    from datetime import datetime as _dt, date as _date
    from decimal import Decimal as _D
    from app.models.planilla import Planilla, PlanillaRow

    oid = _org_id(current_user, org_id)

    # Planillas auto-recuperadas activas
    planillas = (
        db.query(Planilla)
        .filter(
            Planilla.organizacion_id == oid,
            Planilla.deleted_at.is_(None),
            Planilla.nombre_archivo.like("Extracto auto-recuperado%"),
        )
        .all()
    )

    if not planillas:
        return {"dry_run": dry_run, "planillas": 0, "filas": 0, "asientos_revertidos": 0}

    pl_ids = [p.id for p in planillas]
    filas = db.query(PlanillaRow).filter(PlanillaRow.planilla_id.in_(pl_ids)).all()
    fila_ids = [f.id for f in filas]

    # Asientos cc_inicial vinculados a esas filas (si se corrió reconstruir)
    asientos_cc = (
        db.query(Asiento)
        .filter(
            Asiento.organizacion_id == oid,
            Asiento.modulo == "cc_inicial",
            Asiento.referencia_id.in_(fila_ids) if fila_ids else False,
        )
        .all()
    ) if fila_ids else []

    if dry_run:
        return {
            "dry_run": True,
            "planillas": len(planillas),
            "filas": len(fila_ids),
            "asientos_a_revertir": len(asientos_cc),
        }

    # Crear asientos reverso — un solo flush para todos, evita N roundtrips a la DB
    if asientos_cc:
        # Precargar todos los detalles en una sola query
        asiento_ids_cc = [a.id for a in asientos_cc]
        all_lineas = db.query(AsientoDetalle).filter(
            AsientoDetalle.asiento_id.in_(asiento_ids_cc)
        ).all()
        lineas_por_asiento: dict = {}
        for l in all_lineas:
            lineas_por_asiento.setdefault(l.asiento_id, []).append(l)

        # Crear todos los asientos reverso y un único flush para obtener sus IDs
        reversos = []
        for asiento in asientos_cc:
            reverso = Asiento(
                fecha=_date.today(),
                descripcion=f"Reverso: {asiento.descripcion}",
                modulo="cc_inicial_reverso",
                referencia_id=asiento.id,
                organizacion_id=oid,
                usuario_id=current_user.id,
            )
            db.add(reverso)
            reversos.append((asiento, reverso))
        db.flush()  # un solo roundtrip para obtener todos los IDs

        for asiento, reverso in reversos:
            for l in lineas_por_asiento.get(asiento.id, []):
                db.add(AsientoDetalle(
                    asiento_id=reverso.id,
                    cuenta_id=l.cuenta_id,
                    debe=l.haber,
                    haber=l.debe,
                ))

    # Desvincula movimientos para que queden huérfanos y puedan volver a recuperarse
    for fila in filas:
        fila.orden_movimiento_acreditado = None

    # Soft-delete planillas (las filas quedan en DB para trazabilidad)
    now = _dt.utcnow()
    for pl in planillas:
        pl.deleted_at = now

    db.commit()

    logger.info(
        "revertir-planillas-extracto: %d planillas, %d filas, %d asientos revertidos (org %d)",
        len(planillas), len(fila_ids), len(asientos_cc), oid,
    )

    return {
        "ok": True,
        "planillas": len(planillas),
        "filas": len(fila_ids),
        "asientos_revertidos": len(asientos_cc),
    }


# ── Cuenta corriente del cliente (vista derivada de asientos) ─────────────────

# modulo del asiento → (categoría de filtro, etiqueta legible)
_MODULO_TIPO = {
    "um_reclass":        ("banco",   "Conciliación bancaria (UM)"),
    "cc_inicial":        ("banco",   "Acreditación (histórico)"),
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

    # Batch: PlanillaRow para um_reclass / cc_inicial (referencia_id = planilla_row_id)
    row_ids = [a.referencia_id for _, a in filas if (a.modulo or "").startswith(("um_reclass", "cc_inicial")) and a.referencia_id]
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
        elif modulo.startswith(("um_reclass", "cc_inicial")):
            info = row_map.get(a.referencia_id)
            if info:
                origen["planilla_id"] = info["planilla_id"]
                if info.get("movimiento_id"):
                    origen["movimiento_id"] = info["movimiento_id"]
                    origen["extracto_id"] = mov_map.get(info["movimiento_id"])
                elif modulo.startswith("um_reclass"):
                    # Trazabilidad rota en el flujo normal → validación/log, NO estado operativo
                    logger.warning(
                        "Cta.cte. cliente %s: asiento %s (um_reclass) sin movimiento bancario vinculado",
                        cliente_id, a.id,
                    )
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
