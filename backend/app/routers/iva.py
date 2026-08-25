"""Router del módulo IVA Proyección y DDJJ.

Endpoints (prefix /iva):
  GET  /iva/config                          — cuentas configurables (tasa_iva)
  PUT  /iva/config/{cuenta_id}              — setea tasa_iva de una cuenta hoja
  GET  /iva/proyeccion?periodo=             — preview (no persiste)
  POST /iva/proyeccion/calcular?periodo=    — calcula y persiste (upsert)
  POST /iva/proyeccion/{id}/marcar-presentada
  GET  /iva/historial                       — snapshots de la org, paginado

Permisos:
  config (GET/PUT)            → admin_accounting
  proyeccion (GET preview)    → view_accounting
  proyeccion/calcular (POST)  → manage_finance
  marcar-presentada (POST)    → admin_accounting
  historial (GET)             → view_accounting
"""

from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import require_permission, can_switch_org
from app.models.contabilidad import PlanCuenta
from app.models.proyeccion_iva import ProyeccionIva
from app.models.iva_liquidacion import ComprobanteIva, LiquidacionIva
from app.models.user import User
from app.services.auditoria import registrar_log
from app.services.iva_service import (
    calcular_proyeccion_iva,
    guardar_o_actualizar_proyeccion,
    marcar_presentada,
    IvaServiceError,
)
from app.services.mis_comprobantes_parser import parsear_mis_comprobantes
from app.services.iva_liquidacion_service import (
    calcular_liquidacion,
    marcar_presentada as marcar_liquidacion_presentada,
    es_nota_credito,
    IvaLiquidacionError,
)

router = APIRouter(prefix="/iva", tags=["iva"])


# ── Helpers ───────────────────────────────────────────────────────

def _org_id(current_user: User, org_id: Optional[int]) -> int:
    if can_switch_org(current_user, org_id) and org_id:
        return org_id
    return current_user.organizacion_id or 1


def _f(v):
    return float(v) if isinstance(v, Decimal) else v


def _proyeccion_dict(p: ProyeccionIva) -> dict:
    return {
        "id": p.id,
        "organizacion_id": p.organizacion_id,
        "periodo": p.periodo,
        "debito_fiscal": p.debito_fiscal,
        "credito_fiscal": p.credito_fiscal,
        "saldo": p.saldo,
        "estado": p.estado,
        "fecha_presentacion": p.fecha_presentacion,
        "detalle": p.detalle,
        "created_at": p.created_at,
        "updated_at": p.updated_at,
    }


# ── Schemas ───────────────────────────────────────────────────────

class TasaIvaIn(BaseModel):
    tasa_iva: Optional[float] = None


# ── Config: tasa_iva por cuenta ───────────────────────────────────

@router.get("/config")
def get_config(
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin_accounting")),
):
    """Lista las cuentas de tipo resultado (ingresos/gastos) con su tasa_iva
    actual — para que el admin configure cuáles están gravadas.

    No se restringe a cuentas hoja: algunos módulos (p. ej. Pagos →
    `registrar_egreso`) postean directamente contra cuentas "cabecera" como
    `3-2-0-0 Gastos`, así que esa cuenta también debe poder configurarse o
    sus egresos quedarían afuera de la proyección sin forma de incluirlos.
    Como la proyección agrega por `cuenta_id` exacto de cada línea de
    asiento, no hay riesgo de doble conteo entre una cuenta y sus
    subcuentas — cada línea pertenece a una sola cuenta."""
    oid = _org_id(current_user, org_id)

    cuentas = (
        db.query(PlanCuenta)
        .filter(
            PlanCuenta.organizacion_id == oid,
            PlanCuenta.activo == True,
            PlanCuenta.tipo == "resultado",
        )
        .order_by(PlanCuenta.codigo)
        .all()
    )
    items = [
        {
            "id": c.id,
            "codigo": c.codigo,
            "nombre": c.nombre,
            "tipo": c.tipo,
            "es_ingreso": c.codigo.startswith("3-1"),
            "tasa_iva": _f(c.tasa_iva),
        }
        for c in cuentas
    ]
    return {"items": items, "total": len(items)}


