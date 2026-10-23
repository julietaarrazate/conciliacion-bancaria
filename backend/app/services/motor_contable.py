"""
Motor contable — Fase 2.
Genera asientos automáticos cuando ocurren operaciones en el sistema.
Siempre encapsulado en try/except: si falla, la operación principal NO se revierte.
Idempotente: nunca crea dos asientos para el mismo (modulo, referencia_id, org_id).
"""

import logging
from datetime import date
from decimal import Decimal
from typing import Optional
from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.contabilidad import PlanCuenta, ReglaContable, Asiento, AsientoDetalle
from app.services.tz import hoy_art

logger = logging.getLogger(__name__)


def _get_regla(db: Session, evento: str, org_id: int) -> Optional[ReglaContable]:
    return (
        db.query(ReglaContable)
        .filter(
            ReglaContable.evento == evento,
            ReglaContable.organizacion_id == org_id,
            ReglaContable.activo == True,
        )
        .first()
    )


def _ya_existe(db: Session, modulo: str, referencia_id: int, org_id: int) -> bool:
    return (
        db.query(Asiento)
        .filter(
            Asiento.modulo == modulo,
            Asiento.referencia_id == referencia_id,
            Asiento.organizacion_id == org_id,
        )
        .first()
    ) is not None


def _next_numero_asiento(db: Session, org_id: int) -> int:
    """Devuelve el próximo numero_asiento correlativo para la org."""
    max_num = db.query(func.max(Asiento.numero_asiento)).filter(
        Asiento.organizacion_id == org_id
    ).scalar()
    return (max_num or 0) + 1


def _monto(v) -> Decimal:
    try:
        return round(Decimal(str(v).replace(",", ".").replace("$", "").strip()), 2)
    except Exception:
        return Decimal("0")


def _crear_asiento(
    db: Session,
    regla: ReglaContable,
    fecha: date,
    descripcion: str,
    modulo: str,
    referencia_id: int,
    org_id: int,
    usuario_id: Optional[int],
    monto: Decimal,
) -> None:
    a = Asiento(
        fecha=fecha,
        descripcion=descripcion,
        modulo=modulo,
        referencia_id=referencia_id,
        organizacion_id=org_id,
        usuario_id=usuario_id,
        numero_asiento=_next_numero_asiento(db, org_id),
    )
    db.add(a)
    try:
        db.flush()
    except IntegrityError:
        # Otro request creó el asiento en paralelo (race con unique constraint).
        # Salir limpio: el asiento ya existe gracias al otro request.
        db.rollback()
        return
    db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=regla.cuenta_debe_id,  debe=monto, haber=Decimal("0")))
    db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=regla.cuenta_haber_id, debe=Decimal("0"),  haber=monto))


# ─── Extracto bancario principal ─────────────────────────────────────────────
#
# Módulo "extracto_banco": UN asiento por DÍA de movimientos del extracto
# principal (no UM — esos los registra um_lote). Fecha del asiento = fecha de
# los movimientos, así el Libro Diario y el Mayor de Banco siguen las fechas
# reales del banco. Por día, a lo sumo dos pares de líneas:
#     Ingresos del día: Banco Macro D / 2-1-1-1 No identificado H
#     Egresos del día:  2-1-1-2 Pagos a imputar D / Banco Macro H
# referencia_id = id del primer movimiento (menor id) del grupo — mismo criterio
# que um_lote — para respetar el índice único (modulo, referencia_id, org).
# Idempotencia a nivel movimiento: cada movimiento registrado queda marcado con
# MovimientoBanco.asiento_id; correr de nuevo solo toma los que no tienen
# asiento. Reemplaza al viejo registrar_extracto (módulo "extracto": regla
# carga_extracto, cuenta madre 1-1-1-3, abs() de todo contra Pasivo Corriente y
# fecha de hoy), que inflaba el banco con los egresos. Esos asientos viejos se
# corrigen solo con POST /contabilidad/corregir-asientos-banco.

MODULO_EXTRACTO = "extracto_banco"
MODULO_EXTRACTO_LEGACY = "extracto"


def _fecha_movimiento(m, extracto) -> date:
    """Fecha contable de un movimiento: la suya; si no tiene, la del extracto."""
    if isinstance(getattr(m, "fecha", None), date):
        return m.fecha
    if extracto is not None and isinstance(getattr(extracto, "fecha_extracto", None), date):
        return extracto.fecha_extracto
    if extracto is not None and getattr(extracto, "fecha_creacion", None):
        return extracto.fecha_creacion.date()
    return hoy_art()


def movimientos_extracto_sin_asiento(db: Session, extracto_id: int) -> list:
    """Movimientos del extracto principal (source != "um") todavía sin asiento."""
    from sqlalchemy import or_
    from app.models.extracto import MovimientoBanco
    return (
        db.query(MovimientoBanco)
        .filter(
            MovimientoBanco.extracto_id == extracto_id,
            or_(MovimientoBanco.source.is_(None), MovimientoBanco.source != "um"),
            MovimientoBanco.asiento_id.is_(None),
        )
        .order_by(MovimientoBanco.id)
        .all()
    )


def construir_asientos_extracto(db: Session, extracto, usuario_id: Optional[int]) -> list:
    """Arma (sin commit) los asientos "extracto_banco" de los movimientos del
    extracto principal que todavía no tienen asiento. Devuelve los asientos
    creados. Lanza excepción ante un error — el que llama decide el commit o
    rollback (así lo puede usar "Empezar limpio" dentro de su transacción)."""
    org_id = extracto.organizacion_id or 1
    movs = movimientos_extracto_sin_asiento(db, extracto.id)
    if not movs:
        return []
    banco = cuenta_banco_extracto(db, org_id)
    cobros = cuenta_banco_transitoria(db, org_id, "ingreso")
    pagos = cuenta_banco_transitoria(db, org_id, "egreso")
    if not banco or not cobros or not pagos:
        logger.warning(
            "Cuentas del extracto no encontradas org %s (%s / %s / %s) — no se postea",
            org_id, CUENTA_BANCO_EXTRACTO, CUENTA_COBROS_A_IMPUTAR, CUENTA_PAGOS_A_IMPUTAR,
        )
        return []

    grupos: dict = {}
    for m in movs:
        grupos.setdefault(_fecha_movimiento(m, extracto), []).append(m)

    creados = []
    nombre = extracto.nombre_archivo or f"#{extracto.id}"
    for fecha in sorted(grupos):
        grupo = grupos[fecha]
        ingresos = sum((_monto(m.monto) for m in grupo if _monto(m.monto) > 0), Decimal("0"))
        egresos = sum((-_monto(m.monto) for m in grupo if _monto(m.monto) < 0), Decimal("0"))
        if ingresos <= 0 and egresos <= 0:
            continue
        ref = min(m.id for m in grupo)
        existente = (
            db.query(Asiento)
            .filter(
                Asiento.modulo == MODULO_EXTRACTO,
                Asiento.referencia_id == ref,
                Asiento.organizacion_id == org_id,
            )
            .first()
        )
        if existente:
            # Ya registrado (p. ej. por otro request): solo marcar los movimientos.
            for m in grupo:
                m.asiento_id = existente.id
            continue
        lineas = []
        if ingresos > 0:
            lineas += [(banco.id, ingresos, Decimal("0")), (cobros.id, Decimal("0"), ingresos)]
        if egresos > 0:
            lineas += [(pagos.id, egresos, Decimal("0")), (banco.id, Decimal("0"), egresos)]
        total_debe = sum(d for _c, d, _h in lineas)
        total_haber = sum(h for _c, _d, h in lineas)
        if total_debe != total_haber:  # red de seguridad de partida doble
            raise ValueError(f"Asiento extracto {extracto.id} {fecha} no balancea")
        a = Asiento(
            fecha=fecha,
            descripcion=f"Extracto {nombre} — movimientos del {fecha.strftime('%d/%m/%Y')} ({len(grupo)})",
            modulo=MODULO_EXTRACTO,
            referencia_id=ref,
            organizacion_id=org_id,
            usuario_id=usuario_id,
            numero_asiento=_next_numero_asiento(db, org_id),
        )
        db.add(a)
        db.flush()
        for cuenta_id, debe, haber in lineas:
            db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=cuenta_id, debe=debe, haber=haber))
        for m in grupo:
            m.asiento_id = a.id
        db.flush()
        creados.append(a)
    return creados


def registrar_asientos_extracto(db: Session, extracto_id: int, usuario_id: Optional[int]) -> bool:
    """Registra en el Libro Diario los movimientos del extracto principal que
    todavía no tienen asiento (ver construir_asientos_extracto). Lo llaman el
    upload de Excel y la confirmación de un PDF nuevo. Idempotente; un extracto
    borrado no se registra. Tolerante a fallos: devuelve False si no pudo
    (el extracto ya quedó guardado, igual que con el asiento de UM)."""
    try:
        from app.models.extracto import ExtractoBancario
        extracto = db.query(ExtractoBancario).filter(ExtractoBancario.id == extracto_id).first()
        if not extracto or extracto.deleted_at is not None:
            return True
        construir_asientos_extracto(db, extracto, usuario_id)
        db.commit()
        return True
    except Exception as ex:
        db.rollback()
        logger.warning("Error asiento extracto %s: %s", extracto_id, ex)
        return False


