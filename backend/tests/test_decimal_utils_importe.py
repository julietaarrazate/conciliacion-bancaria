"""Tests de `parse_importe_ar` (importes argentinos/US → Decimal a 2 decimales)."""

from decimal import Decimal

import pytest

from app.services.decimal_utils import parse_importe_ar


@pytest.mark.parametrize(
    "raw, esperado",
    [
        # Formato argentino
        ("1.234,56", "1234.56"),
        ("12.345.678,90", "12345678.90"),
        ("1234,56", "1234.56"),
        ("0,00", "0.00"),
        ("0,5", "0.50"),
        (",50", "0.50"),
        # Signos: adelante, atrás, paréntesis, unicode
        ("-1.234,56", "-1234.56"),
        ("1.234,56-", "-1234.56"),
        ("(1.234,56)", "-1234.56"),
        ("+1.234,56", "1234.56"),
        ("1.234,56+", "1234.56"),
        ("−1.234,56", "-1234.56"),
        ("1.234,56 –", "-1234.56"),
        # Moneda en cualquier posición
        ("$ 1.234,56", "1234.56"),
        ("$1.234,56", "1234.56"),
        ("$-1.234,56", "-1234.56"),
        ("-$1.234,56", "-1234.56"),
        ("- $ 1.234,56", "-1234.56"),
        ("$ 1.234,56-", "-1234.56"),
        ("($ 1.234,56)", "-1234.56"),
        ("U$S 10,00", "10.00"),
        ("u$s 10,00", "10.00"),
        ("USD 10.00", "10.00"),
        ("1.234,56 ARS", "1234.56"),
        # Espacios raros (PDF): nbsp, thin space, miles con espacio
        ("\xa01.234,56\xa0", "1234.56"),
        ("1 234,56", "1234.56"),
        ("1 234,56", "1234.56"),
        # Formato US
        ("1,234.56", "1234.56"),
        ("1,234,567.89", "1234567.89"),
        ("1234.56", "1234.56"),
        ("-1,234.56", "-1234.56"),
        # Reglas ambiguas documentadas
        ("1.234", "1234.00"),        # un punto + 3 dígitos → miles AR
        ("999.999", "999999.00"),
        ("1.234.567", "1234567.00"),  # varios puntos → miles AR
        ("1,234,567", "1234567.00"),  # varias comas → miles US
        ("12.5", "12.50"),            # un punto con ≠ 3 decimales → decimal
        ("0.125", "0.13"),            # entero "0" → decimal (redondeo comercial)
        ("1234.567", "1234.57"),      # 4 dígitos delante → no es miles
        ("1234,5", "1234.50"),        # una coma → decimal
        ("12,345", "12.35"),          # una coma siempre es decimal (convención AR)
        ("1.234,567", "1234.57"),
        ("5.", "5.00"),
        ("1500", "1500.00"),
        # Tipos numéricos
        (1234, "1234.00"),
        (-7, "-7.00"),
        (12.345, "12.35"),
        (0.1 + 0.2, "0.30"),
        (Decimal("10.005"), "10.01"),
        (Decimal("-3"), "-3.00"),
    ],
)
def test_parse_importe_ar_valores(raw, esperado):
    resultado = parse_importe_ar(raw)
    assert isinstance(resultado, Decimal)
    assert resultado == Decimal(esperado)
    assert resultado.as_tuple().exponent == -2


@pytest.mark.parametrize(
    "raw",
    [None, "", "   ", "-", "--", "$", "U$S", "abc", "12a", "1.2.3", "1,2,3", "1.23.456",
     "1.234,56.78", "1,234,56", "15/09/2026", "20-12345678-9", "()", True, False,
     float("nan"), float("inf"), Decimal("NaN"), [], {}],
)
def test_parse_importe_ar_invalidos(raw):
    assert parse_importe_ar(raw) is None


@pytest.mark.parametrize(
    "raw",
    ["1" + "0" * 30, "1.000.000.000.000.000.000.000.000.000,00", "1e400", "Infinity",
     Decimal("1E+40"), 10 ** 40, 1e300],
)
def test_parse_importe_ar_numeros_absurdos_no_lanzan(raw):
    # Más dígitos que la precisión de Decimal (PDF roto, lectura de IA delirante): None, nunca una excepción.
    assert parse_importe_ar(raw) is None