@router.put("/config/{cuenta_id}")
def set_tasa_iva(
    cuenta_id: int,
    body: TasaIvaIn,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin_accounting")),
):
    """Setea (o limpia, con null) la tasa_iva de una cuenta resultado de la org.

    No exige cuenta hoja (ver `get_config`) — algunos egresos postean contra
    cuentas cabecera y deben poder marcarse como gravadas igual."""
    oid = _org_id(current_user, org_id)
    c = (
        db.query(PlanCuenta)
        .filter(PlanCuenta.id == cuenta_id, PlanCuenta.organizacion_id == oid)
        .first()
    )
    if not c:
        raise HTTPException(404, "Cuenta no encontrada")
    if c.tipo != "resultado":
        raise HTTPException(400, f"'{c.nombre}' no es una cuenta de resultado (ingreso/gasto)")

    if body.tasa_iva is not None and (body.tasa_iva < 0 or body.tasa_iva > 1):
        raise HTTPException(422, "tasa_iva debe estar entre 0 y 1 (ej. 0.21 = 21%)")

    c.tasa_iva = Decimal(str(body.tasa_iva)) if body.tasa_iva is not None else None
    registrar_log(db, current_user.id, "iva_config", c.id, "UPDATE",
                  {"codigo": c.codigo, "tasa_iva": body.tasa_iva})
    db.commit()
    db.refresh(c)
    return {
        "id": c.id,
        "codigo": c.codigo,
        "nombre": c.nombre,
        "tasa_iva": _f(c.tasa_iva),
    }


# ── Proyección ────────────────────────────────────────────────────

@router.get("/proyeccion")
def preview_proyeccion(
    periodo: str = Query(..., description="Período YYYY-MM"),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("view_accounting")),
):
    """Calcula la proyección de IVA del período sin persistir (preview)."""
    oid = _org_id(current_user, org_id)
    try:
        calc = calcular_proyeccion_iva(db, oid, periodo)
    except IvaServiceError as ex:
        raise HTTPException(400, str(ex))
    return {
        "periodo": calc["periodo"],
        "debito_fiscal": calc["debito_fiscal"],
        "credito_fiscal": calc["credito_fiscal"],
        "credito_fiscal_real": calc["credito_fiscal_real"],
        "credito_fiscal_proyectado": calc["credito_fiscal_proyectado"],
        "saldo": calc["saldo"],
        "detalle": calc["detalle"],
    }


@router.post("/proyeccion/calcular")
def calcular_y_guardar(
    periodo: str = Query(..., description="Período YYYY-MM"),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage_finance")),
):
    """Calcula y persiste la proyección (upsert por org+período)."""
    oid = _org_id(current_user, org_id)
    try:
        p = guardar_o_actualizar_proyeccion(db, oid, periodo)
    except IvaServiceError as ex:
        raise HTTPException(400, str(ex))
    registrar_log(db, current_user.id, "iva_proyeccion", p.id, "CALCULAR",
                  {"periodo": periodo, "saldo": float(p.saldo)})
    db.commit()
    return _proyeccion_dict(p)


@router.post("/proyeccion/{proyeccion_id}/marcar-presentada")
def marcar_proyeccion_presentada(
    proyeccion_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin_accounting")),
):
    """Marca la proyección como presentada (DDJJ enviada)."""
    p = db.query(ProyeccionIva).filter(ProyeccionIva.id == proyeccion_id).first()
    if not p:
        raise HTTPException(404, "Proyección no encontrada")
    if not current_user.is_superadmin and not can_switch_org(current_user, p.organizacion_id) \
            and p.organizacion_id != (current_user.organizacion_id or 1):
        raise HTTPException(403, "Sin acceso")
    try:
        p = marcar_presentada(db, p.organizacion_id, p.periodo)
    except IvaServiceError as ex:
        raise HTTPException(400, str(ex))
    registrar_log(db, current_user.id, "iva_proyeccion", p.id, "PRESENTAR",
                  {"periodo": p.periodo})
    db.commit()
    return _proyeccion_dict(p)


# ── Historial ─────────────────────────────────────────────────────