def asientos_de_extracto(db: Session, extracto_id: int, org_id: int) -> list:
    """Asientos "extracto_banco" que registraron movimientos de este extracto."""
    from app.models.extracto import MovimientoBanco
    ids = {
        r[0] for r in db.query(MovimientoBanco.asiento_id)
        .filter(MovimientoBanco.extracto_id == extracto_id, MovimientoBanco.asiento_id.isnot(None))
        .distinct().all()
    }
    if not ids:
        return []
    return (
        db.query(Asiento)
        .filter(Asiento.id.in_(ids), Asiento.organizacion_id == org_id, Asiento.modulo == MODULO_EXTRACTO)
        .order_by(Asiento.id)
        .all()
    )


def _crear_asiento_multilinea(
    db: Session,
    fecha: date,
    descripcion: str,
    modulo: str,
    referencia_id: int,
    org_id: int,
    usuario_id: Optional[int],
    lineas: list,  # [(cuenta_id, debe, haber), ...]
) -> None:
    """Crea un asiento con N líneas de detalle. lineas = [(cuenta_id, debe, haber)].
    Red de seguridad: si las líneas no cuadran en partida doble (Σdebe ≠ Σhaber)
    NO se postea el asiento — evita corromper el balance silenciosamente."""
    total_debe  = sum(_monto(d) for _, d, _h in lineas)
    total_haber = sum(_monto(h) for _, _d, h in lineas)
    if abs(total_debe - total_haber) > Decimal("0.01"):
        logger.error(
            "Asiento %s ref %s NO balancea (debe=%s haber=%s) — no se postea",
            modulo, referencia_id, total_debe, total_haber,
        )
        return
    a = Asiento(
        fecha=fecha,
        descripcion=descripcion,
        modulo=modulo,
        referencia_id=referencia_id,
        organizacion_id=org_id,
        usuario_id=usuario_id,
        numero_asiento=_next_numero_asiento(db, org_id),
    )
    db.add(a)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return
    for cuenta_id, debe, haber in lineas:
        db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=cuenta_id, debe=debe, haber=haber))


def registrar_cheque(
    db: Session,
    cheque_id: int,
    org_id: int,
    usuario_id: Optional[int],
    titular: str,
    monto: Decimal,
    comision: Decimal,
    fecha: date,
) -> None:
    """Registro cheque (nueva regla contador):
       Cheques en cartera (1-1-2-1) D  /  Cheques depositados (2-1-3-1) H (neto)
                                        /  Comisiones cheques (3-1-3-0) H (comisión)
    Reemplaza el esquema anterior (cheque_carga / cheque_comision)."""
    try:
        if _ya_existe(db, "cheque_registro", cheque_id, org_id):
            return
        monto    = round(_monto(monto), 2)
        comision = round(_monto(comision), 2)
        if monto <= 0:
            return
        neto = monto - comision
        if neto <= 0:
            logger.warning("Cheque %s: valor neto <= 0, se omite asiento", cheque_id)
            return

        cartera    = _get_cuenta_por_codigo(db, "1-1-2-1", org_id)
        depositados = _get_cuenta_por_codigo(db, "2-1-3-1", org_id)
        comisiones = _get_cuenta_por_codigo(db, "3-1-3-0", org_id)
        if not cartera or not depositados or not comisiones:
            logger.warning("Cuentas cheque no encontradas org %s (1-1-2-1/2-1-3-1/3-1-3-0)", org_id)
            return

        lineas = [
            (cartera.id,    monto,    Decimal("0")),
            (depositados.id, Decimal("0"), neto),
        ]
        if comision > 0:
            lineas.append((comisiones.id, Decimal("0"), comision))

        _crear_asiento_multilinea(
            db=db, fecha=fecha,
            descripcion=f"Cheque {titular or ''} — registro",
            modulo="cheque_registro",
            referencia_id=cheque_id,
            org_id=org_id,
            usuario_id=usuario_id,
            lineas=lineas,
        )
        db.commit()
    except Exception as ex:
        db.rollback()
        logger.warning("Error asiento cheque registro %s: %s", cheque_id, ex)


def acreditar_cheque(
    db: Session,
    cheque_id: int,
    org_id: int,
    usuario_id: Optional[int],
    titular: str,
    monto: Decimal,
    neto: Decimal,
    banco_cuenta_id: int,
    cliente_cuenta_id: int,
    fecha: date,
) -> None:
    """Acreditación cheque — 2 asientos (nueva regla contador):
    A1: No identificado 2-1-1-1 (D) / Cheques en cartera (H) →  el dinero entra al banco
    A2: Cheques depositados (D) / Cliente (H) →  cancela pasivo tránsito y acredita al cliente
    A1 no debita el banco: el crédito del extracto ya lo hace (Banco D / 2-1-1-1 H) y
    este asiento cancela esa transitoria (modelo de cuentas transitorias, oct 2026).
    banco_cuenta_id se sigue validando y guardando en el cheque como referencia.
    TODO multi-banco: con una cuenta por banco, la transitoria podría ser por banco."""
    try:
        monto = round(_monto(monto), 2)
        neto  = round(_monto(neto),  2)
        if monto <= 0:
            return

        cartera    = _get_cuenta_por_codigo(db, "1-1-2-1", org_id)
        depositados = _get_cuenta_por_codigo(db, "2-1-3-1", org_id)
        banco_elegido = db.query(PlanCuenta).filter(PlanCuenta.id == banco_cuenta_id).first()
        banco = cuenta_banco_transitoria(db, org_id, "ingreso") if banco_elegido else None
        cliente_cuenta = db.query(PlanCuenta).filter(PlanCuenta.id == cliente_cuenta_id).first()

        if not cartera or not depositados or not banco or not cliente_cuenta:
            logger.warning("Cuentas acreditación cheque no encontradas org %s cheque %s", org_id, cheque_id)
            return

        # A1: No identificado (en lugar de Banco) D / Cheques en cartera H
        if not _ya_existe(db, "cheque_acred_banco", cheque_id, org_id):
            _crear_asiento_directo(
                db=db, fecha=fecha,
                descripcion=f"Cheque {titular or ''} — acreditado banco",
                modulo="cheque_acred_banco",
                referencia_id=cheque_id,
                org_id=org_id,
                usuario_id=usuario_id,
                cuenta_debe_id=banco.id,
                cuenta_haber_id=cartera.id,
                monto=monto,
            )

        # A2: Cheques depositados D / Cliente H
        if not _ya_existe(db, "cheque_acred_cliente", cheque_id, org_id):
            _crear_asiento_directo(
                db=db, fecha=fecha,
                descripcion=f"Cheque {titular or ''} — acreditado cliente",
                modulo="cheque_acred_cliente",
                referencia_id=cheque_id,
                org_id=org_id,
                usuario_id=usuario_id,
                cuenta_debe_id=depositados.id,
                cuenta_haber_id=cliente_cuenta.id,
                monto=neto,
            )

        db.commit()
    except Exception as ex:
        db.rollback()
        logger.warning("Error asiento cheque acred %s: %s", cheque_id, ex)


