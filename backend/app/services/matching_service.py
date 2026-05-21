"""
Servicio de auto-matching para conciliación bancaria.

Estrategia:
1. Match exacto: mismo monto + fecha exacta
2. Match por monto + ventana de ±3 días
3. Match por referencia (si existe)

Devuelve pares (bank_transaction_id, accounting_entry_id).
"""
from decimal import Decimal
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bank_transaction import BankTransaction
from app.models.accounting_entry import AccountingEntry


async def auto_match(
    db: AsyncSession,
    statement_id: int,
    account_id: int,
) -> list[tuple[int, int]]:
    """
    Busca matches automáticos entre transacciones del extracto y asientos contables.
    Retorna lista de (bank_transaction_id, accounting_entry_id) matcheados.
    """
    # Cargar transacciones no conciliadas del extracto
    txn_result = await db.execute(
        select(BankTransaction).where(
            BankTransaction.statement_id == statement_id,
            BankTransaction.is_reconciled == False,  # noqa: E712
        )
    )
    transactions = txn_result.scalars().all()

    # Cargar asientos no conciliados de la cuenta
    entry_result = await db.execute(
        select(AccountingEntry).where(
            AccountingEntry.account_id == account_id,
            AccountingEntry.is_reconciled == False,  # noqa: E712
        )
    )
    entries = entry_result.scalars().all()

    # Índice de asientos por monto para búsqueda rápida
    entries_by_amount: dict[Decimal, list[AccountingEntry]] = {}
    for entry in entries:
        entries_by_amount.setdefault(entry.amount, []).append(entry)

    matches: list[tuple[int, int]] = []
    used_entry_ids: set[int] = set()

    for txn in transactions:
        candidates = entries_by_amount.get(txn.amount, [])
        best_match = _find_best_match(txn, candidates, used_entry_ids)
        if best_match:
            matches.append((txn.id, best_match.id))
            used_entry_ids.add(best_match.id)

    return matches


def _find_best_match(
    txn: BankTransaction,
    candidates: list[AccountingEntry],
    used_ids: set[int],
    date_window_days: int = 3,
) -> AccountingEntry | None:
    """
    Prioridad de match:
    1. Mismo monto + misma fecha + misma referencia
    2. Mismo monto + misma fecha
    3. Mismo monto + fecha dentro de ventana
    """
    available = [c for c in candidates if c.id not in used_ids]
    if not available:
        return None

    window_start = txn.transaction_date - timedelta(days=date_window_days)
    window_end = txn.transaction_date + timedelta(days=date_window_days)

    # 1. Match exacto con referencia
    if txn.reference:
        for entry in available:
            if entry.entry_date == txn.transaction_date and entry.reference == txn.reference:
                return entry

    # 2. Match exacto por fecha
    exact_date = [e for e in available if e.entry_date == txn.transaction_date]
    if exact_date:
        return exact_date[0]

    # 3. Match por ventana de fechas
    window = [e for e in available if window_start <= e.entry_date <= window_end]
    if window:
        # El más cercano en fecha
        return min(window, key=lambda e: abs((e.entry_date - txn.transaction_date).days))

    return None