@router.get("/historial")
def historial(
    org_id: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("view_accounting")),
):
    """Lista los snapshots de proyección de la org, período descendente."""
    oid = _org_id(current_user, org_id)
    q = (
        db.query(ProyeccionIva)
        .filter(ProyeccionIva.organizacion_id == oid)
        .order_by(ProyeccionIva.periodo.desc(), ProyeccionIva.id.desc())
    )
    total = q.count()
    items = q.offset(offset).limit(limit).all()
    return {"items": [_proyeccion_dict(p) for p in items], "total": total}


# ══════════════════════════════════════════════════════════════════
#  LIQUIDACIÓN REAL DE IVA (Excel "Mis Comprobantes" de ARCA)
#  Módulo separado de la proyección de arriba: acá el débito/crédito
#  se importan de los archivos oficiales de ARCA, no se estiman.
# ══════════════════════════════════════════════════════════════════

_PERIODO_RE = None  # validación simple inline


def _validar_periodo(periodo: str) -> str:
    try:
        anio_s, mes_s = periodo.split("-")
        anio, mes = int(anio_s), int(mes_s)
        if not (1 <= mes <= 12) or anio < 2000 or anio > 2100:
            raise ValueError
    except (ValueError, AttributeError):
        raise HTTPException(422, f"Período inválido: {periodo!r}. Use formato 'YYYY-MM'.")
    return f"{anio:04d}-{mes:02d}"


def _comprobante_dict(c: ComprobanteIva) -> dict:
    return {
        "id": c.id,
        "organizacion_id": c.organizacion_id,
        "direccion": c.direccion,
        "periodo": c.periodo,
        "fecha": c.fecha.isoformat() if c.fecha else None,
        "tipo_codigo": c.tipo_codigo,
        "tipo_desc": c.tipo_desc,
        "punto_venta": c.punto_venta,
        "numero": c.numero,
        "cuit_contraparte": c.cuit_contraparte,
        "denominacion": c.denominacion,
        "neto_gravado_total": _f(c.neto_gravado_total),
        "total_iva": _f(c.total_iva),
        "imp_total": _f(c.imp_total),
        "detalle_alicuotas": c.detalle_alicuotas,
        "incluido": c.incluido,
        "archivo_origen": c.archivo_origen,
        "es_nota_credito": es_nota_credito(c.tipo_codigo),
    }


def _liquidacion_dict(liq: LiquidacionIva) -> dict:
    return {
        "id": liq.id,
        "organizacion_id": liq.organizacion_id,
        "periodo": liq.periodo,
        "debito_fiscal": _f(liq.debito_fiscal),
        "credito_fiscal": _f(liq.credito_fiscal),
        "tecnico_periodo": _f(liq.tecnico_periodo),
        "saldo_tecnico_anterior": _f(liq.saldo_tecnico_anterior),
        "saldo_tecnico_nuevo": _f(liq.saldo_tecnico_nuevo),
        "retenciones": _f(liq.retenciones),
        "percepciones": _f(liq.percepciones),
        "saldo_libre_anterior": _f(liq.saldo_libre_anterior),
        "saldo_libre_nuevo": _f(liq.saldo_libre_nuevo),
        "saldo_a_pagar": _f(liq.saldo_a_pagar),
        "cant_emitidos": liq.cant_emitidos,
        "cant_recibidos": liq.cant_recibidos,
        "estado": liq.estado,
        "fecha_presentacion": liq.fecha_presentacion,
        "created_at": liq.created_at,
        "updated_at": liq.updated_at,
    }


class CalcularLiquidacionIn(BaseModel):
    periodo: str
    retenciones: Optional[float] = None
    percepciones: Optional[float] = None
    saldo_tecnico_anterior: Optional[float] = None
    saldo_libre_anterior: Optional[float] = None


class ToggleIncluidoIn(BaseModel):
    incluido: bool


def _liq_por_id_con_acceso(db: Session, current_user: User, liq_id: int) -> LiquidacionIva:
    liq = db.query(LiquidacionIva).filter(LiquidacionIva.id == liq_id).first()
    if not liq:
        raise HTTPException(404, "Liquidación no encontrada")
    if not current_user.is_superadmin and not can_switch_org(current_user, liq.organizacion_id) \
            and liq.organizacion_id != (current_user.organizacion_id or 1):
        raise HTTPException(403, "Sin acceso")
    return liq


# ── Comprobantes: import / listado / toggle / delete ──────────────