def rechazar_cheque(
    db: Session,
    cheque_id: int,
    org_id: int,
    usuario_id: Optional[int],
    titular: str,
    monto: Decimal,
    gastos: Decimal,
    banco_cuenta_id: int,
    cliente_cuenta_id: int,
    fecha: date,
) -> None:
    """Rechazo cheque — 3 asientos (regla contador junio 2026):
    A1: Cliente (D) / Pagos a imputar 2-1-1-2 (H)     →  reversión del cheque acreditado
    A2: Cliente (D) / Gastos de rechazos 3-2-2-1 (H)  →  traslado de gastos al cliente
    A3: Gastos de rechazos 3-2-2-1 (D) / Pagos a imputar 2-1-1-2 (H) →  débito bancario real
    El Haber de A1 y A3 era Banco: el débito del extracto ya mueve el banco
    (2-1-1-2 D / Banco H), así que acá se acredita la transitoria de pagos
    (modelo de cuentas transitorias, oct 2026)."""
    try:
        monto  = round(_monto(monto),  2)
        gastos = round(_monto(gastos), 2)
        if monto <= 0:
            return

        banco_elegido  = db.query(PlanCuenta).filter(PlanCuenta.id == banco_cuenta_id).first()
        banco          = cuenta_banco_transitoria(db, org_id, "egreso") if banco_elegido else None
        cliente_cuenta = db.query(PlanCuenta).filter(PlanCuenta.id == cliente_cuenta_id).first()
        gtos_rechazos  = _get_cuenta_por_codigo(db, "3-2-2-1", org_id)

        if not banco or not cliente_cuenta or not gtos_rechazos:
            logger.warning("Cuentas rechazo cheque no encontradas org %s cheque %s", org_id, cheque_id)
            return

        # A1: Cliente D / Banco H — reversión
        if not _ya_existe(db, "cheque_rechazo_banco", cheque_id, org_id):
            _crear_asiento_directo(
                db=db, fecha=fecha,
                descripcion=f"Cheque {titular or ''} — rechazo reversión",
                modulo="cheque_rechazo_banco",
                referencia_id=cheque_id,
                org_id=org_id, usuario_id=usuario_id,
                cuenta_debe_id=cliente_cuenta.id,
                cuenta_haber_id=banco.id,
                monto=monto,
            )

        # A2 y A3 solo si hay gastos
        if gastos > 0:
            # A2: Cliente D / Gastos de rechazos H — traslado al cliente
            if not _ya_existe(db, "cheque_rechazo_cliente", cheque_id, org_id):
                _crear_asiento_directo(
                    db=db, fecha=fecha,
                    descripcion=f"Cheque {titular or ''} — gastos rechazo a cliente",
                    modulo="cheque_rechazo_cliente",
                    referencia_id=cheque_id,
                    org_id=org_id, usuario_id=usuario_id,
                    cuenta_debe_id=cliente_cuenta.id,
                    cuenta_haber_id=gtos_rechazos.id,
                    monto=gastos,
                )
            # A3: Gastos de rechazos D / Banco H — débito bancario real
            if not _ya_existe(db, "cheque_rechazo_gasto", cheque_id, org_id):
                _crear_asiento_directo(
                    db=db, fecha=fecha,
                    descripcion=f"Cheque {titular or ''} — débito bancario rechazo",
                    modulo="cheque_rechazo_gasto",
                    referencia_id=cheque_id,
                    org_id=org_id, usuario_id=usuario_id,
                    cuenta_debe_id=gtos_rechazos.id,
                    cuenta_haber_id=banco.id,
                    monto=gastos,
                )

        db.commit()
    except Exception as ex:
        db.rollback()
        logger.warning("Error asiento cheque rechazo %s: %s", cheque_id, ex)


def _crear_asiento_directo(
    db: Session,
    fecha: date,
    descripcion: str,
    modulo: str,
    referencia_id: int,
    org_id: int,
    usuario_id: Optional[int],
    cuenta_debe_id: int,
    cuenta_haber_id: int,
    monto: Decimal,
) -> None:
    """Crea un asiento con cuentas explícitas (no por ReglaContable).
    Lo usa el módulo de egresos, que resuelve la cuenta del cliente dinámicamente."""
    a = Asiento(
        fecha=fecha,
        descripcion=descripcion,
        modulo=modulo,
        referencia_id=referencia_id,
        organizacion_id=org_id,
        usuario_id=usuario_id,
        numero_asiento=_next_numero_asiento(db, org_id),
    )
    db.add(a)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return
    db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=cuenta_debe_id,  debe=monto,          haber=Decimal("0")))
    db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=cuenta_haber_id, debe=Decimal("0"),   haber=monto))


def registrar_egreso(
    db: Session,
    egreso_id: int,
    org_id: int,
    usuario_id: Optional[int],
    tipo: str,
    forma_pago: str,
    monto: Decimal,
    fecha: date,
    beneficiario: str = "",
    concepto: str = "",
    cliente_id: Optional[int] = None,
    cliente_nombre: str = "",
) -> None:
    """Asiento del módulo unificado de Pagos (egresos). Una sola función para
    proveedor / gasto / pago_cliente, en banco o efectivo.

    Matriz de cuentas:
      tipo=pago_cliente → Debe: cuenta del cliente (2-1-2-X)
      tipo=proveedor/gasto → Debe: Gastos (3-2-0-0)
      forma_pago=banco    → Haber: Pagos a imputar (2-1-1-2, transitoria)
      forma_pago=efectivo → Haber: Efectivo (1-1-1-2)
    El pago por banco no acredita el banco: lo hace el débito del extracto
    (2-1-1-2 D / Banco H). Este asiento cancela esa transitoria; si el débito
    todavía no llegó, 2-1-1-2 queda acreedora = pagos cargados aún no vistos en
    el banco (modelo de cuentas transitorias, oct 2026; antes: Banco Macro H).
    """
    monto = round(_monto(monto), 2)
    try:
        if _ya_existe(db, "egreso", egreso_id, org_id):
            return
        if monto <= 0:
            return

        # Cuenta del Haber según forma de pago (siempre cuenta hoja)
        if forma_pago == "efectivo":
            cuenta_haber = _get_cuenta_por_codigo(db, "1-1-1-2", org_id)   # Efectivo
        else:
            cuenta_haber = cuenta_banco_transitoria(db, org_id, "egreso")  # Pagos a imputar
        if not cuenta_haber:
            logger.warning("registrar_egreso: falta cuenta Haber (forma=%s, org=%s)", forma_pago, org_id)
            return

        # Cuenta del Debe según tipo
        if tipo == "pago_cliente" and cliente_id:
            cuenta_debe = _get_o_crear_cuenta_cliente(db, cliente_id, org_id)
        else:
            cuenta_debe = _get_cuenta_por_codigo(db, "3-2-0-0", org_id)    # Gastos
        if not cuenta_debe:
            logger.warning("registrar_egreso: falta cuenta Debe (tipo=%s, org=%s)", tipo, org_id)
            return

        etiqueta = beneficiario or cliente_nombre or concepto or "Egreso"
        _crear_asiento_directo(
            db=db,
            fecha=fecha,
            descripcion=f"Pago: {etiqueta} — {forma_pago}",
            modulo="egreso",
            referencia_id=egreso_id,
            org_id=org_id,
            usuario_id=usuario_id,
            cuenta_debe_id=cuenta_debe.id,
            cuenta_haber_id=cuenta_haber.id,
            monto=monto,
        )
        db.commit()
    except Exception as ex:
        db.rollback()
        logger.warning("Error asiento egreso %s: %s", egreso_id, ex)


def registrar_ingreso_efectivo(
    db: Session,
    arqueo_id: int,
    org_id: int,
    usuario_id: Optional[int],
    monto: Decimal,
    fecha: date,
) -> None:
    """Reposición de efectivo (banco → caja): Efectivo (D) / Banco (H).
    Upsert: si ya existe para este arqueo actualiza el monto."""
    try:
        if monto <= 0:
            return
        regla = _get_regla(db, "carga_efectivo", org_id)
        if not regla:
            return
        existente = (
            db.query(Asiento)
            .filter(
                Asiento.modulo == "caja_efectivo",
                Asiento.referencia_id == arqueo_id,
                Asiento.organizacion_id == org_id,
            )
            .first()
        )
        if existente:
            for linea in existente.lineas:
                if linea.cuenta_id == regla.cuenta_debe_id:
                    linea.debe  = monto
                    linea.haber = Decimal("0")
                else:
                    linea.haber = monto
                    linea.debe  = Decimal("0")
            existente.fecha = fecha
            db.commit()
        else:
            _crear_asiento(
                db=db, regla=regla,
                fecha=fecha,
                descripcion="Reposición efectivo desde banco",
                modulo="caja_efectivo",
                referencia_id=arqueo_id,
                org_id=org_id,
                usuario_id=usuario_id,
                monto=round(monto, 2),
            )
            db.commit()
    except Exception as ex:
        db.rollback()
        logger.warning("Error asiento ingreso_efectivo %s: %s", arqueo_id, ex)


