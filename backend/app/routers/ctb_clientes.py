"""Router contabilidad — Vinculación cliente ↔ cuenta contable.

Rutas expuestas (bajo el prefix /contabilidad del router padre):
  GET   /clientes-cuentas
  PUT   /clientes/{cliente_id}/cuenta
  POST  /clientes/{cliente_id}/cuenta/crear
  POST  /clientes/cuentas/crear-faltantes
  POST  /recuperar-clientes-borrados
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user, require_permission
from app.models.cliente import Cliente
from app.models.contabilidad import PlanCuenta
from app.models.user import User
from .ctb_common import _org_id, _cuenta_parent_cliente, _norm_nombre

router = APIRouter(tags=["contabilidad"])
logger = logging.getLogger(__name__)


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