@router.post("/comprobantes/importar")
async def importar_comprobantes(
    file: UploadFile = File(...),
    direccion: str = Query(..., description="'emitido' o 'recibido'"),
    periodo: str = Query(..., description="Período YYYY-MM"),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage_finance")),
):
    """Importa el Excel "Mis Comprobantes" de ARCA de un período.

    Solo se importan los comprobantes cuya fecha cae en el período. La dedup es
    por el unique (org, direccion, tipo, PV, número, cuit): los ya existentes
    cuentan como duplicados (no error). Los de otra fecha cuentan como
    fuera_de_periodo y se ignoran."""
    if direccion not in ("emitido", "recibido"):
        raise HTTPException(422, "direccion debe ser 'emitido' o 'recibido'")
    periodo = _validar_periodo(periodo)
    oid = _org_id(current_user, org_id)

    contenido = await file.read()
    try:
        filas = parsear_mis_comprobantes(contenido, direccion)
    except ValueError as ex:
        raise HTTPException(400, str(ex))

    importados = 0
    duplicados = 0
    fuera_de_periodo = 0
    for row in filas:
        fecha = row["fecha"]
        fila_periodo = f"{fecha.year:04d}-{fecha.month:02d}"
        if fila_periodo != periodo:
            fuera_de_periodo += 1
            continue

        comp = ComprobanteIva(
            organizacion_id=oid,
            direccion=direccion,
            periodo=periodo,
            fecha=fecha,
            tipo_codigo=row["tipo_codigo"],
            tipo_desc=row["tipo_desc"],
            punto_venta=row["punto_venta"],
            numero=row["numero"],
            cuit_contraparte=row["cuit_contraparte"],
            denominacion=row["denominacion"],
            neto_gravado_total=row["neto_gravado_total"],
            total_iva=row["total_iva"],
            imp_total=row["imp_total"],
            detalle_alicuotas=row["detalle_alicuotas"],
            archivo_origen=file.filename,
        )
        db.add(comp)
        try:
            db.commit()
            importados += 1
        except IntegrityError:
            db.rollback()
            duplicados += 1

    registrar_log(db, current_user.id, "comprobantes_iva", 0, "IMPORTAR",
                  {"direccion": direccion, "periodo": periodo,
                   "importados": importados, "duplicados": duplicados,
                   "fuera_de_periodo": fuera_de_periodo})
    db.commit()
    return {
        "importados": importados,
        "duplicados": duplicados,
        "fuera_de_periodo": fuera_de_periodo,
        "periodo": periodo,
    }


@router.get("/comprobantes")
def listar_comprobantes(
    periodo: str = Query(..., description="Período YYYY-MM"),
    direccion: Optional[str] = Query(None, description="'emitido' | 'recibido'"),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("view_accounting")),
):
    """Lista los comprobantes del período con totales de IVA incluido por dirección."""
    periodo = _validar_periodo(periodo)
    oid = _org_id(current_user, org_id)

    q = db.query(ComprobanteIva).filter(
        ComprobanteIva.organizacion_id == oid,
        ComprobanteIva.periodo == periodo,
    )
    if direccion in ("emitido", "recibido"):
        q = q.filter(ComprobanteIva.direccion == direccion)
    comps = q.order_by(ComprobanteIva.fecha, ComprobanteIva.id).all()

    debito = Decimal("0")
    credito = Decimal("0")
    for c in comps:
        if not c.incluido:
            continue
        iva = c.total_iva if isinstance(c.total_iva, Decimal) else Decimal(str(c.total_iva or 0))
        signo = Decimal("-1") if es_nota_credito(c.tipo_codigo) else Decimal("1")
        if c.direccion == "emitido":
            debito += signo * iva
        else:
            credito += signo * iva

    return {
        "items": [_comprobante_dict(c) for c in comps],
        "totales": {
            "debito_incluido": float(debito),
            "credito_incluido": float(credito),
        },
    }