def registrar_planilla(
    db: Session,
    planilla_id: int,
    org_id: int,
    usuario_id: Optional[int],
    cliente_nombre: str,
    nombre_archivo: str,
    rows,
    fecha_acred: date,
    solo_pendientes: bool = False,
    comision_pct: Decimal = Decimal("0"),
) -> None:
    """Asiento al conciliar una planilla: Pasivo Corriente (D) / Cliente (H).
    Si comision_pct > 0 genera un segundo asiento de comisión.
    En re-conciliación (solo_pendientes), actualiza el monto si ya existe."""
    comision_pct = Decimal(str(comision_pct))
    try:
        regla = _get_regla(db, "carga_planilla", org_id)
        if not regla:
            return
        total = sum(_monto(r.monto) for r in rows if r.status == "ok")
        if total <= 0:
            return

        existente = (
            db.query(Asiento)
            .filter(
                Asiento.modulo == "planilla",
                Asiento.referencia_id == planilla_id,
                Asiento.organizacion_id == org_id,
            )
            .first()
        )

        if existente and solo_pendientes:
            for linea in existente.lineas:
                if linea.cuenta_id == regla.cuenta_debe_id:
                    linea.debe = total; linea.haber = Decimal("0")
                else:
                    linea.haber = total; linea.debe = Decimal("0")
            existente.fecha = fecha_acred
        elif not existente:
            _crear_asiento(
                db=db, regla=regla,
                fecha=fecha_acred,
                descripcion=f"{cliente_nombre} — {nombre_archivo}",
                modulo="planilla",
                referencia_id=planilla_id,
                org_id=org_id,
                usuario_id=usuario_id,
                monto=total,
            )

        # Comisión opcional
        if comision_pct > 0:
            comision_monto = round(total * comision_pct / 100, 2)
            if comision_monto > 0:
                regla_com = _get_regla(db, "carga_planilla_comision", org_id)
                if regla_com:
                    existente_com = (
                        db.query(Asiento)
                        .filter(
                            Asiento.modulo == "planilla_comision",
                            Asiento.referencia_id == planilla_id,
                            Asiento.organizacion_id == org_id,
                        )
                        .first()
                    )
                    if existente_com and solo_pendientes:
                        for linea in existente_com.lineas:
                            if linea.cuenta_id == regla_com.cuenta_debe_id:
                                linea.debe = comision_monto; linea.haber = Decimal("0")
                            else:
                                linea.haber = comision_monto; linea.debe = Decimal("0")
                        existente_com.fecha = fecha_acred
                    elif not existente_com:
                        _crear_asiento(
                            db=db, regla=regla_com,
                            fecha=fecha_acred,
                            descripcion=f"{cliente_nombre} — comisión {comision_pct}%",
                            modulo="planilla_comision",
                            referencia_id=planilla_id,
                            org_id=org_id,
                            usuario_id=usuario_id,
                            monto=comision_monto,
                        )

        db.commit()
    except Exception as ex:
        db.rollback()
        logger.warning("Error asiento planilla %s: %s", planilla_id, ex)


# ─── UM: importación y reclasificación ──────────────────────────────────────

def _get_cuenta_por_codigo(db: Session, codigo: str, org_id: int) -> Optional[PlanCuenta]:
    return (
        db.query(PlanCuenta)
        .filter(PlanCuenta.codigo == codigo, PlanCuenta.organizacion_id == org_id, PlanCuenta.activo == True)
        .first()
    )


# ─── Cuentas del banco: modelo de cuentas transitorias (estilo Odoo, oct 2026) ──
#
# La cuenta del banco la mueven SOLO los datos del banco (extracto principal y
# Últimos Movimientos). Todo lo demás que cargamos en Cuadra y que también va a
# aparecer en el extracto (pagos por banco, cheques acreditados, tarjetas, etc.)
# pega contra una cuenta transitoria — "partidas pendientes de imputación":
#   - 2-1-1-1 "No identificado"  = cobros a imputar (plata que ENTRA al banco).
#     El crédito del extracto la acredita; la conciliación / acreditación la debita.
#   - 2-1-1-2 "Pagos a imputar"  = pagos a imputar (plata que SALE del banco).
#     El débito del extracto la debita; el pago cargado en Cuadra la acredita.
# Si todo está explicado, ambas transitorias quedan en cero. Ver
# ACCOUNTING_ENGINE.md §2bis y docs/adr/DECISIONS.md ("Modelo de cuentas
# transitorias estilo Odoo"). Elegir la cuenta SOLO con estos helpers: no
# desparramar códigos por los registrar_*.

CUENTA_BANCO_EXTRACTO = "1-1-1-3-1"   # Banco Macro (hoja)
CUENTA_COBROS_A_IMPUTAR = "2-1-1-1"   # No identificado
CUENTA_PAGOS_A_IMPUTAR = "2-1-1-2"    # Pagos a imputar
_CUENTA_PASIVO_A_CONFIRMAR = "2-1-1-0"  # rubro padre de las dos transitorias


def cuenta_banco_extracto(db: Session, org_id: int) -> Optional[PlanCuenta]:
    """Cuenta contable del banco que mueven los movimientos del extracto / UM.
    TODO multi-banco: hoy todo extracto pega contra Banco Macro (1-1-1-3-1),
    aunque sea de otro banco. Mapear ExtractoBancario.banco → cuenta hoja queda
    para otro cambio (necesita una cuenta por banco en el plan)."""
    return _get_cuenta_por_codigo(db, CUENTA_BANCO_EXTRACTO, org_id)


def cuenta_banco_transitoria(db: Session, org_id: int, sentido: str) -> Optional[PlanCuenta]:
    """Cuenta transitoria que reemplaza al banco en los asientos de módulos.
    sentido="ingreso" (la plata entra al banco) → 2-1-1-1 No identificado.
    sentido="egreso"  (la plata sale del banco) → 2-1-1-2 Pagos a imputar.
    Si la org todavía no tiene 2-1-1-2 (el seed la agrega en el próximo arranque)
    la crea acá bajo 2-1-1-0 — alta aditiva, nunca modifica cuentas existentes."""
    if sentido not in ("ingreso", "egreso"):
        raise ValueError(f"sentido inválido: {sentido!r} (usar 'ingreso' o 'egreso')")
    if sentido == "ingreso":
        return _get_cuenta_por_codigo(db, CUENTA_COBROS_A_IMPUTAR, org_id)
    cuenta = _get_cuenta_por_codigo(db, CUENTA_PAGOS_A_IMPUTAR, org_id)
    if cuenta:
        return cuenta
    padre = _get_cuenta_por_codigo(db, _CUENTA_PASIVO_A_CONFIRMAR, org_id)
    if not padre:
        return None
    # Puede existir inactiva: no se duplica el código.
    if db.query(PlanCuenta).filter(
        PlanCuenta.codigo == CUENTA_PAGOS_A_IMPUTAR, PlanCuenta.organizacion_id == org_id,
    ).first():
        return None
    cuenta = PlanCuenta(
        codigo=CUENTA_PAGOS_A_IMPUTAR, nombre="Pagos a imputar", tipo="pasivo",
        parent_id=padre.id, nivel=(padre.nivel or 3) + 1,
        activo=True, organizacion_id=org_id,
    )
    db.add(cuenta)
    db.flush()
    logger.info("Cuenta 2-1-1-2 Pagos a imputar creada para org %s", org_id)
    return cuenta


def _get_o_crear_cuenta_cliente(db: Session, cliente_id: int, org_id: int, reusar_huecos: bool = False) -> Optional[PlanCuenta]:
    """Resuelve la cuenta contable del Cliente EXISTENTE (vínculo 1:1).
    1. Si el cliente ya tiene cuenta_contable_id → la reutiliza.
    2. Si existe una cuenta bajo 2-1-2-0 con el mismo nombre → la adopta y la vincula.
    3. Si no existe ninguna → crea la cuenta y la vincula al cliente.
       - reusar_huecos=False (default): usa el próximo código (max+1).
       - reusar_huecos=True: usa el primer código libre en la secuencia (rellena
         huecos dejados por cuentas borradas, ej. una 2-1-2-8 eliminada).
    Nunca crea entidades Cliente; solo la cuenta contable asociada al cliente que ya está en el sistema."""
    from sqlalchemy import func as _func
    from app.models.cliente import Cliente

    cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()
    if not cliente:
        return None

    # 1. Cuenta ya vinculada
    if cliente.cuenta_contable_id:
        cuenta = db.query(PlanCuenta).filter(PlanCuenta.id == cliente.cuenta_contable_id).first()
        if cuenta:
            return cuenta

    padre = _get_cuenta_por_codigo(db, "2-1-2-0", org_id)
    if not padre:
        return None

    nombre_norm = (cliente.nombre or "").strip().title()

    # 2. Adoptar cuenta existente por nombre (ej. cuentas de cliente ya sembradas)
    cuenta = (
        db.query(PlanCuenta)
        .filter(
            PlanCuenta.parent_id == padre.id,
            PlanCuenta.organizacion_id == org_id,
            _func.lower(PlanCuenta.nombre) == nombre_norm.lower(),
        )
        .first()
    )
    if cuenta:
        cliente.cuenta_contable_id = cuenta.id
        db.flush()
        return cuenta

    # 3. Crear cuenta nueva y vincularla al cliente
    hijos = db.query(PlanCuenta).filter(PlanCuenta.parent_id == padre.id, PlanCuenta.organizacion_id == org_id).all()
    usados = set()
    for hijo in hijos:
        try:
            usados.add(int(hijo.codigo.rsplit("-", 1)[-1]))
        except (ValueError, IndexError):
            pass
    if reusar_huecos:
        # primer entero >=1 que no esté usado (rellena el hueco más bajo)
        n = 1
        while n in usados:
            n += 1
        nuevo_n = n
    else:
        nuevo_n = (max(usados) if usados else 0) + 1
    nuevo_codigo = f"2-1-2-{nuevo_n}"
    nueva = PlanCuenta(
        codigo=nuevo_codigo, nombre=nombre_norm, tipo="pasivo",
        parent_id=padre.id, nivel=(padre.nivel or 3) + 1,
        activo=True, organizacion_id=org_id,
    )
    db.add(nueva)
    db.flush()
    cliente.cuenta_contable_id = nueva.id
    db.flush()
    logger.info("Cuenta cliente creada: %s %s (cliente_id=%s, org %s)", nuevo_codigo, nombre_norm, cliente_id, org_id)
    return nueva


