"""Helpers de conversión a Decimal compartidos por los servicios financieros."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation


def to_decimal(v) -> Decimal:
    """Convierte cualquier valor numérico (None, float, str, Decimal) a Decimal.

    None o valores no convertibles devuelven Decimal('0') en vez de lanzar."""
    if v is None:
        return Decimal("0")
    if isinstance(v, Decimal):
        return v
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")
