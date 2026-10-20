"""Detección del banco a partir del texto de un PDF.

Reusa el diccionario `INDICADORES_BANCO` del parser de Excel (una sola fuente de
verdad), pero el texto de un PDF es mucho más ruidoso que la cabecera de una
planilla: las direcciones dicen "Provincia de Buenos Aires", "Ciudad Autónoma",
y las descripciones de los movimientos nombran a OTROS bancos ("TRANSF. A BANCO
NACION"). Por eso:

- Se puntúa por zonas: la parte de arriba de la página 1 pesa más (logo/razón
  social), después las líneas que se repiten en todas las páginas (encabezado y
  pie legal), y por último el resto de la página 1. Las líneas que parecen
  movimientos (fecha + importe) NO se miran.
- Las palabras sueltas débiles (provincia, ciudad, nacion, industrial, rio,
  frances) solo cuentan como "banco <palabra>" ("Banco Provincia", "Banco de la
  Nación"). Las marcas (galicia, macro, bbva, santander, icbc, hsbc, …) cuentan
  solas.
- Dentro de cada zona se prueban primero las keywords más largas (lección "rio"
  de BUGS.md) y cada banco suma una sola vez por zona.
"""

from __future__ import annotations

import re
from typing import Iterable

from app.services.excel_parser import INDICADORES_BANCO, _kw_en_texto, _normalizar

GENERICO = "generico"
_DEBILES = {"provincia", "ciudad", "nacion", "industrial", "rio", "frances"}

_CANDIDATOS: list[tuple[str, str, bool]] = sorted(
    (
        (banco, _normalizar(kw.lower()), _normalizar(kw.lower()) in _DEBILES)
        for banco, palabras in INDICADORES_BANCO.items()
        for kw in palabras
    ),
    key=lambda t: len(t[1]),
    reverse=True,
)


def _aparece(kw: str, debil: bool, texto: str) -> bool:
    if debil:
        return re.search(r"\bbanco\s+(?:de\s+(?:la\s+)?)?" + re.escape(kw) + r"\b", texto) is not None
    return _kw_en_texto(kw, texto)


def detectar_banco_zonas(zonas: Iterable[tuple[str, float]]) -> str:
    """`zonas` = [(texto, peso)]. Devuelve la clave de INDICADORES_BANCO o "generico"."""
    puntaje: dict[str, float] = {}
    largo: dict[str, int] = {}
    for texto, peso in zonas:
        t = _normalizar((texto or "").lower())
        if not t.strip():
            continue
        vistos: set[str] = set()
        for banco, kw, debil in _CANDIDATOS:
            if banco in vistos:
                continue
            if _aparece(kw, debil, t):
                vistos.add(banco)
                puntaje[banco] = puntaje.get(banco, 0.0) + peso * (0.6 if debil else 1.0)
                largo[banco] = max(largo.get(banco, 0), len(kw))
    if not puntaje:
        return GENERICO
    orden = list(INDICADORES_BANCO)
    return max(puntaje, key=lambda b: (puntaje[b], largo[b], -orden.index(b)))


def detectar_banco_texto(texto: str) -> str:
    """Variante de una sola zona (texto libre)."""
    return detectar_banco_zonas([(texto, 1.0)])