def registrar_um_import(
    db: Session,
    extracto_id: int,
    org_id: int,
    usuario_id: Optional[int],
    movimientos_nuevos,
    modo: str = "agrupado",
) -> None:
    """Asiento al importar UM, mismas cuentas que el extracto principal:
      ingreso: Banco Macro (D) / No identificado 2-1-1-1 (H)
      egreso:  Pagos a imputar 2-1-1-2 (D) / Banco Macro (H)
    (hasta oct 2026 el egreso iba contra 2-1-1-1; los asientos viejos quedan como están).
    modo='agrupado' → un asiento por lote (suma total).
    modo='individual' → un asiento por movimiento."""
    try:
        if not movimientos_nuevos:
            return
        banco_macro = cuenta_banco_extracto(db, org_id)
        no_id = cuenta_banco_transitoria(db, org_id, "ingreso")
        pagos = cuenta_banco_transitoria(db, org_id, "egreso")
        if not banco_macro or not no_id or not pagos:
            logger.warning("Cuentas UM no encontradas org %s (1-1-1-3-1 / 2-1-1-1 / 2-1-1-2)", org_id)
            return
        if modo == "individual":
            for mov in movimientos_nuevos:
                if _ya_existe(db, "um_mov", mov.id, org_id):
                    continue
                monto = _monto(mov.monto)
                monto_abs = abs(monto)
                if monto_abs <= 0:
                    continue
                fecha_mov = mov.fecha if isinstance(mov.fecha, date) else hoy_art()
                a = Asiento(
                    fecha=fecha_mov,
                    descripcion=f"UM: {mov.titular or 'Sin titular'}",
                    modulo="um_mov",
                    referencia_id=mov.id,
                    organizacion_id=org_id,
                    usuario_id=usuario_id,
                )
                db.add(a)
                db.flush()
                if monto >= 0:
                    # Ingreso: Banco Debe / No Identificado Haber
                    db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=banco_macro.id, debe=monto_abs, haber=Decimal("0")))
                    db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=no_id.id, debe=Decimal("0"), haber=monto_abs))
                else:
                    # Egreso: Pagos a imputar Debe / Banco Haber
                    db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=pagos.id, debe=monto_abs, haber=Decimal("0")))
                    db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=banco_macro.id, debe=Decimal("0"), haber=monto_abs))
        else:
            construir_asiento_um_lote(db, extracto_id, org_id, usuario_id, movimientos_nuevos)
        db.commit()
    except Exception as ex:
        db.rollback()
        logger.warning("Error asiento UM import %s: %s", extracto_id, ex)


def construir_asiento_um_lote(
    db: Session,
    extracto_id: int,
    org_id: int,
    usuario_id: Optional[int],
    movimientos,
) -> Optional[Asiento]:
    """Arma (sin commit) el asiento agrupado "um_lote" de un lote de UM:
      Σ ingresos: Banco Macro D / No identificado 2-1-1-1 H
      Σ egresos:  Pagos a imputar 2-1-1-2 D / Banco Macro H
    referencia_id = id del primer movimiento del lote. Idempotente (no crea si
    ya existe). Lo usan el import de UM y "Empezar limpio" (reset-y-rebuild),
    para que ambos armen exactamente el mismo asiento. Lanza ante un error."""
    if not movimientos:
        return None
    primer_mov = movimientos[0]
    if _ya_existe(db, "um_lote", primer_mov.id, org_id):
        return None
    banco_macro = cuenta_banco_extracto(db, org_id)
    no_id = cuenta_banco_transitoria(db, org_id, "ingreso")
    pagos = cuenta_banco_transitoria(db, org_id, "egreso")
    if not banco_macro or not no_id or not pagos:
        logger.warning("Cuentas UM no encontradas org %s (1-1-1-3-1 / 2-1-1-1 / 2-1-1-2)", org_id)
        return None
    total_pos = sum((max(_monto(m.monto), Decimal("0")) for m in movimientos), Decimal("0"))
    total_neg = sum((abs(min(_monto(m.monto), Decimal("0"))) for m in movimientos), Decimal("0"))
    if total_pos <= 0 and total_neg <= 0:
        return None
    fecha_ref = primer_mov.fecha if isinstance(primer_mov.fecha, date) else hoy_art()
    lote = primer_mov.um_lote or 1
    a = Asiento(
        fecha=fecha_ref,
        descripcion=f"UM lote {lote} — {len(movimientos)} movimientos (extracto #{extracto_id})",
        modulo="um_lote",
        referencia_id=primer_mov.id,
        organizacion_id=org_id,
        usuario_id=usuario_id,
        numero_asiento=_next_numero_asiento(db, org_id),
    )
    db.add(a)
    db.flush()
    if total_pos > 0:
        # Ingresos: Banco Debe / No Identificado Haber
        db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=banco_macro.id, debe=total_pos, haber=Decimal("0")))
        db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=no_id.id, debe=Decimal("0"), haber=total_pos))
    if total_neg > 0:
        # Egresos: Pagos a imputar Debe / Banco Haber
        db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=pagos.id, debe=total_neg, haber=Decimal("0")))
        db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=banco_macro.id, debe=Decimal("0"), haber=total_neg))
    db.flush()
    return a


def registrar_reclasificacion_um(
    db: Session,
    planilla_row_id: int,
    org_id: int,
    usuario_id: Optional[int],
    cliente_id: int,
    cliente_nombre: str,
    monto,
    fecha: date,
) -> None:
    """Asiento de reclasificación al conciliar un movimiento UM: No identificado (D) / Cliente X (H).
    La cuenta del cliente existente se resuelve/crea/vincula vía _get_o_crear_cuenta_cliente."""
    try:
        if _ya_existe(db, "um_reclass", planilla_row_id, org_id):
            return
        no_id = _get_cuenta_por_codigo(db, "2-1-1-1", org_id)
        cuenta_cliente = _get_o_crear_cuenta_cliente(db, cliente_id, org_id) if cliente_id else None
        if not no_id or not cuenta_cliente:
            logger.warning("Cuentas reclasificación no encontradas org %s (cliente_id=%s)", org_id, cliente_id)
            return
        monto_d = abs(_monto(monto))
        if monto_d <= 0:
            return
        fecha_asiento = fecha if isinstance(fecha, date) else hoy_art()
        a = Asiento(
            fecha=fecha_asiento,
            descripcion=f"Reclasif. UM → {cliente_nombre}",
            modulo="um_reclass",
            referencia_id=planilla_row_id,
            organizacion_id=org_id,
            usuario_id=usuario_id,
        )
        db.add(a)
        db.flush()
        db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=no_id.id, debe=monto_d, haber=Decimal("0")))
        db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=cuenta_cliente.id, debe=Decimal("0"), haber=monto_d))
        db.commit()
    except Exception as ex:
        db.rollback()
        logger.warning("Error asiento reclasif. row %s: %s", planilla_row_id, ex)


# Módulos de la reclasificación por planilla, según el origen del movimiento.
MODULO_RECLASS = {"um": "um_reclass_planilla", "extracto": "reclass_planilla_principal"}
# Bucket del extracto principal antes del modelo de cuentas transitorias
# (debitaba Pasivo Corriente 2-1-0-0). Solo lo crean los datos viejos.
MODULO_RECLASS_LEGACY_EXTRACTO = "reclass_planilla_extracto"
CUENTA_PASIVO_CORRIENTE_LEGACY = "2-1-0-0"


def esta_reversado(db: Session, asiento: Asiento) -> bool:
    """True si el asiento ya tiene su `{modulo}_reverso` (ver reversar_asientos)."""
    return (
        db.query(Asiento.id)
        .filter(
            Asiento.modulo == f"{asiento.modulo}_reverso",
            Asiento.referencia_id == asiento.id,
            Asiento.organizacion_id == asiento.organizacion_id,
        )
        .first()
    ) is not None


def asiento_reclass_legacy_vigente(db: Session, planilla_id: int, org_id: int) -> Optional[Asiento]:
    """Asiento viejo reclass_planilla_extracto de la planilla, si existe y no fue reversado."""
    a = (
        db.query(Asiento)
        .filter(
            Asiento.modulo == MODULO_RECLASS_LEGACY_EXTRACTO,
            Asiento.referencia_id == planilla_id,
            Asiento.organizacion_id == org_id,
        )
        .first()
    )
    if a is None or esta_reversado(db, a):
        return None
    return a


