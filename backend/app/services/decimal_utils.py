"""Helpers de conversión a Decimal compartidos por los servicios financieros."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Optional


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


# ── Importes en formato argentino (o US) → Decimal ─────────────────────────
# Canónico para el lector de extractos PDF (y para lo nuevo que lo necesite).
# Los parsers viejos (`excel_parser._parse_monto`, `tarjeta_parser._parse_decimal`,
# etc.) NO se tocan: tienen tests que fijan su comportamiento actual.

_CENTAVO = Decimal("0.01")
_MENOS = ("-", "−", "–")          # guion, signo menos unicode, raya corta
_MONEDAS = ("U$S", "U$D", "US$", "USD", "AR$", "ARS", "$")
_ESPACIOS = ("\xa0", " ", " ", " ", "\t")


def _grupos_de_miles_validos(partes: list[str]) -> bool:
    """`["1", "234", "567"]` → True: el primer grupo 1-3 dígitos, el resto de a 3."""
    if not partes or not partes[0].isdigit() or not 1 <= len(partes[0]) <= 3:
        return False
    return all(p.isdigit() and len(p) == 3 for p in partes[1:])


def _al_centavo(valor: Decimal) -> Optional[Decimal]:
    """Redondea a 0,01; None si el número es demasiado grande para la precisión de
    Decimal (p. ej. `1E+40` o 30 dígitos leídos de un PDF roto): no es un importe."""
    try:
        return valor.quantize(_CENTAVO, rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None


def parse_importe_ar(raw) -> Optional[Decimal]:
    """Convierte un importe escrito como lo imprimen los bancos argentinos a
    `Decimal` cuantizado a 0,01 (redondeo comercial). Devuelve None si no es un
    importe (texto vacío, "-", letras, etc.). Nunca lanza.

    Formatos aceptados:
      - `1.234,56` · `1234,56` · `-1.234,56` · `1.234,56-` (signo al final, típico
        de Galicia/Macro) · `(1.234,56)` (negativo contable) · `+1.234,56`
      - Con moneda: `$ 1.234,56`, `$-1.234,56`, `- $ 1.234,56`, `U$S 10,00`, `USD 10.00`
        (la moneda se descarta: quien llama sabe en qué moneda está la cuenta).
      - Formato US: `1,234.56` · `1234.56`.
      - Miles con espacio: `1 234,56`.
      - int / float / Decimal (los float pasan por `str` para no arrastrar binario).

    Reglas de separadores (las ambiguas, documentadas):
      - Con coma Y punto: el que está más a la derecha es el decimal.
      - Solo comas: una coma es decimal (`1234,5` → 1234.50); varias comas son
        miles US (`1,234,567` → 1234567), y tienen que formar grupos de 3.
      - Solo puntos: varios puntos son miles AR (`1.234.567`), en grupos de 3.
        Un único punto con EXACTAMENTE 3 dígitos detrás y 1-3 dígitos (≠ "0")
        delante es separador de miles AR: `1.234` → 1234 (así imprimen los bancos
        los importes sin centavos). Cualquier otro punto único es decimal:
        `1234.56`, `12.5`, `0.125`, `1234.567`.
    """
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, Decimal):
        if not raw.is_finite():
            return None
        return _al_centavo(raw)
    if isinstance(raw, int):
        return _al_centavo(Decimal(raw))
    if isinstance(raw, float):
        if raw != raw or raw in (float("inf"), float("-inf")):
            return None
        return _al_centavo(Decimal(str(raw)))
    if not isinstance(raw, str):
        return None

    s = raw.strip()
    for esp in _ESPACIOS:
        s = s.replace(esp, "")
    if not s:
        return None

    negativo = False
    # Paréntesis contables: "(1.234,56)" o "($ 1.234,56)".
    if s.startswith("(") and s.endswith(")"):
        negativo = True
        s = s[1:-1]

    # Moneda y signos pueden venir en cualquier orden alrededor del número:
    # "-$1.234,56", "$-1.234,56", "1.234,56-", "$1.234,56-". Se pelan en bucle.
    cambio = True
    while cambio and s:
        cambio = False
        su = s.upper()
        for mon in _MONEDAS:
            if su.startswith(mon):
                s, cambio = s[len(mon):], True
                break
            if su.endswith(mon):
                s, cambio = s[: -len(mon)], True
                break
        if cambio:
            continue
        if s[:1] in _MENOS:
            negativo, s, cambio = True, s[1:], True
        elif s[-1:] in _MENOS:
            negativo, s, cambio = True, s[:-1], True
        elif s[:1] == "+":
            s, cambio = s[1:], True
        elif s[-1:] == "+":
            s, cambio = s[:-1], True
        elif s.startswith("(") and s.endswith(")"):
            negativo, s, cambio = True, s[1:-1], True

    if not s or any(c not in "0123456789.," for c in s) or not any(c.isdigit() for c in s):
        return None

    coma, punto = s.count(","), s.count(".")
    if coma and punto:
        if s.rfind(",") > s.rfind("."):
            entero, _, decimales = s.rpartition(",")
            if entero.count(",") or not _grupos_de_miles_validos(entero.split(".")):
                return None
        else:
            entero, _, decimales = s.rpartition(".")
            if entero.count(".") or not _grupos_de_miles_validos(entero.split(",")):
                return None
        normal = entero.replace(".", "").replace(",", "") + "." + decimales
    elif coma:
        if coma == 1:
            entero, _, decimales = s.partition(",")
            normal = (entero or "0") + "." + decimales
        elif _grupos_de_miles_validos(s.split(",")):
            normal = s.replace(",", "")
        else:
            return None
    elif punto:
        if punto > 1:
            if not _grupos_de_miles_validos(s.split(".")):
                return None
            normal = s.replace(".", "")
        else:
            entero, _, decimales = s.partition(".")
            if len(decimales) == 3 and 1 <= len(entero) <= 3 and entero.isdigit() and entero != "0":
                normal = entero + decimales          # "1.234" → miles AR
            else:
                normal = (entero or "0") + "." + decimales
    else:
        normal = s

    if normal.endswith("."):
        normal += "0"
    try:
        valor = Decimal(normal)
    except (InvalidOperation, ValueError):
        return None
    if negativo:
        valor = -valor
    return _al_centavo(valor) if valor.is_finite() else None
