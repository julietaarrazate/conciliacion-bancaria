"""Router contabilidad — Cuentas corrientes de clientes.

Rutas expuestas (bajo el prefix /contabilidad del router padre):
  GET   /cuentas-corrientes
  GET   /cuenta-corriente
  GET   /cuenta-corriente/exportar-pdf
  POST  /backfill-cuentas-corrientes
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import require_permission
from app.models.cliente import Cliente
from app.models.contabilidad import Asiento, AsientoDetalle, PlanCuenta
from app.models.user import User
from app.services.tz import hoy_art
from .ctb_common import _org_id, _STATUS_CONCILIADO, _tipo_de_modulo

router = APIRouter(tags=["contabilidad"])
logger = logging.getLogger(__name__)


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

    # um_reclass_planilla: referencia_id = planilla_id directamente
    reclass_planilla_ids = {
        a.referencia_id for _, a in filas
        if a.modulo == "um_reclass_planilla" and a.referencia_id
    }
    # um_reclass (legacy per-fila) / cc_inicial: referencia_id = planilla_row_id
    row_ids = [
        a.referencia_id for _, a in filas
        if a.modulo in ("um_reclass", "cc_inicial") and a.referencia_id
    ]
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
        elif modulo == "um_reclass_planilla":
            # referencia_id es directamente el planilla_id
            origen["planilla_id"] = a.referencia_id
        elif modulo in ("um_reclass", "cc_inicial"):
            info = row_map.get(a.referencia_id)
            if info:
                origen["planilla_id"] = info["planilla_id"]
                if info.get("movimiento_id"):
                    origen["movimiento_id"] = info["movimiento_id"]
                    origen["extracto_id"] = mov_map.get(info["movimiento_id"])
                elif modulo == "um_reclass":
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


@router.get("/cuenta-corriente/exportar-pdf")
def exportar_cta_cte_pdf(
    cliente_id: int = Query(...),
    desde: Optional[str] = Query(None),
    hasta: Optional[str] = Query(None),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage_finance")),
):
    """Exporta la cuenta corriente del cliente como PDF."""
    from fastapi.responses import StreamingResponse
    import io
    # Reutiliza la misma lógica que get_cuenta_corriente
    data = get_cuenta_corriente(
        cliente_id=cliente_id, desde=desde, hasta=hasta,
        org_id=org_id, db=db, current_user=current_user,
    )
    from app.services.pdf_export import cuenta_corriente_pdf
    pdf_bytes = cuenta_corriente_pdf(data)
    nombre = (data.get("cliente") or {}).get("nombre", "cliente")
    nombre_safe = "".join(c for c in nombre if c.isalnum() or c in " _-").strip().replace(" ", "_")
    fname = f"cta_cte_{nombre_safe}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


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