def registrar_reclasificacion_planilla(
    db: Session,
    planilla_id: int,
    org_id: int,
    usuario_id: Optional[int],
    cliente_id: int,
    cliente_nombre: str,
    total_monto: Decimal,
    fecha: date,
    nombre_archivo: str = "",
    origen: str = "um",
    comision_pct: Decimal = Decimal("0"),
) -> None:
    """Asiento(s) agrupado(s) por planilla al conciliar pagos identificados a un
    cliente. Un asiento principal — No identificado 2-1-1-1 (D) / Cliente (H) —
    por el NETO (total menos comisión). Si comision_pct > 0, un segundo asiento
    separado — No identificado (D) / Comisiones ganadas (H) — por la comisión.
    Así el cliente queda acreditado por el neto y la comisión se reconoce como
    ingreso aparte (tratamiento acordado con el contador, ago 2026).

    Modelo de cuentas transitorias (oct 2026): el crédito del banco, venga del
    extracto principal o de Últimos Movimientos, queda en 2-1-1-1 (Banco D /
    No identificado H), así que la reclasificación siempre debita 2-1-1-1.
    `origen` ("um" | "extracto") ya no cambia la cuenta, solo el módulo, para
    trazabilidad y para que los dos buckets de una misma planilla no se pisen:
      - "um"       → um_reclass_planilla (+ _comision)
      - "extracto" → reclass_planilla_principal (+ _comision)
    Hasta oct 2026 el bucket del extracto principal usaba el módulo
    reclass_planilla_extracto contra Pasivo Corriente 2-1-0-0. Si la planilla
    todavía tiene ese asiento viejo SIN reversar, una re-conciliación lo sigue
    actualizando con su cuenta vieja (no se corrige en silencio ni se duplica la
    acreditación al cliente); POST /contabilidad/corregir-asientos-banco lo
    reversa y lo rehace en reclass_planilla_principal.

    La cuenta del cliente se resuelve/crea/vincula vía _get_o_crear_cuenta_cliente
    (nunca la cuenta madre genérica "Cliente" 2-1-2-0 — eso fue el bug del
    backfill viejo, ver CHANGELOG ago 2026).

    Upsert por (modulo, planilla_id, org_id): si ya existe un asiento previo,
    actualiza el monto — para re-conciliaciones que acreditan filas adicionales
    o cambian el % de comisión en una segunda pasada. Si la comisión pasó a ser
    0 (se sacó), borra el asiento de comisión existente en vez de dejarlo con
    un monto que ya no corresponde."""
    try:
        total_monto = abs(round(_monto(total_monto), 2))
        if total_monto <= 0:
            return
        if origen not in MODULO_RECLASS:
            raise ValueError(f"origen inválido: {origen!r} (usar 'um' o 'extracto')")
        modulo = MODULO_RECLASS[origen]
        cuenta_origen = cuenta_banco_transitoria(db, org_id, "ingreso")
        if origen == "extracto":
            legacy = asiento_reclass_legacy_vigente(db, planilla_id, org_id)
            if legacy is not None:
                modulo = MODULO_RECLASS_LEGACY_EXTRACTO
                linea_origen = next((ln for ln in legacy.lineas if (ln.debe or 0) > 0), None)
                if linea_origen is not None:
                    cuenta_origen = db.query(PlanCuenta).filter(PlanCuenta.id == linea_origen.cuenta_id).first()
        origen = cuenta_origen
        cuenta_cliente = _get_o_crear_cuenta_cliente(db, cliente_id, org_id) if cliente_id else None
        if not origen or not cuenta_cliente:
            logger.warning(
                "Cuentas reclasificación planilla no encontradas org %s (cliente_id=%s, modulo=%s)",
                org_id, cliente_id, modulo,
            )
            return

        comision_pct = Decimal(str(comision_pct or 0))
        comision_monto = round(total_monto * comision_pct / 100, 2) if comision_pct > 0 else Decimal("0")
        neto = total_monto - comision_monto

        fecha_asiento = fecha if isinstance(fecha, date) else hoy_art()
        desc = f"TT {cliente_nombre}"
        if nombre_archivo:
            desc += f" — {nombre_archivo}"

        modulo_com = modulo + "_comision"

        existente = (
            db.query(Asiento)
            .filter(
                Asiento.modulo == modulo,
                Asiento.referencia_id == planilla_id,
                Asiento.organizacion_id == org_id,
            )
            .first()
        )
        if existente:
            for linea in existente.lineas:
                if linea.cuenta_id == origen.id:
                    linea.debe = neto
                    linea.haber = Decimal("0")
                else:
                    linea.haber = neto
                    linea.debe = Decimal("0")
            existente.fecha = fecha_asiento
        else:
            a = Asiento(
                fecha=fecha_asiento,
                descripcion=desc,
                modulo=modulo,
                referencia_id=planilla_id,
                organizacion_id=org_id,
                usuario_id=usuario_id,
                numero_asiento=_next_numero_asiento(db, org_id),
            )
            db.add(a)
            db.flush()
            db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=origen.id,          debe=neto,         haber=Decimal("0")))
            db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=cuenta_cliente.id,  debe=Decimal("0"), haber=neto))

        if comision_monto > 0:
            comisiones = _get_cuenta_por_codigo(db, "3-1-1-0", org_id)
            if not comisiones:
                logger.warning("Cuenta Comisiones ganadas (3-1-1-0) no encontrada org %s", org_id)
            else:
                existente_com = (
                    db.query(Asiento)
                    .filter(
                        Asiento.modulo == modulo_com,
                        Asiento.referencia_id == planilla_id,
                        Asiento.organizacion_id == org_id,
                    )
                    .first()
                )
                if existente_com:
                    for linea in existente_com.lineas:
                        if linea.cuenta_id == origen.id:
                            linea.debe = comision_monto
                            linea.haber = Decimal("0")
                        else:
                            linea.haber = comision_monto
                            linea.debe = Decimal("0")
                    existente_com.fecha = fecha_asiento
                else:
                    a2 = Asiento(
                        fecha=fecha_asiento,
                        descripcion=f"Comisión {comision_pct}% — {cliente_nombre}",
                        modulo=modulo_com,
                        referencia_id=planilla_id,
                        organizacion_id=org_id,
                        usuario_id=usuario_id,
                        numero_asiento=_next_numero_asiento(db, org_id),
                    )
                    db.add(a2)
                    db.flush()
                    db.add(AsientoDetalle(asiento_id=a2.id, cuenta_id=origen.id,     debe=comision_monto, haber=Decimal("0")))
                    db.add(AsientoDetalle(asiento_id=a2.id, cuenta_id=comisiones.id, debe=Decimal("0"),   haber=comision_monto))
        else:
            ids_com = [
                r[0] for r in db.query(Asiento.id).filter(
                    Asiento.modulo == modulo_com,
                    Asiento.referencia_id == planilla_id,
                    Asiento.organizacion_id == org_id,
                ).all()
            ]
            if ids_com:
                db.query(AsientoDetalle).filter(AsientoDetalle.asiento_id.in_(ids_com)).delete(synchronize_session=False)
                db.query(Asiento).filter(Asiento.id.in_(ids_com)).delete(synchronize_session=False)

        db.commit()
    except Exception as ex:
        db.rollback()
        logger.warning("Error asiento reclasif. planilla %s: %s", planilla_id, ex)


def registrar_liquidacion_aprobacion(
    db: Session,
    liquidacion_id: int,
    detalle_id: int,
    org_id: int,
    usuario_id: Optional[int],
    cliente_id: int,
    cliente_nombre: str,
    monto_conciliado: Decimal,
    monto_neto: Decimal,
    monto_comision: Decimal,
    fecha: date,
) -> None:
    """Asiento al aprobar una liquidación, por cada detalle (cliente):
    Cliente (2-1-2-X) D monto_conciliado / Pagos a imputar (2-1-1-2) H monto_neto
    + Comisiones ganadas (3-1-1-0) H monto_comision (si > 0).
    Cancela la deuda con el cliente y reconoce la comisión como ingreso. El
    pago al cliente sale por banco: el débito del extracto mueve el banco
    (2-1-1-2 D / Banco H); acá se acredita la transitoria (antes: Banco Macro H)."""
    try:
        if _ya_existe(db, "liquidacion_aprobacion", detalle_id, org_id):
            return
        monto_conciliado = round(_monto(monto_conciliado), 2)
        monto_neto       = round(_monto(monto_neto), 2)
        monto_comision   = round(_monto(monto_comision), 2)
        if monto_conciliado <= 0:
            return
        cuenta_cliente = _get_o_crear_cuenta_cliente(db, cliente_id, org_id) if cliente_id else None
        banco          = cuenta_banco_transitoria(db, org_id, "egreso")
        comisiones     = _get_cuenta_por_codigo(db, "3-1-1-0", org_id)
        # Exigir la cuenta de comisiones cuando hay comisión: sin ella el asiento
        # quedaría desbalanceado (Cliente D conciliado / Pagos a imputar H neto, con neto < conciliado).
        if not cuenta_cliente or not banco or (monto_comision > 0 and not comisiones):
            logger.warning("Cuentas liquidación incompletas org %s (cliente_id=%s) — no se postea", org_id, cliente_id)
            return
        lineas = [
            (cuenta_cliente.id, monto_conciliado, Decimal("0")),
            (banco.id,          Decimal("0"),     monto_neto),
        ]
        if monto_comision > 0:
            lineas.append((comisiones.id, Decimal("0"), monto_comision))
        _crear_asiento_multilinea(
            db=db,
            fecha=fecha if isinstance(fecha, date) else hoy_art(),
            descripcion=f"Liquidación #{liquidacion_id} — {cliente_nombre}",
            modulo="liquidacion_aprobacion",
            referencia_id=detalle_id,
            org_id=org_id,
            usuario_id=usuario_id,
            lineas=lineas,
        )
        db.commit()
    except Exception as ex:
        db.rollback()
        logger.warning("Error asiento liquidacion aprobacion detalle %s: %s", detalle_id, ex)


