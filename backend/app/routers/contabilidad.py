from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from typing import Optional
from pydantic import BaseModel
import logging

from app.database import get_db
from app.middleware.auth import get_current_user, require_permission, can_switch_org
from app.models.user import User
from app.models.cliente import Cliente
from app.models.contabilidad import PlanCuenta, ReglaContable, Asiento, AsientoDetalle
from app.services.tz import hoy_art

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
    if can_switch_org(current_user, org_id) and org_id:
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
    cuenta_id: Optional[int] = Query(None),
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
    if cuenta_id:
        q = q.filter(Asiento.id.in_(
            db.query(AsientoDetalle.asiento_id).filter(AsientoDetalle.cuenta_id == cuenta_id)
        ))
    total = q.count()
    items = q.order_by(Asiento.fecha.desc(), Asiento.id.desc()).offset(skip).limit(limit).all()
    return {
        "total": total,
        "items": [
            {
                "id": a.id,
                "numero_asiento": a.numero_asiento or a.id,
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


def _norm_nombre(s: str) -> str:
    """Normaliza nombre para comparación: NFKD, sin diacríticos, minúsculas."""
    import unicodedata as _ud
    if not s:
        return ''
    s = _ud.normalize('NFKD', s)
    s = ''.join(c for c in s if not _ud.combining(c))
    return s.lower().strip()


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


@router.post("/recuperar-clientes-borrados")
def recuperar_clientes_borrados(
    payload: Optional[dict] = None,
    dry_run: bool = Query(False, description="Solo previsualiza la lista de candidatos"),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin_accounting")),
):
    """Recrea clientes que están acreditados en el extracto (movimientos_banco)
    pero ya no existen como Cliente, y les crea/vincula su cuenta contable.
    - dry_run=true → devuelve la lista de candidatos (nombres) para que el
      usuario elija cuáles recrear (evita recrear nombres basura del extracto).
    - POST con body {"nombres": [...]} → recrea SOLO esos (validados contra los
      candidatos del extracto). Todo aditivo: nunca toca clientes ni movimientos."""
    from app.models.extracto import MovimientoBanco
    from app.services.motor_contable import _get_o_crear_cuenta_cliente

    oid = _org_id(current_user, org_id)

    # Nombres acreditados en el extracto (excluye nulos, vacíos y "no identificado")
    nombres_rows = (
        db.query(MovimientoBanco.cliente_acreditado)
        .filter(
            MovimientoBanco.organizacion_id == oid,
            MovimientoBanco.cliente_acreditado.isnot(None),
            MovimientoBanco.cliente_acreditado != "",
            ~MovimientoBanco.cliente_acreditado.ilike("no identificado"),
        )
        .distinct()
        .all()
    )

    # Clientes existentes (normalizados) para no duplicar
    existentes = {
        _norm_nombre(c.nombre)
        for c in db.query(Cliente).filter(Cliente.organizacion_id == oid).all()
    }

    # Candidatos únicos a recrear (dedup por forma normalizada): norm -> nombre presentable
    faltantes: dict = {}
    for (nombre_raw,) in nombres_rows:
        nombre = (nombre_raw or "").strip()
        if not nombre:
            continue
        norm = _norm_nombre(nombre)
        if norm in existentes or norm in faltantes:
            continue
        faltantes[norm] = nombre[:1].upper() + nombre[1:]

    if dry_run:
        return {
            "dry_run": True,
            "clientes_a_recrear": len(faltantes),
            "nombres": sorted(faltantes.values()),
        }

    # Selección explícita: solo recreamos los nombres pedidos (validados contra candidatos)
    seleccion = (payload or {}).get("nombres") or []
    seleccion_norm = {_norm_nombre(n) for n in seleccion if (n or "").strip()}
    if not seleccion_norm:
        raise HTTPException(400, "Indicá qué clientes recrear (lista vacía).")

    a_crear = {norm: nombre for norm, nombre in faltantes.items() if norm in seleccion_norm}
    if not a_crear:
        raise HTTPException(400, "Ninguno de los nombres elegidos es un candidato válido del extracto.")

    recreados = []
    for nombre in a_crear.values():
        cli = Cliente(nombre=nombre, organizacion_id=oid)
        db.add(cli)
        db.flush()  # obtener id
        cuenta = None
        try:
            # reusar_huecos: si quedó un código libre (ej. 2-1-2-8 borrada), lo rellena
            cuenta = _get_o_crear_cuenta_cliente(db, cli.id, oid, reusar_huecos=True)
        except Exception as ex:
            logger.warning("recuperar-clientes: cuenta de %s: %s", nombre, ex)
        recreados.append({"cliente": nombre, "codigo": cuenta.codigo if cuenta else None})

    db.commit()
    logger.info("recuperar-clientes-borrados: %d recreados (org %d)", len(recreados), oid)
    return {"ok": True, "recreados": len(recreados), "detalle": recreados}


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
        fecha_asiento = fecha_acred or (fecha_carga.date() if fecha_carga else hoy_art())
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


# ── Cuenta corriente del cliente (vista derivada de asientos) ─────────────────

# modulo del asiento → (categoría de filtro, etiqueta legible)
_MODULO_TIPO = {
    "um_reclass":        ("banco",   "Conciliación bancaria (UM)"),
    "cc_inicial":        ("banco",   "Acreditación (histórico)"),
    "planilla":          ("tt",      "Transferencia (TT)"),
    "planilla_comision": ("tt",      "Comisión TT"),
    "cheque_carga":          ("cheques", "Cheque"),           # legacy
    "cheque_rechazo":        ("cheques", "Cheque rechazado"),  # legacy
    "cheque_registro":       ("cheques", "Cheque registrado"),
    "cheque_acred_banco":    ("cheques", "Cheque acreditado (banco)"),
    "cheque_acred_cliente":  ("cheques", "Cheque acreditado"),
    "cheque_rechazo_banco":  ("cheques", "Cheque rechazado (reversión)"),
    "cheque_rechazo_cliente":("cheques", "Gastos rechazo cheque"),
    "cheque_rechazo_gasto":  ("cheques", "Débito bancario rechazo"),
    "egreso":            ("ajustes", "Pago / Egreso"),
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
    filas = q.order_by(Asiento.fecha, Asiento.id).all()  # ASC para saldo correcto; se invierte al retornar

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

    # Batch: cuentas contraparte (los otros detalles del mismo asiento)
    asiento_ids_all = [a.id for _, a in filas]
    contra_map: dict[int, str] = {}  # asiento_id → "codigo nombre"
    if asiento_ids_all:
        otras = (
            db.query(AsientoDetalle, PlanCuenta)
            .join(PlanCuenta, AsientoDetalle.cuenta_id == PlanCuenta.id)
            .filter(AsientoDetalle.asiento_id.in_(asiento_ids_all),
                    AsientoDetalle.cuenta_id != cli.cuenta_contable_id)
            .all()
        )
        for od, pc in otras:
            if od.asiento_id not in contra_map:
                contra_map[od.asiento_id] = f"{pc.codigo} {pc.nombre}"

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
            "cuenta_contraparte": contra_map.get(a.id, ""),
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
        "movimientos": list(reversed(movimientos)),
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


@router.post("/reset-y-rebuild")
def reset_y_rebuild_asientos(
    dry_run: bool = Query(True, description="True = solo muestra qué haría; False = ejecuta"),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Borra TODOS los asientos de la org y los reconstruye desde los datos reales:
    - um_lote: un asiento por cada lote de UM importado en el extracto
    - cc_inicial: un asiento por cada fila de planilla conciliada con cliente vinculado
    Sólo superadmin puede ejecutarlo (dry_run=false).
    """
    if not current_user.is_superadmin:
        raise HTTPException(status_code=403, detail="Solo superadmin")

    from decimal import Decimal as _D
    from datetime import date as _date
    from app.models.extracto import MovimientoBanco, ExtractoBancario
    from app.models.planilla import Planilla, PlanillaRow
    from app.services.motor_contable import (
        _get_cuenta_por_codigo, _get_o_crear_cuenta_cliente, _monto,
    )

    oid = _org_id(current_user, org_id)

    # Self-heal: garantiza la columna numero_asiento aunque Render no haya
    # corrido el safety net de startup todavía. Sin esto, la query de renumerado
    # falla con "column numero_asiento does not exist" y revierte el borrado.
    try:
        db.execute(text("ALTER TABLE asientos ADD COLUMN IF NOT EXISTS numero_asiento INTEGER"))
        db.commit()
    except Exception as _col_ex:
        db.rollback()
        logger.warning("reset-y-rebuild: no se pudo asegurar numero_asiento: %s", _col_ex)

    # ── Conteos actuales ──────────────────────────────────────────
    n_asientos = db.query(Asiento).filter(Asiento.organizacion_id == oid).count()
    n_detalles = (
        db.query(AsientoDetalle)
        .join(Asiento, AsientoDetalle.asiento_id == Asiento.id)
        .filter(Asiento.organizacion_id == oid)
        .count()
    )

    # ── Movimientos UM agrupados por lote ─────────────────────────
    um_movs = (
        db.query(MovimientoBanco)
        .join(ExtractoBancario, MovimientoBanco.extracto_id == ExtractoBancario.id)
        .filter(
            ExtractoBancario.organizacion_id == oid,
            MovimientoBanco.source == "um",
        )
        .order_by(MovimientoBanco.um_lote, MovimientoBanco.id)
        .all()
    )
    from itertools import groupby
    lotes = {}
    for m in um_movs:
        lote_key = m.um_lote or 0
        lotes.setdefault(lote_key, []).append(m)
    n_um_lotes = len(lotes)

    # ── Filas conciliadas con cuenta contable ────────────────────
    filas_ok = (
        db.query(PlanillaRow, Planilla, Cliente)
        .join(Planilla, PlanillaRow.planilla_id == Planilla.id)
        .join(Cliente, Planilla.cliente_id == Cliente.id)
        .filter(
            Planilla.organizacion_id == oid,
            Planilla.deleted_at.is_(None),
            PlanillaRow.status.in_(["ok", "OK", "PAGO_PARCIAL", "CONCILIADO_CON_DIFERENCIA"]),
            Cliente.cuenta_contable_id.isnot(None),
        )
        .all()
    )
    n_filas_ok = len(filas_ok)

    if dry_run:
        return {
            "dry_run": True,
            "a_borrar": {"asientos": n_asientos, "detalles": n_detalles},
            "a_crear": {
                "um_lotes": n_um_lotes,
                "cc_iniciales": n_filas_ok,
                "total_asientos_nuevos": n_um_lotes + n_filas_ok,
            },
            "msg": "Ejecutá con dry_run=false para aplicar los cambios.",
        }

    # ── EJECUTAR: borrar todo ─────────────────────────────────────
    try:
        ids_asientos = [
            a.id for a in db.query(Asiento.id).filter(Asiento.organizacion_id == oid).all()
        ]
        if ids_asientos:
            db.query(AsientoDetalle).filter(AsientoDetalle.asiento_id.in_(ids_asientos)).delete(synchronize_session=False)
            db.query(Asiento).filter(Asiento.id.in_(ids_asientos)).delete(synchronize_session=False)
        db.flush()

        banco_macro = _get_cuenta_por_codigo(db, "1-1-1-3-1", oid)
        no_id       = _get_cuenta_por_codigo(db, "2-1-1-1", oid)
        if not banco_macro or not no_id:
            db.rollback()
            raise HTTPException(status_code=500, detail="Plan de cuentas incompleto: faltan cuentas base (Banco Macro o No Identificado)")

        contador = 0

        # ── Reconstruir um_lote ───────────────────────────────────
        # Acumula asientos y hace un único flush para obtener todos los IDs
        pending_um: list = []
        for lote_key, movs in sorted(lotes.items()):
            total_pos = sum(max(_monto(m.monto), _D("0")) for m in movs)
            total_neg = sum(abs(min(_monto(m.monto), _D("0"))) for m in movs)
            if total_pos <= 0 and total_neg <= 0:
                continue
            primer = movs[0]
            fecha_ref = primer.fecha if isinstance(primer.fecha, _date) else hoy_art()
            a = Asiento(
                fecha=fecha_ref,
                descripcion=f"UM lote {lote_key} — {len(movs)} movimientos (extracto #{primer.extracto_id})",
                modulo="um_lote",
                referencia_id=primer.id,
                organizacion_id=oid,
                usuario_id=current_user.id,
            )
            db.add(a)
            pending_um.append((a, total_pos, total_neg))
        db.flush()
        for a, total_pos, total_neg in pending_um:
            if total_pos > 0:
                db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=banco_macro.id, debe=total_pos, haber=_D("0")))
                db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=no_id.id, debe=_D("0"), haber=total_pos))
            if total_neg > 0:
                db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=no_id.id, debe=total_neg, haber=_D("0")))
                db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=banco_macro.id, debe=_D("0"), haber=total_neg))
        contador += len(pending_um)

        # ── Reconstruir cc_inicial ────────────────────────────────
        # Cache de cuentas por cliente + flush único al final del lote
        _cuenta_cache: dict = {}
        pending_cc: list = []
        for row, planilla, cliente in filas_ok:
            if cliente.id not in _cuenta_cache:
                _cuenta_cache[cliente.id] = _get_o_crear_cuenta_cliente(db, cliente.id, oid)
            cuenta_cli = _cuenta_cache[cliente.id]
            if not cuenta_cli:
                continue
            monto = abs(_monto(row.monto))  # planilla rows son siempre ingresos (positivos)
            if monto <= 0:
                continue
            fecha = (row.fecha_acred or planilla.fecha_carga or hoy_art())
            if not isinstance(fecha, _date):
                try:
                    from datetime import datetime as _dt
                    fecha = _dt.strptime(str(fecha)[:10], "%Y-%m-%d").date()
                except Exception:
                    fecha = hoy_art()
            a = Asiento(
                fecha=fecha,
                descripcion=f"Acreditación {cliente.nombre} — {planilla.nombre_archivo}",
                modulo="cc_inicial",
                referencia_id=row.id,
                organizacion_id=oid,
                usuario_id=current_user.id,
            )
            db.add(a)
            pending_cc.append((a, monto, cuenta_cli.id))
        db.flush()
        for a, monto, cuenta_cli_id in pending_cc:
            db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=banco_macro.id, debe=monto, haber=_D("0")))
            db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=cuenta_cli_id, debe=_D("0"), haber=monto))
        contador += len(pending_cc)

        # ── Renumerar correlativamente ────────────────────────────
        nuevos = (
            db.query(Asiento)
            .filter(Asiento.organizacion_id == oid)
            .order_by(Asiento.fecha, Asiento.id)
            .all()
        )
        for i, a in enumerate(nuevos, start=1):
            a.numero_asiento = i

        db.commit()
        return {
            "dry_run": False,
            "borrados": {"asientos": n_asientos, "detalles": n_detalles},
            "creados": contador,
            "msg": f"Libro Diario reconstruido: {contador} asientos numerados del 1 al {contador}.",
        }

    except HTTPException:
        raise
    except Exception as ex:
        db.rollback()
        logger.error("reset-y-rebuild error: %s", ex)
        raise HTTPException(status_code=500, detail=str(ex))


# ── Ajuste manual del Libro Diario ──────────────────────────────────────────

class AsientoManualIn(BaseModel):
    cuenta_debe_id: int
    cuenta_haber_id: int
    monto: float
    fecha: str
    descripcion: str


@router.post("/asiento-manual")
def post_asiento_manual(
    body: AsientoManualIn,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin_accounting")),
):
    from decimal import Decimal, InvalidOperation
    from datetime import date as _date
    from app.services.motor_contable import registrar_ajuste_manual

    oid = _org_id(current_user, org_id)
    cuenta_debe = db.query(PlanCuenta).filter(PlanCuenta.id == body.cuenta_debe_id, PlanCuenta.organizacion_id == oid).first()
    cuenta_haber = db.query(PlanCuenta).filter(PlanCuenta.id == body.cuenta_haber_id, PlanCuenta.organizacion_id == oid).first()
    if not cuenta_debe or not cuenta_haber:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    if body.cuenta_debe_id == body.cuenta_haber_id:
        raise HTTPException(status_code=400, detail="Las cuentas Debe y Haber no pueden ser la misma")
    for c in (cuenta_debe, cuenta_haber):
        if db.query(PlanCuenta).filter(PlanCuenta.parent_id == c.id).first():
            raise HTTPException(status_code=400, detail=f"'{c.nombre}' no es cuenta hoja (tiene subcuentas)")
    try:
        monto = Decimal(str(body.monto))
    except InvalidOperation:
        raise HTTPException(status_code=400, detail="Monto inválido")
    if monto <= 0:
        raise HTTPException(status_code=400, detail="El monto debe ser mayor que cero")
    try:
        fecha = _date.fromisoformat(body.fecha)
    except ValueError:
        raise HTTPException(status_code=400, detail="Fecha inválida")
    try:
        asiento_id = registrar_ajuste_manual(
            db=db, org_id=oid, usuario_id=current_user.id,
            cuenta_debe_id=cuenta_debe.id, cuenta_haber_id=cuenta_haber.id,
            monto=monto, fecha=fecha,
            descripcion=body.descripcion.strip() or f"Ajuste manual: {cuenta_debe.nombre} / {cuenta_haber.nombre}",
        )
        db.commit()
        return {"ok": True, "asiento_id": asiento_id}
    except Exception as ex:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(ex))


class PatchFechaBody(BaseModel):
    fecha: str  # YYYY-MM-DD

@router.patch("/asientos/{asiento_id}/fecha")
def patch_asiento_fecha(
    asiento_id: int,
    body: PatchFechaBody,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin_accounting")),
):
    """Editar la fecha de un asiento individual (solo superadmin)."""
    from datetime import date as _date
    oid = _org_id(current_user, org_id)
    a = db.query(Asiento).filter(Asiento.id == asiento_id, Asiento.organizacion_id == oid).first()
    if not a:
        raise HTTPException(404, "Asiento no encontrado")
    try:
        a.fecha = _date.fromisoformat(body.fecha)
    except ValueError:
        raise HTTPException(400, "Formato de fecha inválido (YYYY-MM-DD)")
    db.commit()
    return {"ok": True, "id": a.id, "fecha": str(a.fecha)}


@router.delete("/asientos/{asiento_id}")
def delete_asiento_manual(
    asiento_id: int,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin_accounting")),
):
    from app.services.motor_contable import _next_numero_asiento
    from datetime import date as _date

    oid = _org_id(current_user, org_id)
    asiento = db.query(Asiento).filter(Asiento.id == asiento_id, Asiento.organizacion_id == oid).first()
    if not asiento:
        raise HTTPException(status_code=404, detail="Asiento no encontrado")
    if asiento.modulo != "ajuste_manual":
        raise HTTPException(status_code=400, detail="Solo se pueden revertir asientos de ajuste manual")
    ya_reversado = db.query(Asiento).filter(
        Asiento.modulo == "ajuste_manual_reverso",
        Asiento.referencia_id == asiento_id,
        Asiento.organizacion_id == oid,
    ).first()
    if ya_reversado:
        raise HTTPException(status_code=400, detail="Este asiento ya fue revertido")
    lineas_orig = db.query(AsientoDetalle).filter(AsientoDetalle.asiento_id == asiento_id).all()
    try:
        reverso = Asiento(
            fecha=hoy_art(),
            descripcion=f"REVERSO #{asiento_id}: {asiento.descripcion or ''} — Revertido manualmente",
            modulo="ajuste_manual_reverso",
            referencia_id=asiento_id,
            organizacion_id=oid,
            usuario_id=current_user.id,
            numero_asiento=_next_numero_asiento(db, oid),
        )
        db.add(reverso)
        db.flush()
        for linea in lineas_orig:
            db.add(AsientoDetalle(asiento_id=reverso.id, cuenta_id=linea.cuenta_id, debe=linea.haber, haber=linea.debe))
        db.commit()
        return {"ok": True, "reverso_id": reverso.id}
    except Exception as ex:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(ex))


# ── Diagnóstico y fix de fechas con timezone incorrecto ────────────────────────

@router.post("/fix-fechas-utc")
def fix_fechas_utc(
    dry_run: bool = Query(True),
    org_id: Optional[int] = Query(None),
    desde: Optional[str] = Query(None),
    hasta: Optional[str] = Query(None),
    modulo: Optional[str] = Query(None),
    direccion: str = Query("atrasar"),  # "atrasar" (−1 día) o "adelantar" (+1 día)
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin_accounting")),
):
    """
    Corrige fechas de asientos y egresos en un rango de fechas dado.
    direccion=atrasar  → resta 1 día (para registros UTC-creados 1 día adelantado)
    direccion=adelantar → suma 1 día (para registros ingresados con fecha de ayer por error)
    dry_run=true: solo muestra los afectados sin modificar nada.
    """
    from datetime import datetime, timezone, timedelta, date as _date
    from app.models.egreso import Egreso

    oid = _org_id(current_user, org_id)
    delta = timedelta(days=1) if direccion == "adelantar" else timedelta(days=-1)

    a_q = db.query(Asiento).filter(Asiento.organizacion_id == oid)
    if desde:
        a_q = a_q.filter(Asiento.fecha >= desde)
    if hasta:
        a_q = a_q.filter(Asiento.fecha <= hasta)
    if modulo:
        a_q = a_q.filter(Asiento.modulo == modulo)
    asientos_q = a_q.all()

    try:
        e_q = db.query(Egreso).filter(Egreso.organizacion_id == oid)
        if desde:
            e_q = e_q.filter(Egreso.fecha >= desde)
        if hasta:
            e_q = e_q.filter(Egreso.fecha <= hasta)
        egresos_q = e_q.all()
    except Exception:
        egresos_q = []

    asientos_afectados = [
        {"id": a.id, "fecha_actual": str(a.fecha), "created_at_utc": str(a.created_at),
         "modulo": a.modulo, "descripcion": (a.descripcion or '')[:60]}
        for a in asientos_q
    ]
    egresos_afectados = [
        {"id": e.id, "fecha_actual": str(e.fecha), "created_at_utc": str(e.created_at),
         "descripcion": (e.descripcion or '')[:60]}
        for e in egresos_q
    ]

    if not dry_run:
        for a in asientos_q:
            if a.fecha:
                a.fecha = a.fecha + delta
        for e in egresos_q:
            if e.fecha:
                e.fecha = e.fecha + delta
        db.commit()

    accion = "+1 día (adelantado)" if direccion == "adelantar" else "−1 día (atrasado)"
    return {
        "dry_run": dry_run,
        "direccion": direccion,
        "asientos_afectados": len(asientos_afectados),
        "egresos_afectados": len(egresos_afectados),
        "detalle_asientos": asientos_afectados,
        "detalle_egresos": egresos_afectados,
        "mensaje": (
            f"Solo conteo — no se modificó nada. ({len(asientos_afectados)} asientos + {len(egresos_afectados)} egresos en el rango)." if dry_run else
            f"Fechas corregidas {accion}: {len(asientos_afectados)} asientos + {len(egresos_afectados)} egresos."
        ),
    }
