"""Liquidación REAL de IVA a partir de los comprobantes de ARCA.

Mecánica fiscal argentina (RG DDJJ IVA):
  - Débito fiscal   = Σ Total IVA de comprobantes EMITIDOS incluidos del período.
  - Crédito fiscal  = Σ Total IVA de comprobantes RECIBIDOS incluidos del período.
  - Las NOTAS DE CRÉDITO (tipos en `TIPOS_NOTA_CREDITO`) RESTAN en su columna.

  Posición del período:
    tecnico_periodo = débito − crédito.
    posicion = tecnico_periodo − saldo_tecnico_anterior.
      posicion ≤ 0 → saldo_tecnico_nuevo = −posicion, a_pagar_parcial = 0.
      posicion > 0 → saldo_tecnico_nuevo = 0,          a_pagar_parcial = posicion.

  Crédito de LIBRE disponibilidad (retenciones + percepciones + saldo libre
  anterior) cancela el a_pagar_parcial:
    credito_libre ≥ a_pagar_parcial → saldo_libre_nuevo = credito_libre − a_pagar_parcial, saldo_a_pagar = 0.
    credito_libre <  a_pagar_parcial → saldo_libre_nuevo = 0, saldo_a_pagar = a_pagar_parcial − credito_libre.

El saldo TÉCNICO solo compensa IVA (art. 24 primer párrafo); el de LIBRE
disponibilidad puede aplicarse a otros impuestos — por eso se llevan separados.

Los saldos anteriores, si el parámetro llega None, se AUTO-HEREDAN del período
inmediato anterior (mismo org). Pasar el parámetro explícito es un override
manual (bootstrapping del primer período).
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.iva_liquidacion import ComprobanteIva, LiquidacionIva
from app.services.decimal_utils import to_decimal as _D
from app.services.tz import now_art

_DOS = Decimal("0.01")

# NC A/B/C/M + NC FCE MiPyME A/B/C — restan del total de su dirección.
TIPOS_NOTA_CREDITO = {3, 8, 13, 53, 203, 208, 213}


class IvaLiquidacionError(Exception):
    """Error de negocio de la liquidación real de IVA."""


def es_nota_credito(tipo_codigo: int) -> bool:
    return tipo_codigo in TIPOS_NOTA_CREDITO


def _periodo_anterior(periodo: str) -> str:
    anio_s, mes_s = periodo.split("-")
    anio, mes = int(anio_s), int(mes_s)
    if mes == 1:
        return f"{anio - 1:04d}-12"
    return f"{anio:04d}-{mes - 1:02d}"


def _sumar_iva(db: Session, org_id: int, periodo: str, direccion: str) -> tuple[Decimal, int]:
    """Suma el Total IVA de los comprobantes INCLUIDOS de esa dirección/período.
    Las notas de crédito restan. Devuelve (suma, cantidad)."""
    comps = (
        db.query(ComprobanteIva)
        .filter(
            ComprobanteIva.organizacion_id == org_id,
            ComprobanteIva.periodo == periodo,
            ComprobanteIva.direccion == direccion,
            ComprobanteIva.incluido.is_(True),
        )
        .all()
    )
    total = Decimal("0")
    for c in comps:
        iva = _D(c.total_iva)
        if es_nota_credito(c.tipo_codigo):
            total -= iva
        else:
            total += iva
    return total.quantize(_DOS), len(comps)


def calcular_liquidacion(
    db: Session,
    org_id: int,
    periodo: str,
    retenciones: Decimal | None = None,
    percepciones: Decimal | None = None,
    saldo_tecnico_anterior: Decimal | None = None,
    saldo_libre_anterior: Decimal | None = None,
) -> LiquidacionIva:
    """Calcula (y upsertea) la liquidación real de IVA del período.

    Si la liquidación del período ya está 'presentada' → IvaLiquidacionError
    (no se recalcula). El router lo traduce a 409.
    """
    existente = (
        db.query(LiquidacionIva)
        .filter(
            LiquidacionIva.organizacion_id == org_id,
            LiquidacionIva.periodo == periodo,
        )
        .first()
    )
    if existente is not None and existente.estado == "presentada":
        raise IvaLiquidacionError(
            f"La liquidación del período {periodo} ya está presentada; no se recalcula."
        )

    # Saldos anteriores: override manual si vienen, si no heredar del período previo.
    if saldo_tecnico_anterior is None or saldo_libre_anterior is None:
        prev = (
            db.query(LiquidacionIva)
            .filter(
                LiquidacionIva.organizacion_id == org_id,
                LiquidacionIva.periodo == _periodo_anterior(periodo),
            )
            .first()
        )
        if saldo_tecnico_anterior is None:
            saldo_tecnico_anterior = _D(prev.saldo_tecnico_nuevo) if prev else Decimal("0")
        if saldo_libre_anterior is None:
            saldo_libre_anterior = _D(prev.saldo_libre_nuevo) if prev else Decimal("0")

    ret = _D(retenciones).quantize(_DOS) if retenciones is not None else Decimal("0.00")
    perc = _D(percepciones).quantize(_DOS) if percepciones is not None else Decimal("0.00")
    st_ant = _D(saldo_tecnico_anterior).quantize(_DOS)
    sl_ant = _D(saldo_libre_anterior).quantize(_DOS)

    debito, cant_emit = _sumar_iva(db, org_id, periodo, "emitido")
    credito, cant_recib = _sumar_iva(db, org_id, periodo, "recibido")

    tecnico_periodo = (debito - credito).quantize(_DOS)
    posicion = (tecnico_periodo - st_ant).quantize(_DOS)

    if posicion <= 0:
        saldo_tecnico_nuevo = (-posicion).quantize(_DOS)
        a_pagar_parcial = Decimal("0.00")
    else:
        saldo_tecnico_nuevo = Decimal("0.00")
        a_pagar_parcial = posicion

    credito_libre = (ret + perc + sl_ant).quantize(_DOS)
    if credito_libre >= a_pagar_parcial:
        saldo_libre_nuevo = (credito_libre - a_pagar_parcial).quantize(_DOS)
        saldo_a_pagar = Decimal("0.00")
    else:
        saldo_libre_nuevo = Decimal("0.00")
        saldo_a_pagar = (a_pagar_parcial - credito_libre).quantize(_DOS)

    if existente is None:
        existente = LiquidacionIva(
            organizacion_id=org_id,
            periodo=periodo,
            estado="borrador",
        )
        db.add(existente)

    existente.debito_fiscal = debito
    existente.credito_fiscal = credito
    existente.tecnico_periodo = tecnico_periodo
    existente.saldo_tecnico_anterior = st_ant
    existente.saldo_tecnico_nuevo = saldo_tecnico_nuevo
    existente.retenciones = ret
    existente.percepciones = perc
    existente.saldo_libre_anterior = sl_ant
    existente.saldo_libre_nuevo = saldo_libre_nuevo
    existente.saldo_a_pagar = saldo_a_pagar
    existente.cant_emitidos = cant_emit
    existente.cant_recibidos = cant_recib

    db.commit()
    db.refresh(existente)
    return existente


def marcar_presentada(db: Session, liquidacion: LiquidacionIva) -> LiquidacionIva:
    """Marca la liquidación como presentada. Si ya lo estaba → IvaLiquidacionError."""
    if liquidacion.estado == "presentada":
        raise IvaLiquidacionError("La liquidación ya está presentada.")
    liquidacion.estado = "presentada"
    liquidacion.fecha_presentacion = now_art()
    db.commit()
    db.refresh(liquidacion)
    return liquidacion