def registrar_liquidacion_sueldos(
    db: Session,
    liquidacion_id: int,
    org_id: int,
    usuario_id: Optional[int],
    periodo: str,
    total_bruto: Decimal,
    total_aportes: Decimal,
    total_contribuciones: Decimal,
    total_neto: Decimal,
    total_retencion_ganancias: Decimal = Decimal("0"),
) -> None:
    """Asiento agrupado al aprobar una liquidación de sueldos del período:
        Sueldos y cargas sociales (3-2-4-0, gasto) D       por bruto + contribuciones
        Sueldos a pagar (2-1-4-0) H                        por el neto a pagar al empleado
        Cargas sociales a pagar (2-1-5-0) H                por aportes + contribuciones
        Retención de Ganancias a depositar (2-1-6-0) H     por la retención de 4ta (si > 0)
    La retención de Ganancias que se le descuenta al empleado es un pasivo del
    empleador (la retiene para depositarla a ARCA): por eso va al Haber. Sin esta
    contrapartida el asiento descuadraba al activar Ganancias (porque el neto ya
    viene con la retención restada) y la red de partida doble no lo posteaba.
    Partida doble: D = bruto+contrib ; H = neto + aportes + contrib + ganancias
                   = (bruto−aportes−ganancias) + aportes + contrib + ganancias
                   = bruto + contrib = D ✓.
    Idempotente por (modulo, referencia_id=liquidacion_id, org)."""
    try:
        if _ya_existe(db, "sueldos_liquidacion", liquidacion_id, org_id):
            return
        bruto   = round(_monto(total_bruto), 2)
        aportes = round(_monto(total_aportes), 2)
        contrib = round(_monto(total_contribuciones), 2)
        neto    = round(_monto(total_neto), 2)
        ret     = round(_monto(total_retencion_ganancias), 2)
        if bruto <= 0:
            return
        gasto       = _get_cuenta_por_codigo(db, "3-2-4-0", org_id)
        sueldos_pag = _get_cuenta_por_codigo(db, "2-1-4-0", org_id)
        cargas_pag  = _get_cuenta_por_codigo(db, "2-1-5-0", org_id)
        if not gasto or not sueldos_pag or not cargas_pag:
            logger.warning(
                "Cuentas sueldos no encontradas org %s (3-2-4-0/2-1-4-0/2-1-5-0)", org_id
            )
            return
        debe_total = (bruto + contrib)
        cargas = (aportes + contrib)
        lineas = [
            (gasto.id,       debe_total,   Decimal("0")),
            (sueldos_pag.id, Decimal("0"), neto),
            (cargas_pag.id,  Decimal("0"), cargas),
        ]
        if ret > 0:
            ret_pag = _get_cuenta_por_codigo(db, "2-1-6-0", org_id)
            if ret_pag:
                lineas.append((ret_pag.id, Decimal("0"), ret))
            else:
                # Defensivo: PLAN_PATCH crea 2-1-6-0 en cada arranque, así que en
                # producción siempre existe. Si faltara, no agregamos la línea para
                # no romper el alta — pero el asiento descuadraría, así que avisamos.
                logger.warning(
                    "Cuenta 2-1-6-0 (Retención de Ganancias) no encontrada org %s — "
                    "asiento de sueldos sin contrapartida de retención", org_id
                )
        _crear_asiento_multilinea(
            db=db,
            fecha=hoy_art(),
            descripcion=f"Liquidación de sueldos {periodo}",
            modulo="sueldos_liquidacion",
            referencia_id=liquidacion_id,
            org_id=org_id,
            usuario_id=usuario_id,
            lineas=lineas,
        )
        db.commit()
    except Exception as ex:
        db.rollback()
        logger.warning("Error asiento liquidacion sueldos %s: %s", liquidacion_id, ex)


def registrar_cc_inicial(
    db: Session,
    planilla_row_id: int,
    org_id: int,
    usuario_id: Optional[int],
    cliente_id: int,
    cliente_nombre: str,
    monto,
    fecha: date,
    nombre_archivo: str = "",
) -> bool:
    """Backfill histórico de cuenta corriente: acreditación ya conciliada →
    No identificado 2-1-1-1 (D) / Cliente X (H). Asiento neto y balanceado para
    reconstruir las cuentas corrientes desde datos cargados antes de que existiera
    el motor. El Debe era Banco Macro: con el modelo de cuentas transitorias
    (oct 2026) el banco lo mueve solo el extracto (Banco D / 2-1-1-1 H) y esto
    es una reclasificación más, como la de una planilla conciliada.
    Idempotente: no crea si la fila ya tiene asiento del flujo normal (um_reclass)
    ni un cc_inicial previo. Devuelve True si creó el asiento."""
    try:
        if _ya_existe(db, "um_reclass", planilla_row_id, org_id):
            return False
        if _ya_existe(db, "cc_inicial", planilla_row_id, org_id):
            return False
        banco = cuenta_banco_transitoria(db, org_id, "ingreso")
        cuenta_cliente = _get_o_crear_cuenta_cliente(db, cliente_id, org_id) if cliente_id else None
        if not banco or not cuenta_cliente:
            return False
        monto_d = abs(_monto(monto))
        if monto_d <= 0:
            return False
        fecha_asiento = fecha if isinstance(fecha, date) else hoy_art()
        desc = f"Acreditación histórica — {cliente_nombre}"
        if nombre_archivo:
            desc += f" ({nombre_archivo})"
        a = Asiento(
            fecha=fecha_asiento,
            descripcion=desc,
            modulo="cc_inicial",
            referencia_id=planilla_row_id,
            organizacion_id=org_id,
            usuario_id=usuario_id,
        )
        db.add(a)
        db.flush()
        db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=banco.id, debe=monto_d, haber=Decimal("0")))
        db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=cuenta_cliente.id, debe=Decimal("0"), haber=monto_d))
        db.commit()
        return True
    except Exception as ex:
        db.rollback()
        logger.warning("Error cc_inicial row %s: %s", planilla_row_id, ex)
        return False


# ─── Reversión contable ──────────────────────────────────────────────────────

def reversar_asientos(
    db: Session,
    modulo: str,
    referencia_id: int,
    org_id: int,
    usuario_id: Optional[int],
    motivo: str = "Reverso por baja del registro origen",
) -> int:
    """Crea asientos de reverso (debe↔haber invertidos) para los asientos del
    modulo+referencia dados. NO borra los originales — la trazabilidad queda
    completa en el libro: el asiento original más su reverso.

    Idempotente: si ya existe un reverso para el mismo origen, no crea otro.
    Devuelve la cantidad de reversos creados.
    """
    try:
        originales = (
            db.query(Asiento)
            .filter(
                Asiento.modulo == modulo,
                Asiento.referencia_id == referencia_id,
                Asiento.organizacion_id == org_id,
            )
            .all()
        )
        if not originales:
            return 0

        modulo_reverso = f"{modulo}_reverso"
        creados = 0
        for orig in originales:
            # Idempotencia: no duplicar si ya hay un reverso para este asiento
            ya_reversado = (
                db.query(Asiento)
                .filter(
                    Asiento.modulo == modulo_reverso,
                    Asiento.referencia_id == orig.id,
                    Asiento.organizacion_id == org_id,
                )
                .first()
            )
            if ya_reversado:
                continue

            reverso = Asiento(
                fecha=hoy_art(),
                descripcion=f"REVERSO #{orig.id}: {orig.descripcion or ''} — {motivo}",
                modulo=modulo_reverso,
                referencia_id=orig.id,
                organizacion_id=org_id,
                usuario_id=usuario_id,
                numero_asiento=_next_numero_asiento(db, org_id),
            )
            db.add(reverso)
            db.flush()

            # Invertir cada línea del original (debe ↔ haber)
            for linea in orig.lineas:
                db.add(AsientoDetalle(
                    asiento_id=reverso.id,
                    cuenta_id=linea.cuenta_id,
                    debe=linea.haber,
                    haber=linea.debe,
                ))
            creados += 1

        if creados:
            db.commit()
        return creados
    except Exception as ex:
        db.rollback()
        logger.warning("Error reversando %s/%s: %s", modulo, referencia_id, ex)
        return 0