@router.patch("/comprobantes/{comprobante_id}")
def toggle_comprobante(
    comprobante_id: int,
    body: ToggleIncluidoIn,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage_finance")),
):
    """Incluye/excluye un comprobante del cálculo de la liquidación (sin borrarlo)."""
    oid = _org_id(current_user, org_id)
    c = db.query(ComprobanteIva).filter(
        ComprobanteIva.id == comprobante_id,
        ComprobanteIva.organizacion_id == oid,
    ).first()
    if not c:
        raise HTTPException(404, "Comprobante no encontrado")
    c.incluido = body.incluido
    registrar_log(db, current_user.id, "comprobantes_iva", c.id, "TOGGLE_INCLUIDO",
                  {"incluido": body.incluido})
    db.commit()
    return {"ok": True}


@router.delete("/comprobantes/{comprobante_id}")
def eliminar_comprobante(
    comprobante_id: int,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage_finance")),
):
    """Borra un comprobante (hard delete — es staging re-importable)."""
    oid = _org_id(current_user, org_id)
    c = db.query(ComprobanteIva).filter(
        ComprobanteIva.id == comprobante_id,
        ComprobanteIva.organizacion_id == oid,
    ).first()
    if not c:
        raise HTTPException(404, "Comprobante no encontrado")
    registrar_log(db, current_user.id, "comprobantes_iva", c.id, "DELETE",
                  {"direccion": c.direccion, "periodo": c.periodo,
                   "tipo": c.tipo_desc, "numero": c.numero}, autocommit=False)
    db.delete(c)
    db.commit()
    return {"ok": True}


# ── Liquidación: calcular / obtener / historial / presentar ───────

@router.post("/liquidacion/calcular")
def calcular_liquidacion_endpoint(
    body: CalcularLiquidacionIn,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage_finance")),
):
    """Calcula (upsert) la liquidación real de IVA del período. 409 si ya presentada."""
    periodo = _validar_periodo(body.periodo)
    oid = _org_id(current_user, org_id)

    def _dec(v):
        return Decimal(str(v)) if v is not None else None

    try:
        liq = calcular_liquidacion(
            db, oid, periodo,
            retenciones=_dec(body.retenciones),
            percepciones=_dec(body.percepciones),
            saldo_tecnico_anterior=_dec(body.saldo_tecnico_anterior),
            saldo_libre_anterior=_dec(body.saldo_libre_anterior),
        )
    except IvaLiquidacionError as ex:
        raise HTTPException(409, str(ex))
    registrar_log(db, current_user.id, "liquidaciones_iva", liq.id, "CALCULAR",
                  {"periodo": periodo, "saldo_a_pagar": float(liq.saldo_a_pagar)})
    db.commit()
    return _liquidacion_dict(liq)


@router.get("/liquidacion")
def obtener_liquidacion(
    periodo: str = Query(..., description="Período YYYY-MM"),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("view_accounting")),
):
    """Devuelve la liquidación real del período, o 404."""
    periodo = _validar_periodo(periodo)
    oid = _org_id(current_user, org_id)
    liq = db.query(LiquidacionIva).filter(
        LiquidacionIva.organizacion_id == oid,
        LiquidacionIva.periodo == periodo,
    ).first()
    if not liq:
        raise HTTPException(404, "No existe liquidación para ese período")
    return _liquidacion_dict(liq)


@router.get("/liquidacion/historial")
def historial_liquidaciones(
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("view_accounting")),
):
    """Lista las liquidaciones reales de la org, período descendente."""
    oid = _org_id(current_user, org_id)
    items = db.query(LiquidacionIva).filter(
        LiquidacionIva.organizacion_id == oid,
    ).order_by(LiquidacionIva.periodo.desc(), LiquidacionIva.id.desc()).all()
    return {"items": [_liquidacion_dict(x) for x in items]}


@router.post("/liquidacion/{liquidacion_id}/presentar")
def presentar_liquidacion(
    liquidacion_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin_accounting")),
):
    """Marca la liquidación como presentada (DDJJ enviada). 409 si ya lo estaba."""
    liq = _liq_por_id_con_acceso(db, current_user, liquidacion_id)
    try:
        liq = marcar_liquidacion_presentada(db, liq)
    except IvaLiquidacionError as ex:
        raise HTTPException(409, str(ex))
    registrar_log(db, current_user.id, "liquidaciones_iva", liq.id, "PRESENTAR",
                  {"periodo": liq.periodo})
    db.commit()
    return _liquidacion_dict(liq)
