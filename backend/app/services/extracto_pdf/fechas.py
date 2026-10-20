"""Fechas de los extractos PDF: tokens, período del resumen y año faltante.

Los resúmenes argentinos imprimen la fecha de cada movimiento de muchas formas:
`15/09/2026`, `15/09/26`, `15-09-26`, `15.09.2026`, `2026-09-15`, `15-SEP`,
`15 sep 2026` y — muy común — **sin año**: `15/09`. El año se toma, en orden:

1. del período del resumen ("Período 01/09/2026 al 30/09/2026", "Resumen del …
   al …", "Desde … Hasta …", "Septiembre 2026"),
2. de las otras fechas completas que aparecen en el documento,
3. de `hoy` (inyectable), sin aceptar fechas en el futuro.

Para cada fecha sin año se elige el año que la deja más cerca de la referencia;
eso resuelve solo el cruce diciembre → enero de un resumen que abarca dos años.
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable, Optional

from app.services.excel_parser import _normalizar

MESES = {
    "ene": 1, "enero": 1, "jan": 1,
    "feb": 2, "febrero": 2,
    "mar": 3, "marzo": 3,
    "abr": 4, "abril": 4, "apr": 4,
    "may": 5, "mayo": 5,
    "jun": 6, "junio": 6,
    "jul": 7, "julio": 7,
    "ago": 8, "agosto": 8, "aug": 8,
    "sep": 9, "sept": 9, "set": 9, "septiembre": 9, "setiembre": 9,
    "oct": 10, "octubre": 10,
    "nov": 11, "noviembre": 11,
    "dic": 12, "diciembre": 12, "dec": 12,
}

# (día, mes, año|None)
FechaParcial = tuple[int, int, Optional[int]]

_RE_NUM = re.compile(r"^(\d{1,2})([/\-.])(\d{1,2})(?:\2(\d{4}|\d{2}))?$")
_RE_ISO = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$")
_RE_MES = re.compile(r"^(\d{1,2})[\s\-/.]*([a-z]{3,10})\.?(?:[\s\-/.]*(\d{4}|\d{2}))?$")
_RE_FECHA_LIBRE = re.compile(
    r"(?<![\d/.\-])(\d{1,2})([/\-.])(\d{1,2})\2(\d{4}|\d{2})(?!\d)"
)
_RE_FECHA_ISO_LIBRE = re.compile(r"(?<!\d)(\d{4})-(\d{1,2})-(\d{1,2})(?!\d)")
_RE_FECHA_LARGA = re.compile(r"\b(\d{1,2})\s+de\s+([a-z]+)\s+(?:de(?:l)?\s+)?(\d{4})\b")
_RE_MES_ANIO = re.compile(r"\b([a-z]{3,10})\.?\s*(?:de\s+|del\s+)?[/\-]?\s*(\d{4})\b")
_RE_MM_AAAA = re.compile(r"(?<![\d/])(\d{1,2})/(\d{4})(?![\d/])")

_CLAVES_PERIODO = (
    "periodo", "desde", "hasta", "resumen", "movimientos", "entre", "extracto",
    "consulta", "del ", "fecha de cierre",
)
_CLAVES_MES = ("periodo", "resumen", "mes", "extracto", "movimientos", "liquidacion")


def _anio(raw: Optional[str]) -> Optional[int]:
    if raw is None:
        return None
    y = int(raw)
    if len(raw) == 2:
        y += 2000 if y < 70 else 1900
    return y


def _valida(d: int, m: int, y: Optional[int]) -> bool:
    if not (1 <= m <= 12 and 1 <= d <= 31):
        return False
    if y is None:
        return d <= (29 if m == 2 else calendar.monthrange(2001, m)[1])
    if not 1990 <= y <= 2100:
        return False
    return d <= calendar.monthrange(y, m)[1]


def parsear_fecha(texto: str) -> Optional[FechaParcial]:
    """Fecha de un token o de la celda de fecha. Acepta los formatos de arriba
    (con o sin año). `dd.mm` sin año NO se acepta: se confunde con un importe."""
    if not texto:
        return None
    s = _normalizar(texto.strip().lower())
    m = _RE_NUM.match(s)
    if m:
        d, mes, sep, y = int(m.group(1)), int(m.group(3)), m.group(2), _anio(m.group(4))
        if sep == "." and y is None:
            return None
        return (d, mes, y) if _valida(d, mes, y) else None
    m = _RE_ISO.match(s)
    if m:
        y, mes, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return (d, mes, y) if _valida(d, mes, y) else None
    m = _RE_MES.match(s)
    if m and m.group(2) in MESES:
        d, mes, y = int(m.group(1)), MESES[m.group(2)], _anio(m.group(3))
        return (d, mes, y) if _valida(d, mes, y) else None
    return None


def parsear_fecha_inicio(texto: str) -> Optional[FechaParcial]:
    """Fecha al comienzo de un texto ("15/09 TRANSF…", "15 SEP 2026 …")."""
    if not texto:
        return None
    partes = texto.split()
    for n in (3, 2, 1):
        if len(partes) >= n:
            f = parsear_fecha(" ".join(partes[:n]))
            if f:
                return f
    return None


def a_date(f: Optional[FechaParcial]) -> Optional[date]:
    if f is None or f[2] is None:
        return None
    try:
        return date(f[2], f[1], f[0])
    except ValueError:
        return None


def fechas_completas_en(texto: str) -> list[date]:
    """Todas las fechas con año que aparecen en un texto libre."""
    s = _normalizar(texto.lower())
    out: list[date] = []
    for m in _RE_FECHA_LIBRE.finditer(s):
        d, mes, y = int(m.group(1)), int(m.group(3)), _anio(m.group(4))
        if _valida(d, mes, y):
            out.append(date(y, mes, d))
    for m in _RE_FECHA_ISO_LIBRE.finditer(s):
        y, mes, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if _valida(d, mes, y):
            out.append(date(y, mes, d))
    for m in _RE_FECHA_LARGA.finditer(s):
        mes = MESES.get(m.group(2))
        d, y = int(m.group(1)), int(m.group(3))
        if mes and _valida(d, mes, y):
            out.append(date(y, mes, d))
    return out


def detectar_periodo(lineas: Iterable[str]) -> Optional[tuple[date, date]]:
    """Período del resumen a partir de los textos de las primeras líneas.

    Busca, en orden: una línea con dos fechas completas y una palabra de período
    ("Período 01/09/2026 al 30/09/2026"); un par de líneas "Desde …" / "Hasta …";
    un mes con año ("Septiembre 2026", "09/2026") en una línea que hable de período."""
    textos = [_normalizar(t.lower()) for t in lineas]
    desde_suelto: Optional[date] = None
    hasta_suelto: Optional[date] = None
    for t in textos:
        fechas = fechas_completas_en(t)
        if len(fechas) >= 2 and any(k in t for k in _CLAVES_PERIODO):
            a, b = min(fechas[:2]), max(fechas[:2])
            if 0 <= (b - a).days <= 400:
                return a, b
        if len(fechas) == 1:
            if "desde" in t and desde_suelto is None:
                desde_suelto = fechas[0]
            elif "hasta" in t and hasta_suelto is None:
                hasta_suelto = fechas[0]
    if desde_suelto and hasta_suelto and 0 <= (hasta_suelto - desde_suelto).days <= 400:
        return desde_suelto, hasta_suelto
    for t in textos:
        if not any(k in t for k in _CLAVES_MES) and len(t.split()) > 3:
            continue
        for m in _RE_MES_ANIO.finditer(t):
            mes = MESES.get(m.group(1))
            y = int(m.group(2))
            if mes and 1990 <= y <= 2100:
                return date(y, mes, 1), date(y, mes, calendar.monthrange(y, mes)[1])
        if any(k in t for k in _CLAVES_MES):
            for m in _RE_MM_AAAA.finditer(t):
                mes, y = int(m.group(1)), int(m.group(2))
                if 1 <= mes <= 12 and 1990 <= y <= 2100:
                    return date(y, mes, 1), date(y, mes, calendar.monthrange(y, mes)[1])
    return None


@dataclass
class ContextoFechas:
    """Lo necesario para completar el año de las fechas sin año."""

    referencia: date
    origen: str                         # "periodo" | "documento" | "hoy"
    periodo: Optional[tuple[date, date]]
    hoy: date

    def resolver(self, f: Optional[FechaParcial]) -> Optional[date]:
        if f is None:
            return None
        d, m, y = f
        if y is not None:
            return a_date(f)
        candidatos: list[date] = []
        for anio in (self.referencia.year - 1, self.referencia.year, self.referencia.year + 1):
            try:
                candidatos.append(date(anio, m, d))
            except ValueError:
                continue
        if not candidatos:
            return None
        if self.origen == "hoy":
            # Sin período ni fechas completas: un extracto no puede ser del futuro.
            tope = self.hoy + timedelta(days=7)
            pasados = [c for c in candidatos if c <= tope]
            candidatos = pasados or candidatos
        return min(candidatos, key=lambda c: abs((c - self.referencia).days))


def armar_contexto(
    periodo: Optional[tuple[date, date]],
    fechas_documento: Iterable[date],
    hoy: date,
) -> ContextoFechas:
    if periodo:
        desde, hasta = periodo
        return ContextoFechas(desde + (hasta - desde) / 2, "periodo", periodo, hoy)
    fechas = sorted(f for f in fechas_documento if f <= hoy + timedelta(days=31))
    if fechas:
        return ContextoFechas(fechas[len(fechas) // 2], "documento", None, hoy)
    return ContextoFechas(hoy, "hoy", None, hoy)
