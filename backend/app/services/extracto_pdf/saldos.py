"""Validación de saldos de un extracto (Decimal punta a punta).

Única fuente de verdad del "¿cierra el extracto?": la usa el lector al leer el
PDF y el servicio al confirmar las filas que editó la persona.

    saldo_inicial + créditos − débitos = saldo_final      (tolerancia 0,01)

y, cuando las filas traen saldo, el control fila por fila del saldo corrido
(`saldo[i] = saldo[i-1] + monto[i]` en orden cronológico).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional, Sequence

from app.services.decimal_utils import parse_importe_ar

TOLERANCIA = Decimal("0.01")
CERO = Decimal("0.00")
MOTIVO_SALTO = "El saldo no sigue"


def _dec(v) -> Optional[Decimal]:
    return parse_importe_ar(v)


def validar_saldos(
    movimientos: Sequence[dict],
    *,
    orden: str,
    saldo_inicial,
    saldo_final,
) -> dict:
    """Valida un extracto. `movimientos` en el orden en que se muestran
    (`orden` = "asc": el más viejo primero; "desc": el más nuevo primero), con
    `monto` (crédito +, débito −) y `saldo` opcional; acepta Decimal, str o número.

    Si falta el saldo inicial se infiere de la primera fila (cronológica) con
    saldo: `saldo − montos hasta esa fila`. Si falta el final, solo del saldo de
    la última fila cronológica (si no lo trae, queda sin saldo final y no cierra).
    `cierra` exige que la diferencia sea ≤ 0,01 y que no haya saltos en el saldo
    corrido. `filas_con_salto` usa los índices del orden recibido."""
    n = len(movimientos)
    indices = list(range(n)) if orden != "desc" else list(range(n - 1, -1, -1))
    montos = [_dec(m.get("monto")) or CERO for m in movimientos]
    saldos = [_dec(m.get("saldo")) for m in movimientos]

    si = _dec(saldo_inicial)
    sf = _dec(saldo_final)
    si_inferido = sf_inferido = False

    if si is None:
        acumulado = CERO
        for i in indices:
            acumulado += montos[i]
            if saldos[i] is not None:
                si = saldos[i] - acumulado
                si_inferido = True
                break
    if sf is None and indices and saldos[indices[-1]] is not None:
        # Solo de la última fila cronológica: si no trae saldo, sus importes no
        # se pueden controlar y deducir el final de ellos sería darlos por buenos.
        sf = saldos[indices[-1]]
        sf_inferido = True

    total_creditos = sum((m for m in montos if m > 0), CERO)
    total_debitos = sum((-m for m in montos if m < 0), CERO)

    calculado = si + total_creditos - total_debitos if si is not None else None
    diferencia = sf - calculado if (sf is not None and calculado is not None) else None
    saltos: list[int] = []
    previo = si
    for i in indices:
        if saldos[i] is not None:
            if previo is not None and abs(previo + montos[i] - saldos[i]) > TOLERANCIA:
                saltos.append(i)
            previo = saldos[i]
        elif previo is not None:
            previo = previo + montos[i]
    saltos.sort()
    # Dos saltos pueden compensarse y dejar la diferencia en cero: con un salto
    # en el saldo corrido el extracto no cierra aunque los totales den.
    cierra = diferencia is not None and abs(diferencia) <= TOLERANCIA and not saltos

    return {
        "saldo_inicial": si,
        "saldo_inicial_inferido": si_inferido,
        "saldo_final": sf,
        "saldo_final_inferido": sf_inferido,
        "total_creditos": total_creditos,
        "total_debitos": total_debitos,
        "cantidad": n,
        "saldo_final_calculado": calculado,
        "diferencia": diferencia,
        "cierra": cierra,
        "filas_con_salto": saltos,
    }


def marcar_dudosas(movimientos: list[dict], cuadre: dict) -> list[dict]:
    """Marca `dudosa=True` + motivo en las filas donde se corta el saldo corrido.
    Modifica y devuelve la misma lista."""
    for i in cuadre.get("filas_con_salto") or []:
        if 0 <= i < len(movimientos):
            fila = movimientos[i]
            motivos = fila.setdefault("motivos", [])
            if MOTIVO_SALTO not in motivos:
                motivos.append(MOTIVO_SALTO)
            fila["dudosa"] = True
    return movimientos


def formatear_pesos(valor: Optional[Decimal]) -> str:
    """`Decimal("-1234.5")` → "-$ 1.234,50" (para mensajes al usuario)."""
    if valor is None:
        return "—"
    v = Decimal(valor).quantize(TOLERANCIA)
    signo = "-" if v < 0 else ""
    entero, _, dec = f"{abs(v):,.2f}".partition(".")
    return f"{signo}$ {entero.replace(',', '.')},{dec}"
