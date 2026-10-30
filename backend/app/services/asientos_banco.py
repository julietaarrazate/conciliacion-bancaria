"""Asientos del banco: reconstrucción, corrección del histórico y control.

Modelo de cuentas transitorias estilo Odoo (oct 2026, ver
docs/architecture/ACCOUNTING_ENGINE.md §2bis y docs/adr/DECISIONS.md): la cuenta
del banco la mueven SOLO los datos del banco (extracto principal + Últimos
Movimientos) y los módulos pegan contra 2-1-1-1 (cobros a imputar) / 2-1-1-2
(pagos a imputar). Este módulo junta las tres herramientas de administración de
esos asientos, todas por organización:

- `reconstruir_asientos_banco` — "Empezar limpio" (POST /contabilidad/reset-y-rebuild):
  borra y rearma SOLO los módulos que sabe reconstruir desde los datos (extracto
  principal, UM y reclasificación de planillas, más sus versiones viejas y sus
  reversos). Todo lo demás (pagos, cheques, tarjetas, sueldos, ajustes manuales…)
  se conserva intacto; al final renumera 1..N por (fecha, id) incluyéndolos.
- `corregir_asientos_banco` — corrección explícita del histórico
  (POST /contabilidad/corregir-asientos-banco): reversa los asientos armados con
  el modelo viejo y crea los correctos. Nunca borra ni edita asientos existentes,
  es idempotente y el dry_run no persiste nada.
- `control_banco` — saldo del banco en libros vs. saldo del último extracto, más
  los saldos de las transitorias (GET /contabilidad/control-banco).

Montos en Decimal punta a punta.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.contabilidad import Asiento, AsientoDetalle, PlanCuenta
from app.models.extracto import ExtractoBancario, MovimientoBanco
from app.services import motor_contable as mc
from app.services.tz import hoy_art

logger = logging.getLogger(__name__)

_CERO = Decimal("0")

# Módulos que "Empezar limpio" sabe reconstruir desde los datos reales.
MODULOS_RECONSTRUIBLES = (
    mc.MODULO_EXTRACTO,                       # extracto principal (uno por día)
    "um_lote",                                # Últimos Movimientos (uno por lote)
    "um_reclass_planilla", "um_reclass_planilla_comision",
    "reclass_planilla_principal", "reclass_planilla_principal_comision",
)
# Versiones viejas de esos mismos módulos: el rebuild las reemplaza (si se
# conservaran, duplicarían lo que el rebuild vuelve a crear).
MODULOS_REEMPLAZADOS = (
    mc.MODULO_EXTRACTO_LEGACY,                # extracto viejo (abs() contra 2-1-0-0)
    "um_mov",                                 # UM en modo individual
    "um_lote_corregido", "um_mov_corregido",  # UM rehechos por corregir_asientos_banco
    "um_reclass", "cc_inicial",               # reclasificación por fila (legacy / histórica)
    mc.MODULO_RECLASS_LEGACY_EXTRACTO, mc.MODULO_RECLASS_LEGACY_EXTRACTO + "_comision",
    "planilla", "planilla_comision",          # registrar_planilla (dead code)
)


def modulos_del_rebuild() -> set[str]:
    """Módulos que borra el rebuild: los reconstruibles, sus versiones viejas y
    los reversos de ambos. Cualquier otro módulo se conserva."""
    base = set(MODULOS_RECONSTRUIBLES) | set(MODULOS_REEMPLAZADOS)
    return base | {f"{m}_reverso" for m in base}


# ─── Saldos ──────────────────────────────────────────────────────────────────

def saldo_cuenta(db: Session, oid: int, codigo: str) -> Decimal:
    """Saldo (Σdebe − Σhaber) de una cuenta por código, solo sus propias líneas."""
    cuenta = db.query(PlanCuenta).filter(PlanCuenta.codigo == codigo, PlanCuenta.organizacion_id == oid).first()
    if not cuenta:
        return _CERO
    debe, haber = (
        db.query(func.coalesce(func.sum(AsientoDetalle.debe), 0), func.coalesce(func.sum(AsientoDetalle.haber), 0))
        .join(Asiento, AsientoDetalle.asiento_id == Asiento.id)
        .filter(AsientoDetalle.cuenta_id == cuenta.id, Asiento.organizacion_id == oid)
        .one()
    )
    return (Decimal(str(debe)) - Decimal(str(haber))).quantize(Decimal("0.01"))


_CUENTAS_CONTROL = (
    ("banco", mc.CUENTA_BANCO_EXTRACTO),
    ("banco_cuenta_madre", "1-1-1-3"),
    ("pasivo_corriente", mc.CUENTA_PASIVO_CORRIENTE_LEGACY),
    ("cobros_a_imputar", mc.CUENTA_COBROS_A_IMPUTAR),
    ("pagos_a_imputar", mc.CUENTA_PAGOS_A_IMPUTAR),
)


def saldos_cuentas_banco(db: Session, oid: int) -> dict:
    """Saldos de Banco Macro, la cuenta madre Banco, Pasivo Corriente y las dos
    transitorias, como strings (JSON-safe, sin perder Decimal)."""
    return {
        clave: {"codigo": codigo, "saldo": str(saldo_cuenta(db, oid, codigo))}
        for clave, codigo in _CUENTAS_CONTROL
    }


def _resumen_asiento(a: Asiento) -> dict:
    total = sum((Decimal(str(ln.debe or 0)) for ln in a.lineas), _CERO)
    return {
        "id": a.id, "numero_asiento": a.numero_asiento, "modulo": a.modulo,
        "referencia_id": a.referencia_id, "fecha": a.fecha.isoformat() if a.fecha else None,
        "descripcion": a.descripcion, "total_debe": str(total),
    }


# ─── Reconstrucción ("Empezar limpio") ───────────────────────────────────────

_STATUS_OK = ["ok", "OK", "PAGO_PARCIAL", "CONCILIADO_CON_DIFERENCIA"]


def _extractos_activos(db: Session, oid: int) -> list:
    return (
        db.query(ExtractoBancario)
        .filter(ExtractoBancario.organizacion_id == oid, ExtractoBancario.deleted_at.is_(None))
        .order_by(ExtractoBancario.id)
        .all()
    )


def _lotes_um(db: Session, ids_extractos: list) -> dict:
    """Movimientos UM agrupados por (extracto, lote) — un asiento um_lote cada uno."""
    if not ids_extractos:
        return {}
    movs = (
        db.query(MovimientoBanco)
        .filter(MovimientoBanco.extracto_id.in_(ids_extractos), MovimientoBanco.source == "um")
        .order_by(MovimientoBanco.extracto_id, MovimientoBanco.um_lote, MovimientoBanco.id)
        .all()
    )
    lotes: dict = {}
    for m in movs:
        lotes.setdefault((m.extracto_id, m.um_lote or 0), []).append(m)
    return lotes


def _buckets_reclass(db: Session, oid: int, ids_extractos: list) -> dict:
    """Filas conciliadas agrupadas por (planilla, origen del movimiento). Solo
    planillas no borradas y movimientos de extractos no borrados."""
    from app.models.cliente import Cliente
    from app.models.planilla import Planilla, PlanillaRow

    filas_ok = (
        db.query(PlanillaRow, Planilla, Cliente)
        .join(Planilla, PlanillaRow.planilla_id == Planilla.id)
        .join(Cliente, Planilla.cliente_id == Cliente.id)
        .filter(
            Planilla.organizacion_id == oid,
            Planilla.deleted_at.is_(None),
            PlanillaRow.status.in_(_STATUS_OK),
        )
        .all()
    )
    ids_acreditados = {r.orden_movimiento_acreditado for r, _p, _c in filas_ok if r.orden_movimiento_acreditado}
    origen_por_mov = {}
    if ids_acreditados and ids_extractos:
        origen_por_mov = {
            mid: ("um" if src == "um" else "extracto")
            for mid, src in (
                db.query(MovimientoBanco.id, MovimientoBanco.source)
                .filter(MovimientoBanco.id.in_(ids_acreditados), MovimientoBanco.extracto_id.in_(ids_extractos))
                .all()
            )
        }
    buckets: dict = {}
    for row, planilla, cliente in filas_ok:
        origen = origen_por_mov.get(row.orden_movimiento_acreditado)
        if origen is None:
            continue
        key = (planilla.id, origen)
        if key not in buckets:
            buckets[key] = {"planilla": planilla, "cliente": cliente, "rows": []}
        buckets[key]["rows"].append(row)
    return buckets


def _contar_por_modulo(asientos: list) -> dict:
    out: dict = {}
    for (modulo,) in asientos:
        out[modulo or "(sin módulo)"] = out.get(modulo or "(sin módulo)", 0) + 1
    return dict(sorted(out.items()))


def plan_reconstruccion(db: Session, oid: int) -> dict:
    """Qué haría "Empezar limpio" (sin tocar nada): asientos a borrar y a
    conservar por módulo, y cuántos se crearían por fuente."""
    familia = modulos_del_rebuild()
    todos = db.query(Asiento.modulo).filter(Asiento.organizacion_id == oid).all()
    a_borrar = [t for t in todos if t[0] in familia]
    a_conservar = [t for t in todos if t[0] not in familia]
    n_detalles = (
        db.query(AsientoDetalle)
        .join(Asiento, AsientoDetalle.asiento_id == Asiento.id)
        .filter(Asiento.organizacion_id == oid, Asiento.modulo.in_(familia))
        .count()
    )
    extractos = _extractos_activos(db, oid)
    ids_ext = [e.id for e in extractos]
    dias = set()
    if ids_ext:
        for ext_id, fecha in (
            db.query(MovimientoBanco.extracto_id, MovimientoBanco.fecha)
            .filter(
                MovimientoBanco.extracto_id.in_(ids_ext),
                or_(MovimientoBanco.source.is_(None), MovimientoBanco.source != "um"),
            )
            .distinct()
            .all()
        ):
            dias.add((ext_id, fecha))
    n_extractos = len({ext_id for ext_id, _f in dias})
    n_lotes = len(_lotes_um(db, ids_ext))
    n_buckets = len(_buckets_reclass(db, oid, ids_ext))
    return {
        "a_borrar": {
            "asientos": len(a_borrar), "detalles": n_detalles,
            "por_modulo": _contar_por_modulo(a_borrar),
        },
        "a_conservar": {"asientos": len(a_conservar), "por_modulo": _contar_por_modulo(a_conservar)},
        "a_crear": {
            "extractos": n_extractos,
            "dias_extracto": len(dias),
            "um_lotes": n_lotes,
            "reclass_planilla_buckets": n_buckets,
            "total_asientos_nuevos": f"≤ {len(dias) + n_lotes + n_buckets} (+1 por bucket con comisión > 0)",
        },
    }


def renumerar(db: Session, oid: int) -> int:
    """Numera correlativamente 1..N todos los asientos de la org por (fecha, id)."""
    asientos = (
        db.query(Asiento).filter(Asiento.organizacion_id == oid)
        .order_by(Asiento.fecha, Asiento.id).all()
    )
    for i, a in enumerate(asientos, start=1):
        a.numero_asiento = i
    return len(asientos)


def reconstruir_asientos_banco(db: Session, oid: int, usuario_id: Optional[int]) -> dict:
    """Borra los asientos de `modulos_del_rebuild()` de la org y los rearma desde
    los datos (extractos, UM, planillas conciliadas) con el modelo de cuentas
    transitorias; conserva el resto y renumera 1..N. Todo en UNA transacción:
    no hace commit (lo hace el router) y lanza ante un error para que el router
    haga rollback y no quede el libro a medio borrar."""
    familia = modulos_del_rebuild()
    ids_borrar = [
        r[0] for r in db.query(Asiento.id)
        .filter(Asiento.organizacion_id == oid, Asiento.modulo.in_(familia)).all()
    ]
    n_detalles = 0
    if ids_borrar:
        n_detalles = (
            db.query(AsientoDetalle).filter(AsientoDetalle.asiento_id.in_(ids_borrar))
            .delete(synchronize_session=False)
        )
        db.query(Asiento).filter(Asiento.id.in_(ids_borrar)).delete(synchronize_session=False)
    # Los movimientos quedan sin asiento: se vuelven a registrar abajo.
    ids_ext_org = [r[0] for r in db.query(ExtractoBancario.id).filter(ExtractoBancario.organizacion_id == oid).all()]
    if ids_ext_org:
        db.query(MovimientoBanco).filter(
            MovimientoBanco.extracto_id.in_(ids_ext_org), MovimientoBanco.asiento_id.isnot(None),
        ).update({"asiento_id": None}, synchronize_session=False)
    db.flush()
    db.expire_all()

    if not mc.cuenta_banco_extracto(db, oid) or not mc.cuenta_banco_transitoria(db, oid, "ingreso") \
            or not mc.cuenta_banco_transitoria(db, oid, "egreso"):
        raise ValueError("Plan de cuentas incompleto: faltan Banco Macro (1-1-1-3-1) o las transitorias 2-1-1-1 / 2-1-1-2")

    creados = {"extracto_banco": 0, "um_lote": 0, "reclass": 0, "reclass_comision": 0}

    # ── Extracto principal: un asiento por día ──
    extractos = _extractos_activos(db, oid)
    for ext in extractos:
        creados["extracto_banco"] += len(mc.construir_asientos_extracto(db, ext, usuario_id))

    # ── UM: un asiento por (extracto, lote) ──
    for (ext_id, _lote), movs in sorted(_lotes_um(db, [e.id for e in extractos]).items()):
        if mc.construir_asiento_um_lote(db, ext_id, oid, usuario_id, movs) is not None:
            creados["um_lote"] += 1

    # ── Reclasificación por planilla, un bucket por origen ──
    # Mismo criterio que el flujo vivo (conciliacion.py::conciliar_planilla →
    # registrar_reclasificacion_planilla): No identificado D / Cliente H por el
    # NETO y, si hay comisión, No identificado D / Comisiones ganadas H aparte.
    no_id = mc.cuenta_banco_transitoria(db, oid, "ingreso")
    comisiones = mc._get_cuenta_por_codigo(db, "3-1-1-0", oid)
    cuentas_cliente: dict = {}
    for (planilla_id, origen), grupo in sorted(_buckets_reclass(db, oid, [e.id for e in extractos]).items(),
                                               key=lambda kv: (kv[0][0], kv[0][1])):
        planilla, cliente, rows = grupo["planilla"], grupo["cliente"], grupo["rows"]
        if cliente.id not in cuentas_cliente:
            cuentas_cliente[cliente.id] = mc._get_o_crear_cuenta_cliente(db, cliente.id, oid)
        cuenta_cli = cuentas_cliente[cliente.id]
        if not cuenta_cli:
            continue
        total = sum((abs(mc._monto(r.monto)) for r in rows), _CERO)
        if total <= 0:
            continue
        pct = Decimal(str(planilla.porcentaje_comision or 0))
        comision = round(total * pct / Decimal("100"), 2) if pct > 0 else _CERO
        neto = total - comision
        fechas = [r.fecha_acred for r in rows if r.fecha_acred]
        fecha = max(fechas) if fechas else planilla.fecha_carga or hoy_art()
        if isinstance(fecha, datetime):
            fecha = fecha.date()
        if not isinstance(fecha, date):
            fecha = hoy_art()
        modulo = mc.MODULO_RECLASS[origen]
        a = Asiento(
            fecha=fecha, descripcion=f"TT {cliente.nombre} — {planilla.nombre_archivo}",
            modulo=modulo, referencia_id=planilla_id, organizacion_id=oid, usuario_id=usuario_id,
            numero_asiento=mc._next_numero_asiento(db, oid),
        )
        db.add(a)
        db.flush()
        db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=no_id.id, debe=neto, haber=_CERO))
        db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=cuenta_cli.id, debe=_CERO, haber=neto))
        creados["reclass"] += 1
        if comision > 0 and comisiones:
            a2 = Asiento(
                fecha=fecha, descripcion=f"Comisión {pct}% — {cliente.nombre}",
                modulo=modulo + "_comision", referencia_id=planilla_id, organizacion_id=oid,
                usuario_id=usuario_id, numero_asiento=mc._next_numero_asiento(db, oid),
            )
            db.add(a2)
            db.flush()
            db.add(AsientoDetalle(asiento_id=a2.id, cuenta_id=no_id.id, debe=comision, haber=_CERO))
            db.add(AsientoDetalle(asiento_id=a2.id, cuenta_id=comisiones.id, debe=_CERO, haber=comision))
            creados["reclass_comision"] += 1
        db.flush()

    total_libro = renumerar(db, oid)
    n_creados = sum(creados.values())
    return {
        "borrados": {"asientos": len(ids_borrar), "detalles": n_detalles},
        "conservados": total_libro - n_creados,
        "creados": n_creados,
        "creados_por_modulo": creados,
        "total_libro": total_libro,
    }


# ─── Corrección explícita del histórico ──────────────────────────────────────

def _legacy_extracto_vigentes(db: Session, oid: int) -> list:
    """Asientos "extracto" del modelo viejo (registrar_extracto) sin reversar."""
    return [
        a for a in db.query(Asiento)
        .filter(Asiento.organizacion_id == oid, Asiento.modulo == mc.MODULO_EXTRACTO_LEGACY)
        .order_by(Asiento.id).all()
        if not mc.esta_reversado(db, a)
    ]


def _legacy_reclass_vigentes(db: Session, oid: int) -> list:
    """Asientos reclass_planilla_extracto(_comision) sin reversar que debitan
    Pasivo Corriente 2-1-0-0 (bucket del extracto principal del modelo viejo)."""
    pasivo = mc._get_cuenta_por_codigo(db, mc.CUENTA_PASIVO_CORRIENTE_LEGACY, oid)
    if not pasivo:
        return []
    modulos = (mc.MODULO_RECLASS_LEGACY_EXTRACTO, mc.MODULO_RECLASS_LEGACY_EXTRACTO + "_comision")
    out = []
    for a in (
        db.query(Asiento).filter(Asiento.organizacion_id == oid, Asiento.modulo.in_(modulos))
        .order_by(Asiento.id).all()
    ):
        if any(ln.cuenta_id == pasivo.id and (ln.debe or 0) > 0 for ln in a.lineas) and not mc.esta_reversado(db, a):
            out.append(a)
    return out


def _cuenta_pagos_a_imputar_info(db: Session, oid: int) -> dict:
    """Estado de 2-1-1-2 en el plan de la org (aviso si el código ya lo usa otra cuenta)."""
    c = db.query(PlanCuenta).filter(
        PlanCuenta.codigo == mc.CUENTA_PAGOS_A_IMPUTAR, PlanCuenta.organizacion_id == oid,
    ).first()
    if not c:
        return {"existe": False, "se_crea": True}
    return {
        "existe": True, "nombre": c.nombre, "activa": bool(c.activo),
        "ok": bool(c.activo) and (c.nombre or "").strip().lower() == "pagos a imputar",
    }


MODULO_UM_LOTE_CORREGIDO = "um_lote_corregido"
MODULO_UM_MOV_CORREGIDO = "um_mov_corregido"

# Módulos que son "datos del banco" (o su corrección): no van a la lista "a revisar".
_MODULOS_DATOS_BANCO = {
    mc.MODULO_EXTRACTO, mc.MODULO_EXTRACTO_LEGACY,
    "um_lote", "um_mov", MODULO_UM_LOTE_CORREGIDO, MODULO_UM_MOV_CORREGIDO,
}


def _legacy_um_vigentes(db: Session, oid: int) -> list:
    """Asientos um_lote / um_mov sin reversar cuyos egresos debitaron
    No identificado 2-1-1-1 (modelo viejo; hoy van contra 2-1-1-2)."""
    no_id = mc.cuenta_banco_transitoria(db, oid, "ingreso")
    if not no_id:
        return []
    out = []
    for a in (
        db.query(Asiento).filter(Asiento.organizacion_id == oid, Asiento.modulo.in_(("um_lote", "um_mov")))
        .order_by(Asiento.id).all()
    ):
        if any(ln.cuenta_id == no_id.id and (ln.debe or 0) > 0 for ln in a.lineas) and not mc.esta_reversado(db, a):
            out.append(a)
    return out


def _movimientos_del_asiento_um(db: Session, a: Asiento) -> list:
    """Movimientos UM que cubre un asiento um_lote (el lote de su primer
    movimiento, ordenado por id) o um_mov (el movimiento mismo)."""
    primer = db.query(MovimientoBanco).filter(MovimientoBanco.id == a.referencia_id).first()
    if primer is None or primer.source != "um":
        return []
    if a.modulo == "um_mov":
        return [primer]
    q = db.query(MovimientoBanco).filter(
        MovimientoBanco.extracto_id == primer.extracto_id, MovimientoBanco.source == "um",
    )
    q = q.filter(MovimientoBanco.um_lote == primer.um_lote) if primer.um_lote is not None \
        else q.filter(MovimientoBanco.um_lote.is_(None))
    movs = q.order_by(MovimientoBanco.id).all()
    return movs if movs and movs[0].id == primer.id else []


def _totales_banco(lineas, banco_id: int) -> tuple:
    debe = sum((Decimal(str(ln.debe or 0)) for ln in lineas if ln.cuenta_id == banco_id), _CERO)
    haber = sum((Decimal(str(ln.haber or 0)) for ln in lineas if ln.cuenta_id == banco_id), _CERO)
    return debe, haber


def _asientos_a_revisar(db: Session, oid: int) -> dict:
    """Asientos de módulos (egresos, cheques, tarjetas, liquidaciones, caja,
    ajustes…) que pegan directo contra el banco (Banco Macro o la cuenta madre)
    y siguen vigentes. La corrección NO los toca: se listan para revisarlos con
    el contador (con el extracto registrado, mueven el banco dos veces)."""
    ids_banco = [
        c.id for c in db.query(PlanCuenta).filter(
            PlanCuenta.organizacion_id == oid, PlanCuenta.codigo.in_((mc.CUENTA_BANCO_EXTRACTO, "1-1-1-3")),
        ).all()
    ]
    if not ids_banco:
        return {"cantidad": 0, "total": "0.00", "por_modulo": {}, "asientos": []}
    candidatos = (
        db.query(Asiento)
        .join(AsientoDetalle, AsientoDetalle.asiento_id == Asiento.id)
        .filter(Asiento.organizacion_id == oid, AsientoDetalle.cuenta_id.in_(ids_banco))
        .distinct().order_by(Asiento.id).all()
    )
    lista, total, por_modulo = [], _CERO, {}
    for a in candidatos:
        modulo = a.modulo or "(sin módulo)"
        if modulo in _MODULOS_DATOS_BANCO or modulo.endswith("_reverso") or mc.esta_reversado(db, a):
            continue
        monto = sum((Decimal(str(ln.debe or 0)) + Decimal(str(ln.haber or 0))
                     for ln in a.lineas if ln.cuenta_id in ids_banco), _CERO)
        total += monto
        por_modulo[modulo] = por_modulo.get(modulo, 0) + 1
        r = _resumen_asiento(a)
        r["monto_banco"] = str(monto)
        lista.append(r)
    return {"cantidad": len(lista), "total": str(total.quantize(Decimal("0.01"))),
            "por_modulo": dict(sorted(por_modulo.items())), "asientos": lista}


def corregir_asientos_banco(db: Session, oid: int, usuario_id: Optional[int], dry_run: bool = True) -> dict:
    """Corrige el histórico del banco al modelo de cuentas transitorias, sin
    borrar ni editar ningún asiento existente:

    1. Cada asiento "extracto" viejo (abs() de todo, cuenta madre 1-1-1-3 contra
       Pasivo Corriente) → un REVERSO ("extracto_reverso").
    2. Cada reclasificación vieja que debitó Pasivo Corriente 2-1-0-0
       (reclass_planilla_extracto[_comision]) → un REVERSO y la misma
       reclasificación rehecha contra No identificado 2-1-1-1 en
       reclass_planilla_principal[_comision] (mismos montos, fecha y cliente).
    3. Cada um_lote / um_mov viejo cuyos egresos debitaron 2-1-1-1 → un REVERSO
       y el mismo asiento rehecho con el armador actual (egresos contra 2-1-1-2)
       en um_lote_corregido / um_mov_corregido (el índice único no deja repetir
       el módulo para la misma referencia), con la fecha del original. Solo si
       los movimientos del lote siguen dando los mismos importes de banco que
       el asiento viejo; si no, se informa en `conflictos` y no se toca. El
       saldo del banco no cambia (solo se mueve la contrapartida de los egresos).
    4. Los movimientos del extracto principal sin asiento (extractos no
       borrados) → registrados con construir_asientos_extracto (uno por día,
       fecha real, Banco Macro contra 2-1-1-1 / 2-1-1-2).

    Fuera de alcance (solo se listan en `a_revisar`, con cantidad y total):
    egresos, cheques, tarjetas, liquidaciones, caja y ajustes viejos que pegan
    directo contra el banco.

    Los reversos llevan la fecha del asiento original, así los saldos por fecha
    del Mayor quedan coherentes con los asientos nuevos (que van con la fecha
    del movimiento). Los asientos nuevos se numeran a continuación del último:
    no se renumera nada existente.

    Idempotente: una segunda corrida no encuentra nada que reversar ni
    movimientos sin asiento. dry_run=True arma todo dentro de la transacción,
    calcula los saldos resultantes y hace rollback: no persiste nada.
    No hace commit si dry_run=False: lo hace el router (junto con la auditoría)."""
    saldos_antes = saldos_cuentas_banco(db, oid)
    cuenta_2112 = _cuenta_pagos_a_imputar_info(db, oid)
    a_revisar = _asientos_a_revisar(db, oid)
    motivo = "Corrección al modelo de cuentas transitorias (oct 2026)"

    legacy_ext = _legacy_extracto_vigentes(db, oid)
    legacy_rec = _legacy_reclass_vigentes(db, oid)
    legacy_um = _legacy_um_vigentes(db, oid)

    reversados: list = []
    creados: list = []
    conflictos: list = []
    no_id = mc.cuenta_banco_transitoria(db, oid, "ingreso")
    pasivo = mc._get_cuenta_por_codigo(db, mc.CUENTA_PASIVO_CORRIENTE_LEGACY, oid)
    banco = mc.cuenta_banco_extracto(db, oid)

    def _reversar(a: Asiento) -> None:
        resumen = _resumen_asiento(a)
        rev = mc.construir_reverso(db, a, usuario_id, motivo, fecha=a.fecha)
        if rev is not None:
            reversados.append(resumen)
            creados.append(rev)

    for a in legacy_ext:
        _reversar(a)

    for a in legacy_rec:
        modulo_nuevo = (
            mc.MODULO_RECLASS["extracto"] + ("_comision" if a.modulo.endswith("_comision") else "")
        )
        ya = db.query(Asiento).filter(
            Asiento.modulo == modulo_nuevo, Asiento.referencia_id == a.referencia_id,
            Asiento.organizacion_id == oid,
        ).first()
        if ya is not None:
            # Ya hay una reclasificación nueva para esa planilla: rehacer la vieja
            # duplicaría la acreditación. Se informa y no se toca.
            conflictos.append({"asiento_id": a.id, "modulo": a.modulo, "planilla_id": a.referencia_id,
                               "motivo": f"ya existe {modulo_nuevo} #{ya.id}"})
            continue
        _reversar(a)
        nuevo = Asiento(
            fecha=a.fecha, descripcion=a.descripcion, modulo=modulo_nuevo,
            referencia_id=a.referencia_id, organizacion_id=oid, usuario_id=usuario_id,
            numero_asiento=mc._next_numero_asiento(db, oid),
        )
        db.add(nuevo)
        db.flush()
        for ln in a.lineas:
            cuenta_id = no_id.id if (pasivo and ln.cuenta_id == pasivo.id) else ln.cuenta_id
            db.add(AsientoDetalle(asiento_id=nuevo.id, cuenta_id=cuenta_id, debe=ln.debe, haber=ln.haber))
        db.flush()
        creados.append(nuevo)

    for a in legacy_um:
        modulo_nuevo = MODULO_UM_MOV_CORREGIDO if a.modulo == "um_mov" else MODULO_UM_LOTE_CORREGIDO
        movs = _movimientos_del_asiento_um(db, a)
        if not movs or not banco:
            conflictos.append({"asiento_id": a.id, "modulo": a.modulo, "referencia_id": a.referencia_id,
                               "motivo": "no se encontraron los movimientos UM del asiento"})
            continue
        pos = sum((max(mc._monto(m.monto), _CERO) for m in movs), _CERO)
        neg = sum((-min(mc._monto(m.monto), _CERO) for m in movs), _CERO)
        if (pos, neg) != _totales_banco(a.lineas, banco.id):
            conflictos.append({"asiento_id": a.id, "modulo": a.modulo, "referencia_id": a.referencia_id,
                               "motivo": "los movimientos ya no suman lo mismo que el asiento (se editaron)"})
            continue
        if db.query(Asiento.id).filter(Asiento.modulo == modulo_nuevo, Asiento.referencia_id == a.referencia_id,
                                       Asiento.organizacion_id == oid).first():
            conflictos.append({"asiento_id": a.id, "modulo": a.modulo, "referencia_id": a.referencia_id,
                               "motivo": f"ya existe {modulo_nuevo}"})
            continue
        _reversar(a)
        if a.modulo == "um_mov":
            nuevo = mc.construir_asiento_um_mov(db, movs[0], oid, usuario_id, modulo=modulo_nuevo)
        else:
            nuevo = mc.construir_asiento_um_lote(db, movs[0].extracto_id, oid, usuario_id, movs,
                                                 modulo=modulo_nuevo)
        if nuevo is None:
            raise ValueError(f"No se pudo rehacer el asiento UM #{a.id}")
        nuevo.fecha = a.fecha  # misma fecha que el original
        db.flush()
        creados.append(nuevo)

    for ext in _extractos_activos(db, oid):
        creados.extend(mc.construir_asientos_extracto(db, ext, usuario_id))

    db.flush()
    for a in creados:
        db.refresh(a)
    a_crear = [_resumen_asiento(a) for a in creados]
    saldos_despues = saldos_cuentas_banco(db, oid)
    resumen_modulos: dict = {}
    for a in creados:
        resumen_modulos[a.modulo] = resumen_modulos.get(a.modulo, 0) + 1

    resultado = {
        "dry_run": dry_run,
        "org_id": oid,
        "a_reversar": reversados,
        "a_crear": a_crear,
        "a_crear_por_modulo": dict(sorted(resumen_modulos.items())),
        "conflictos": conflictos,
        "a_revisar": a_revisar,
        "saldos_antes": saldos_antes,
        "saldos_despues": saldos_despues,
        "cuenta_pagos_a_imputar": cuenta_2112,
        "nada_que_corregir": not a_crear,
    }
    if dry_run:
        db.rollback()
    return resultado


# ─── Control: banco en libros vs. extracto ───────────────────────────────────

def _tramos_de_saldo(db: Session, ids_ext: list) -> list:
    """Cada bloque continuo de movimientos con saldo: el extracto principal y los UM de
    cada extracto, por separado. El orden dentro del archivo varía según el banco (más
    nuevo arriba o abajo), así que se ordena por fecha y, dentro del día, por `orden` en
    el sentido que encadena los saldos (saldo anterior + monto = saldo). Devuelve por
    tramo: fechas, saldo inicial/final, neto y si cuadra por dentro."""
    filas = (
        db.query(
            MovimientoBanco.extracto_id, MovimientoBanco.source, MovimientoBanco.fecha,
            MovimientoBanco.orden, MovimientoBanco.id, MovimientoBanco.monto, MovimientoBanco.saldo,
        )
        .filter(
            MovimientoBanco.extracto_id.in_(ids_ext),
            MovimientoBanco.saldo.isnot(None), MovimientoBanco.fecha.isnot(None),
        )
        .all()
    )
    bloques: dict = {}
    for f in filas:
        clave = (f.extracto_id, "um" if f.source == "um" else "principal")
        bloques.setdefault(clave, []).append(f)

    def _saltos(movs):
        return sum(
            1 for a, b in zip(movs, movs[1:])
            if abs(Decimal(str(a.saldo)) + Decimal(str(b.monto)) - Decimal(str(b.saldo))) > Decimal("0.01")
        )

    tramos = []
    for (extracto_id, origen), movs in bloques.items():
        asc = sorted(movs, key=lambda m: (_a_fecha(m.fecha), m.orden or 0, m.id))
        desc = sorted(movs, key=lambda m: (_a_fecha(m.fecha), -(m.orden or 0), -m.id))
        orden = min((asc, desc), key=_saltos)
        primero, ultimo = orden[0], orden[-1]
        ini = Decimal(str(primero.saldo)) - Decimal(str(primero.monto))
        fin = Decimal(str(ultimo.saldo))
        neto = sum((Decimal(str(m.monto)) for m in orden), _CERO)
        tramos.append({
            "extracto_id": extracto_id, "origen": origen,
            "desde": str(_a_fecha(primero.fecha)), "hasta": str(_a_fecha(ultimo.fecha)),
            "saldo_inicial": str(ini.quantize(Decimal("0.01"))),
            "saldo_final": str(fin.quantize(Decimal("0.01"))),
            "neto": str(neto.quantize(Decimal("0.01"))),
            "cuadra": abs(fin - ini - neto) <= Decimal("0.01"),
        })
    tramos.sort(key=lambda t: (t["desde"], t["hasta"], t["origen"] != "principal"))
    return tramos


def _a_fecha(f):
    return f.date() if isinstance(f, datetime) else f


def _huecos(tramos: list) -> list:
    """Entre tramos consecutivos, el saldo de arranque del siguiente debería ser el
    saldo final del anterior. Si no, faltan movimientos sin cargar en el medio."""
    huecos = []
    for a, b in zip(tramos, tramos[1:]):
        dif = Decimal(b["saldo_inicial"]) - Decimal(a["saldo_final"])
        if abs(dif) > Decimal("0.01"):
            huecos.append({
                "desde": a["hasta"], "hasta": b["desde"],
                "saldo_antes": a["saldo_final"], "saldo_despues": b["saldo_inicial"],
                "monto_faltante": str(dif.quantize(Decimal("0.01"))),
            })
    return huecos


def control_banco(db: Session, oid: int) -> dict:
    """Saldo de Banco Macro en el Libro vs. el saldo del último extracto, más
    los saldos de las transitorias. Si todo el banco está registrado, el saldo
    en libros = suma de los movimientos (extracto + UM) = saldo final del último
    extracto − saldo inicial del primero (no hay asiento de apertura)."""
    extractos = _extractos_activos(db, oid)
    ids_ext = [e.id for e in extractos]
    suma_movs = _CERO
    sin_asiento = 0
    saldo_final = None
    saldo_inicial = None
    tramos: list = []
    if ids_ext:
        suma_movs = Decimal(str(
            db.query(func.coalesce(func.sum(MovimientoBanco.monto), 0))
            .filter(MovimientoBanco.extracto_id.in_(ids_ext)).scalar() or 0
        ))
        sin_asiento = (
            db.query(MovimientoBanco)
            .filter(
                MovimientoBanco.extracto_id.in_(ids_ext),
                or_(MovimientoBanco.source.is_(None), MovimientoBanco.source != "um"),
                MovimientoBanco.asiento_id.is_(None),
            ).count()
        )
        # Saldos del banco: del primer y último tramo continuo (ver _tramos_de_saldo).
        tramos = _tramos_de_saldo(db, ids_ext)
        if tramos:
            saldo_inicial = Decimal(tramos[0]["saldo_inicial"])
            saldo_final = Decimal(tramos[-1]["saldo_final"])

    saldos = saldos_cuentas_banco(db, oid)
    libro = Decimal(saldos["banco"]["saldo"])
    dif_movs = (libro - suma_movs).quantize(Decimal("0.01"))
    dif_extracto = None
    if saldo_final is not None and saldo_inicial is not None:
        dif_extracto = (saldo_final - saldo_inicial - libro).quantize(Decimal("0.01"))
    huecos = _huecos(tramos)
    return {
        "org_id": oid,
        "saldo_libro_banco": str(libro),
        "tramos": tramos,
        "huecos": huecos,
        "tramos_que_no_cuadran": sum(1 for t in tramos if not t["cuadra"]),
        "saldo_real_banco": tramos[-1]["saldo_final"] if tramos else None,
        "fecha_saldo_real_banco": tramos[-1]["hasta"] if tramos else None,
        "suma_movimientos_extractos": str(suma_movs.quantize(Decimal("0.01"))),
        "diferencia_libro_vs_movimientos": str(dif_movs),
        "saldo_ultimo_extracto": str(saldo_final) if saldo_final is not None else None,
        "saldo_inicial_primer_extracto": str(saldo_inicial) if saldo_inicial is not None else None,
        "diferencia_libro_vs_extracto": str(dif_extracto) if dif_extracto is not None else None,
        "movimientos_extracto_sin_asiento": sin_asiento,
        "saldos": saldos,
        "ok": dif_movs == 0 and sin_asiento == 0,
        "nota": (
            "Banco Macro debe igualar la suma de los movimientos de los extractos (no hay asiento "
            "de apertura: la diferencia contra el saldo del banco es el saldo inicial del primero). "
            "Si entre dos extractos el saldo no encadena, faltan movimientos sin cargar (`huecos`): "
            "la diferencia contra el extracto es la suma de esos huecos, no un error contable. "
            "2-1-1-1 acreedora = cobros del banco sin imputar a un cliente; 2-1-1-2 deudora = débitos "
            "del banco sin un pago cargado, acreedora = pagos cargados que el banco todavía no debitó."
        ),
    }
