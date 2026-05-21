"""
Servicio de auto-matching para conciliación bancaria.

Estrategia mejorada:
1. Match exacto: monto + fecha + referencia (best)
2. Match por monto + ventana de fechas configurable
3. Detección de "duplicado por fecha distinta": el mismo (cliente, monto, ref) ya fue
   acreditado en otra fecha → marca la txn con fecha_acreditacion_original (NO error).
4. Marca de estados: 'no_esta' (movimiento de planilla sin contraparte) y
   'faltan_datos' (txn sin cliente identificable).

Devuelve un dict con:
  - matches: list[(bank_transaction_id, accounting_entry_id)]
  - no_esta: list[movimiento_planilla_id]
  - faltan_datos: list[bank_transaction_id]
"""
from decimal import Decimal
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bank_transaction import BankTransaction
from app.models.accounting_entry import AccountingEntry
from app.models.planilla import MovimientoPlanilla, PlanillaCliente
from app.models.cliente import Cliente


DEFAULT_DATE_WINDOW = 5  # días — ajustado para realidad argentina (extractos con atraso)


async def auto_match(
    db: AsyncSession,
    statement_id: int,
    account_id: int,
    date_window_days: int = DEFAULT_DATE_WINDOW,
) -> list[tuple[int, int]]:
    """Versión simple: retorna lista de (bank_transaction_id, accounting_entry_id) matcheados.
    Para resultados extendidos usar auto_match_full."""
    full = await auto_match_full(db, statement_id, account_id, date_window_days)
    return full["matches"]


async def auto_match_full(
    db: AsyncSession,
    statement_id: int,
    account_id: int,
    date_window_days: int = DEFAULT_DATE_WINDOW,
) -> dict:
    """Match completo. Retorna matches + estados detectados (duplicados, no_esta, faltan_datos)."""
    txn_result = await db.execute(
        select(BankTransaction).where(
            BankTransaction.statement_id == statement_id,
            BankTransaction.is_reconciled == False,  # noqa: E712
        )
    )
    transactions = list(txn_result.scalars().all())

    entry_result = await db.execute(
        select(AccountingEntry).where(
            AccountingEntry.account_id == account_id,
            AccountingEntry.is_reconciled == False,  # noqa: E712
        )
    )
    entries = list(entry_result.scalars().all())

    entries_by_amount: dict[Decimal, list[AccountingEntry]] = {}
    for entry in entries:
        entries_by_amount.setdefault(entry.amount, []).append(entry)

    # Ya acreditados (extractos anteriores) por (monto, referencia) → para detectar acreditación previa
    prev_acred = await db.execute(
        select(BankTransaction).where(
            BankTransaction.is_reconciled == True,  # noqa: E712
            BankTransaction.statement_id != statement_id,
        )
    )
    prev_by_key: dict[tuple, BankTransaction] = {}
    for t in prev_acred.scalars().all():
        prev_by_key[(t.amount, t.reference or "")] = t

    matches: list[tuple[int, int]] = []
    used_entry_ids: set[int] = set()
    faltan_datos_ids: list[int] = []

    for txn in transactions:
        # Detectar acreditación previa con fecha distinta
        prev = prev_by_key.get((txn.amount, txn.reference or ""))
        if prev:
            txn.fecha_acreditacion_original = prev.transaction_date
            txn.estado = "acreditado"
            txn.is_reconciled = True
            continue

        # Detectar "faltan datos": no se puede identificar cliente
        if not txn.cliente_id and not txn.reference:
            txn.estado = "faltan_datos"
            faltan_datos_ids.append(txn.id)

        candidates = entries_by_amount.get(txn.amount, [])
        best = _find_best_match(txn, candidates, used_entry_ids, date_window_days)
        if best:
            matches.append((txn.id, best.id))
            used_entry_ids.add(best.id)
            txn.estado = "acreditado"

    # Detectar 'no_esta': movimientos de planilla activos cuyo monto no aparece en este extracto
    no_esta_ids: list[int] = []
    if transactions:
        # set de montos del extracto
        montos_extracto = {t.amount for t in transactions}
        # Movimientos pendientes en planillas activas
        mov_result = await db.execute(
            select(MovimientoPlanilla)
            .join(PlanillaCliente, PlanillaCliente.id == MovimientoPlanilla.planilla_id)
            .join(Cliente, Cliente.id == PlanillaCliente.cliente_id)
            .where(MovimientoPlanilla.estado == "pendiente", Cliente.activo == True)  # noqa: E712
        )
        for mov in mov_result.scalars().all():
            if mov.monto not in montos_extracto:
                mov.estado = "no_esta"
                no_esta_ids.append(mov.id)

    return {
        "matches": matches,
        "no_esta": no_esta_ids,
        "faltan_datos": faltan_datos_ids,
    }


def _find_best_match(
    txn: BankTransaction,
    candidates: list,
    used_ids: set[int],
    date_window_days: int,
):
    available = [c for c in candidates if c.id not in used_ids]
    if not available:
        return None

    window_start = txn.transaction_date - timedelta(days=date_window_days)
    window_end = txn.transaction_date + timedelta(days=date_window_days)

    # 1. Exacto con referencia
    if txn.reference:
        for entry in available:
            if entry.entry_date == txn.transaction_date and entry.reference == txn.reference:
                return entry

    # 2. Mismo día
    exact_date = [e for e in available if e.entry_date == txn.transaction_date]
    if exact_date:
        return exact_date[0]

    # 3. Ventana de fechas — el más cercano
    window = [e for e in available if window_start <= e.entry_date <= window_end]
    if window:
        return min(window, key=lambda e: abs((e.entry_date - txn.transaction_date).days))

    return None