def registrar_ajuste_manual(
    db: Session,
    org_id: int,
    usuario_id: int,
    cuenta_debe_id: int,
    cuenta_haber_id: int,
    monto: Decimal,
    fecha: date,
    descripcion: str,
) -> int:
    """Crea un asiento de ajuste manual. Retorna el ID del asiento creado.
    NO es idempotente — cada llamada crea un asiento nuevo.
    """
    a = Asiento(
        fecha=fecha,
        descripcion=descripcion,
        modulo="ajuste_manual",
        referencia_id=None,
        organizacion_id=org_id,
        usuario_id=usuario_id,
        numero_asiento=_next_numero_asiento(db, org_id),
    )
    db.add(a)
    db.flush()
    db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=cuenta_debe_id, debe=monto, haber=Decimal("0")))
    db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=cuenta_haber_id, debe=Decimal("0"), haber=monto))
    return a.id


# ─── Liquidaciones de tarjetas de crédito (Visa / Mastercard / Amex) ──────────

# Cuenta de aranceles por marca de tarjeta.
_ARANCEL_CUENTA_POR_MARCA = {
    "visa":       "3-2-3-1",
    "mastercard": "3-2-3-2",
    "amex":       "3-2-3-3",
}


def registrar_liquidacion_tarjeta(
    db: Session,
    liquidacion_id: int,
    org_id: int,
    usuario_id: Optional[int],
    marca: str,
    monto_bruto: Decimal,
    aranceles: Decimal,
    iva_df: Decimal,
    percepciones_iibb: Decimal,
    retenciones: Decimal,
    neto: Decimal,
    fecha: date,
    descripcion: str = "",
) -> Optional[int]:
    """Asiento mensual agrupado de liquidación de tarjeta (módulo `tarjeta_liq`).

        No identificado (2-1-1-1)             D: neto   (antes: Banco Macro)
        Aranceles tarjeta (3-2-3-X por marca) D: aranceles
        IVA Crédito Fiscal (1-1-2-4)          D: iva_df
        Percepciones IIBB (1-1-2-5)           D: percepciones_iibb
        Retenciones de impuestos (1-1-2-6)    D: retenciones
            Ingresos por tarjetas (3-1-4-0)   H: monto_bruto

    El neto lo acredita el banco: ese crédito del extracto ya hace Banco D /
    2-1-1-1 H, así que acá se debita la transitoria de cobros (modelo de cuentas
    transitorias, oct 2026).

    Devuelve el ID del asiento creado (o None si no se pudo crear). Idempotente:
    no crea un segundo asiento para la misma (tarjeta_liq, liquidacion_id, org)."""
    try:
        if _ya_existe(db, "tarjeta_liq", liquidacion_id, org_id):
            existente = (
                db.query(Asiento)
                .filter(
                    Asiento.modulo == "tarjeta_liq",
                    Asiento.referencia_id == liquidacion_id,
                    Asiento.organizacion_id == org_id,
                )
                .first()
            )
            return existente.id if existente else None

        monto_bruto       = round(_monto(monto_bruto), 2)
        aranceles         = round(_monto(aranceles), 2)
        iva_df            = round(_monto(iva_df), 2)
        percepciones_iibb = round(_monto(percepciones_iibb), 2)
        retenciones       = round(_monto(retenciones), 2)
        neto              = round(_monto(neto), 2)

        banco         = cuenta_banco_transitoria(db, org_id, "ingreso")
        ingresos      = _get_cuenta_por_codigo(db, "3-1-4-0", org_id)
        cta_iva       = _get_cuenta_por_codigo(db, "1-1-2-4", org_id)
        cta_iibb      = _get_cuenta_por_codigo(db, "1-1-2-5", org_id)
        cta_ret       = _get_cuenta_por_codigo(db, "1-1-2-6", org_id)
        cod_arancel   = _ARANCEL_CUENTA_POR_MARCA.get(str(marca).lower(), "3-2-3-0")
        cta_arancel   = _get_cuenta_por_codigo(db, cod_arancel, org_id)

        if not (banco and ingresos and cta_iva and cta_iibb and cta_ret and cta_arancel):
            logger.warning(
                "Cuentas tarjeta incompletas org %s liq %s — no se postea", org_id, liquidacion_id
            )
            return None

        lineas = [(banco.id, neto, Decimal("0"))]
        if aranceles > 0:
            lineas.append((cta_arancel.id, aranceles, Decimal("0")))
        if iva_df > 0:
            lineas.append((cta_iva.id, iva_df, Decimal("0")))
        if percepciones_iibb > 0:
            lineas.append((cta_iibb.id, percepciones_iibb, Decimal("0")))
        if retenciones > 0:
            lineas.append((cta_ret.id, retenciones, Decimal("0")))
        lineas.append((ingresos.id, Decimal("0"), monto_bruto))

        a = Asiento(
            fecha=fecha if isinstance(fecha, date) else hoy_art(),
            descripcion=descripcion or f"Liquidación tarjeta {str(marca).capitalize()}",
            modulo="tarjeta_liq",
            referencia_id=liquidacion_id,
            organizacion_id=org_id,
            usuario_id=usuario_id,
            numero_asiento=_next_numero_asiento(db, org_id),
        )
        # Red de seguridad: rechazar si no cuadra en partida doble
        total_debe  = sum(d for _c, d, _h in lineas)
        total_haber = sum(h for _c, _d, h in lineas)
        if abs(total_debe - total_haber) > Decimal("0.01"):
            logger.error(
                "Asiento tarjeta_liq liq %s NO balancea (debe=%s haber=%s) — no se postea",
                liquidacion_id, total_debe, total_haber,
            )
            return None
        db.add(a)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            return None
        for cuenta_id, debe, haber in lineas:
            db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=cuenta_id, debe=debe, haber=haber))
        db.commit()
        return a.id
    except Exception as ex:
        db.rollback()
        logger.warning("Error asiento tarjeta_liq %s: %s", liquidacion_id, ex)
        return None


def registrar_factura_arca(
    db: Session,
    comprobante_id: int,
    org_id: int,
    usuario_id: Optional[int],
    cliente_id: Optional[int],
    cliente_nombre: str,
    importe_neto: Decimal,
    importe_iva: Decimal,
    importe_total: Decimal,
    fecha: date,
) -> Optional[int]:
    """Asiento al obtener el CAE de una factura ARCA:
    Cliente (2-1-2-X) D total  /  Ventas (3-1-5-0) H neto + IVA Débito Fiscal (2-2-1-0) H iva.
    Sin cliente vinculado no se postea (no hay contra-cuenta D) — el comprobante con CAE
    sigue siendo válido igual, solo queda sin reflejo en el Libro Diario."""
    try:
        if _ya_existe(db, "arca_factura", comprobante_id, org_id):
            return None
        importe_neto  = round(_monto(importe_neto), 2)
        importe_iva   = round(_monto(importe_iva), 2)
        importe_total = round(_monto(importe_total), 2)
        if importe_total <= 0 or not cliente_id:
            return None

        cuenta_cliente = _get_o_crear_cuenta_cliente(db, cliente_id, org_id)
        ventas         = _get_cuenta_por_codigo(db, "3-1-5-0", org_id)
        iva_df         = _get_cuenta_por_codigo(db, "2-2-1-0", org_id)
        if not cuenta_cliente or not ventas or (importe_iva > 0 and not iva_df):
            logger.warning("Cuentas factura ARCA incompletas org %s (cliente_id=%s) — no se postea", org_id, cliente_id)
            return None

        lineas = [
            (cuenta_cliente.id, importe_total, Decimal("0")),
            (ventas.id,         Decimal("0"),  importe_neto),
        ]
        if importe_iva > 0:
            lineas.append((iva_df.id, Decimal("0"), importe_iva))

        a = Asiento(
            fecha=fecha if isinstance(fecha, date) else hoy_art(),
            descripcion=f"Factura ARCA — {cliente_nombre or ''}",
            modulo="arca_factura",
            referencia_id=comprobante_id,
            organizacion_id=org_id,
            usuario_id=usuario_id,
            numero_asiento=_next_numero_asiento(db, org_id),
        )
        total_debe  = sum(d for _c, d, _h in lineas)
        total_haber = sum(h for _c, _d, h in lineas)
        if abs(total_debe - total_haber) > Decimal("0.01"):
            logger.error(
                "Asiento arca_factura comprobante %s NO balancea (debe=%s haber=%s) — no se postea",
                comprobante_id, total_debe, total_haber,
            )
            return None
        db.add(a)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            return None
        for cuenta_id, debe, haber in lineas:
            db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=cuenta_id, debe=debe, haber=haber))
        db.commit()
        return a.id
    except Exception as ex:
        db.rollback()
        logger.warning("Error asiento arca_factura %s: %s", comprobante_id, ex)
        return None
