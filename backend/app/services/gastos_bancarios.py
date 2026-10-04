"""Resumen de gastos bancarios y "% explicado" de un extracto.

100% read-only: no toca el motor de conciliación, no muta movimientos ni genera
asientos. Lee el concepto (`MovimientoBanco.titular`) de cada débito y lo agrupa
por tipo de gasto (comisiones, impuesto Ley 25.413, SIRCREB/IIBB, IVA, …) para
que el cliente pueda cuadrar la nota de débito del banco al centavo sin sumar a
mano.

Reglas:
- Solo se clasifican DÉBITOS (monto < 0). Un crédito de un cliente que se llame
  "IVA SRL" o "Comisiones SA" nunca cuenta como gasto.
- Primera regla que matchea gana (el orden importa: "PERCEPCION IVA" va antes
  que "IVA", "SIRCREB" antes que todo lo demás de IIBB).
- Montos en Decimal punta a punta (ver docs/database/DATABASE_RULES.md).
"""

import re
import unicodedata
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional, Tuple

from app.services.conciliacion import es_libre


def _norm(texto: str) -> str:
    """Minúsculas sin acentos ("Comisión" → "comision")."""
    t = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in t if not unicodedata.combining(c)).lower()


# (concepto legible, regex sobre el texto normalizado). Orden = prioridad.
_REGLAS: List[Tuple[str, "re.Pattern[str]"]] = [
    ("Impuesto Ley 25.413 (débitos y créditos)", re.compile(
        r"25\.?413|imp(uesto)?\.?\s*(a\s+los\s+)?(s/\s*)?(deb|cred)(ito)?s?\b|imp\.?\s*s/\s*(deb|cred)")),
    ("SIRCREB / Ingresos Brutos", re.compile(
        r"sircreb|ing(resos)?\.?\s*brutos|\biibb\b|\bii\.?\s*bb\b|(ret|perc)\w*\.?\s*(de\s+)?i\.?b\b")),
    ("Percepción IVA", re.compile(r"(perc|percep)\w*\.?\s*(de\s+)?iva|rg\.?\s*2408")),
    ("IVA", re.compile(r"\biva\b")),
    ("Comisiones y mantenimiento", re.compile(
        r"comision|\bcom\.|\bcom\s|mantenimiento|\bmant\.|servicio de cuenta|serv\.?\s*cta|paquete|chequera|cargo por")),
    ("Intereses y sellos", re.compile(r"interes|sellado|\bsellos?\b")),
]


def clasificar_gasto(titular: Optional[str], monto) -> Optional[str]:
    """Concepto de gasto bancario del movimiento, o None si no es un gasto."""
    try:
        if monto is None or Decimal(str(monto)) >= 0:
            return None
    except Exception:
        return None
    texto = _norm(titular or "")
    if not texto:
        return None
    for concepto, patron in _REGLAS:
        if patron.search(texto):
            return concepto
    return None


def resumen_extracto(movimientos: Iterable) -> Dict[str, Any]:
    """Gastos bancarios agrupados por concepto + % de ingresos ya explicados.

    Returns:
        gastos_bancarios: {conceptos: [{concepto, cantidad, total}], cantidad, total}
            `total` en positivo (lo que se llevó el banco).
        explicado: {creditos, acreditados, sin_acreditar, porcentaje}
            créditos (monto > 0) del extracto acreditados a un cliente.
            `porcentaje` es None si el extracto no tiene créditos.
    """
    por_concepto: Dict[str, Dict[str, Any]] = {}
    creditos = 0
    acreditados = 0

    for m in movimientos or []:
        monto = getattr(m, "monto", None)
        if monto is None:
            continue
        try:
            monto_d = Decimal(str(monto))
        except Exception:
            continue

        if monto_d > 0:
            creditos += 1
            if not es_libre(getattr(m, "cliente_acreditado", None)):
                acreditados += 1
            continue

        concepto = clasificar_gasto(getattr(m, "titular", None), monto_d)
        if concepto:
            g = por_concepto.setdefault(concepto, {"concepto": concepto, "cantidad": 0, "total": Decimal("0")})
            g["cantidad"] += 1
            g["total"] += -monto_d

    orden = {c: i for i, (c, _) in enumerate(_REGLAS)}
    conceptos = sorted(por_concepto.values(), key=lambda g: orden[g["concepto"]])
    for g in conceptos:
        g["total"] = g["total"].quantize(Decimal("0.01"))

    total_gastos = sum((g["total"] for g in conceptos), Decimal("0")).quantize(Decimal("0.01"))
    porcentaje = (
        float((Decimal(acreditados) * 100 / Decimal(creditos)).quantize(Decimal("0.1")))
        if creditos else None
    )

    return {
        "gastos_bancarios": {
            "conceptos": conceptos,
            "cantidad": sum(g["cantidad"] for g in conceptos),
            "total": total_gastos,
        },
        "explicado": {
            "creditos": creditos,
            "acreditados": acreditados,
            "sin_acreditar": creditos - acreditados,
            "porcentaje": porcentaje,
        },
    }
