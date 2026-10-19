"""Lectura de la tabla de movimientos de un extracto PDF con texto.

Todo pasa por un **layout**: la descripción de las columnas por posición
horizontal. Es un dict JSON-serializable (lo mismo que se guarda como molde):

    {
      "version": 1,
      "tipo": "encabezado" | "estructural" | "ia",
      "columnas": [{"campo": "fecha", "lo": 0.0, "hi": 82.5}, ...],   # bandas contiguas
      "ancla": "fecha descripcion origen credito debito saldo",          # texto normalizado
      "ancla_x0": 40.0,
    }

`campo` ∈ fecha | descripcion | referencia | otro | signo | debito | credito | importe | saldo.
`signo` es la columna que dice "Débito"/"Crédito" (o D/C) con el importe sin signo
en otra columna. Cada palabra cae en la banda que contiene su centro. El `ancla` es la línea que
marca el comienzo de la tabla en cada página (el encabezado de columnas, o la
línea de arriba de la primera fila si no hay encabezado reconocible).

Hay tres maneras de armar un layout y UNA sola de leer con él (`leer_con_layout`):

- `layouts_por_encabezado`: encuentra la fila de títulos ("Fecha | Descripción |
  Débito | Crédito | Saldo") con los diccionarios del parser de Excel y ajusta las
  bandas con la posición real de los datos.
- `layouts_estructurales`: sin títulos reconocibles, usa las líneas que empiezan
  con una fecha y agrupa los importes por su borde derecho (columnas alineadas);
  la columna de más a la derecha es el saldo.
- `molde.inducir_layout` (en otro módulo): a partir de las filas que leyó la IA.

Un **importe** es un token con exactamente 2 decimales (formato AR o US), con
signo opcional adelante/atrás o entre paréntesis: así no se confunde con números
de comprobante, CUIT o CBU.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from decimal import Decimal
from itertools import product
from typing import Optional

from app.services.decimal_utils import parse_importe_ar
from app.services.excel_parser import (
    KEYWORDS_CREDITO,
    KEYWORDS_DEBITO,
    KEYWORDS_FECHA,
    KEYWORDS_MONTO,
    KEYWORDS_ORDEN,
    KEYWORDS_SALDO,
    KEYWORDS_TITULAR,
    _normalizar,
)

from .fechas import ContextoFechas, FechaParcial, parsear_fecha
from .texto import Documento, Linea

CAMPOS_IMPORTE = ("debito", "credito", "importe", "saldo")
CAMPOS_MOVIMIENTO = ("debito", "credito", "importe")
CAMPOS_TEXTO = ("fecha", "descripcion", "referencia", "otro", "signo")
BANDA_MAX = 10000.0
CERO = Decimal("0.00")
TOL = Decimal("0.01")

MOTIVO_SIN_FECHA = "Sin fecha"
MOTIVO_FUERA_PERIODO = "Fecha fuera del período"
MOTIVO_SIGNO = "Signo sin confirmar"
MOTIVO_DOBLE = "Tiene débito y crédito en la misma fila"
MOTIVO_VARIOS = "Hay más de un importe en la misma columna"

# ── Tokens ──────────────────────────────────────────────────────────────────

_NUM = r"(?:\d{1,3}(?:\.\d{3})+,\d{2}|\d+,\d{2}|\d{1,3}(?:,\d{3})+\.\d{2}|\d+\.\d{2})"
_SIG = "[-+−–]?"
_RE_IMPORTE = re.compile(
    r"^\(?" + _SIG + r"(?:U\$S|US\$|U\$D|USD|\$)?" + _SIG + _NUM + _SIG + r"\)?$", re.IGNORECASE
)
_PREFIJOS_IMPORTE = {"-", "−", "–", "+", "$", "$-", "-$", "u$s", "us$", "usd", "(", "($", "(-", "-($"}
_SUFIJOS_IMPORTE = {"-", "−", "–", "+", ")", "-)"}


@dataclass(slots=True)
class Token:
    texto: str
    x0: float
    x1: float
    size: float
    importe: Optional[Decimal] = None      # None si no es un importe
    negativo: bool = False                 # signo negativo explícito en el PDF

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2


def es_importe(texto: str) -> bool:
    t = texto.replace(" ", "")
    return bool(_RE_IMPORTE.match(t)) and parse_importe_ar(t) is not None


def _token(texto: str, x0: float, x1: float, size: float) -> Token:
    tok = Token(texto, x0, x1, size)
    if es_importe(texto):
        valor = parse_importe_ar(texto.replace(" ", ""))
        tok.importe = valor
        tok.negativo = valor is not None and valor < 0
    return tok


def tokens(linea: Linea) -> list[Token]:
    """Palabras de la línea como tokens; une signos/moneda sueltos a su importe
    ("-" "1.234,56" → "-1.234,56", "1.234,56" "-" → "1.234,56-", "$" "10,00")."""
    cache = linea.cache.get("tokens")
    if cache is not None:
        return cache
    base = [_token(p.texto, p.x0, p.x1, p.size) for p in linea.palabras]
    out: list[Token] = []
    i = 0
    while i < len(base):
        t = base[i]
        if t.importe is None and t.texto.lower() in _PREFIJOS_IMPORTE:
            # Prefijos encadenados ("-" "$" "1.234,56").
            j = i
            texto = t.texto
            while j + 1 < len(base) and base[j + 1].x0 - base[j].x1 <= 1.2 * max(t.size, 1.0):
                j += 1
                texto += base[j].texto
                if base[j].importe is not None or base[j].texto.lower() not in _PREFIJOS_IMPORTE:
                    break
            if j > i and es_importe(texto):
                t = _token(texto, t.x0, base[j].x1, max(t.size, base[j].size))
                i = j
        if t.importe is not None and i + 1 < len(base):
            sig = base[i + 1]
            if sig.texto in _SUFIJOS_IMPORTE and sig.x0 - t.x1 <= 0.8 * max(t.size, 1.0):
                texto = t.texto + sig.texto
                if es_importe(texto):
                    t = _token(texto, t.x0, sig.x1, t.size)
                    i += 1
        out.append(t)
        i += 1
    linea.cache["tokens"] = out
    return out


def texto_normalizado(texto: str) -> str:
    """Minúsculas, sin acentos, solo palabras de letras (sin dígitos)."""
    return " ".join(re.findall(r"[a-z]+", _normalizar((texto or "").lower())))


_PALABRAS_DEBITO = {"debito", "deb", "db", "d", "debe"}
_PALABRAS_CREDITO = {"credito", "cred", "cr", "c", "haber"}


def signo_de_texto(texto: str) -> Optional[int]:
    """−1 / +1 si el texto es solo la marca de débito o crédito ("Débito", "D",
    "CR", "Haber"); None si es cualquier otra cosa."""
    palabra = texto_normalizado(texto)
    if palabra in _PALABRAS_DEBITO:
        return -1
    if palabra in _PALABRAS_CREDITO:
        return 1
    return None


def texto_ancla(linea: Linea) -> str:
    cache = linea.cache.get("ancla")
    if cache is None:
        cache = texto_normalizado(linea.texto)
        linea.cache["ancla"] = cache
    return cache


def tiene_importe(linea: Linea) -> bool:
    return any(t.importe is not None for t in tokens(linea))


def fecha_al_inicio(linea: Linea) -> tuple[Optional[FechaParcial], int]:
    """(fecha, cantidad de tokens que ocupa) si la línea empieza con una fecha."""
    toks = tokens(linea)
    for n in (3, 2, 1):
        if len(toks) >= n:
            f = parsear_fecha(" ".join(t.texto for t in toks[:n]))
            if f:
                return f, n
    return None, 0


# ── Encabezados de columnas ─────────────────────────────────────────────────

def _simples(lista: list[str]) -> list[str]:
    return [_normalizar(k) for k in lista if re.fullmatch(r"[a-z]+", _normalizar(k))]


# Reusa los diccionarios del parser de Excel + palabras propias de los PDF.
_PREFIJOS_CAMPO: dict[str, list[str]] = {
    "saldo": _simples(KEYWORDS_SALDO),
    "fecha": _simples(KEYWORDS_FECHA) + ["dia"],
    "debito": _simples(KEYWORDS_DEBITO) + ["egreso", "retiro"],
    "credito": _simples(KEYWORDS_CREDITO) + ["ingreso", "deposito", "abono"],
    "importe": _simples(KEYWORDS_MONTO) + ["valor"],
    "referencia": _simples(KEYWORDS_ORDEN)
    + ["comprob", "combte", "cbte", "ref", "id", "doc", "documento", "cheque", "n"],
    "descripcion": _simples(KEYWORDS_TITULAR) + ["movimiento", "leyenda", "transaccion", "operacion", "causal"],
    "otro": ["origen", "canal", "sucursal", "suc", "cod", "codigo", "hora", "categoria", "terminal"],
}
_PRIORIDAD = ["saldo", "fecha", "debito", "credito", "importe", "referencia", "descripcion", "otro"]
_FUERTES = {"debito", "credito", "importe", "saldo"}
_KW_ORDENADAS = sorted(
    ((k, campo) for campo, ks in _PREFIJOS_CAMPO.items() for k in ks), key=lambda kc: len(kc[0]), reverse=True
)


def _campo_de_palabra(palabra: str) -> set[str]:
    campos: set[str] = set()
    for t in re.findall(r"[a-z]+", _normalizar(palabra.lower())):
        for k, campo in _KW_ORDENADAS:
            if t == k or (len(k) >= 3 and t.startswith(k)):
                campos.add(campo)
                break
    return campos


@dataclass(slots=True)
class Celda:
    campo: str
    x0: float
    x1: float

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2


def _prioritario(campos: set[str]) -> Optional[str]:
    for c in _PRIORIDAD:
        if c in campos:
            return c
    return None


def celdas_encabezado(linea: Linea) -> Optional[list[Celda]]:
    """Si la línea es una fila de títulos de columnas, sus celdas (en orden x)."""
    toks = tokens(linea)
    if not toks or any(t.importe is not None for t in toks) or len(toks) > 30:
        return None
    if any(parsear_fecha(t.texto) for t in toks):
        return None
    # Frases: palabras separadas por ~un espacio.
    frases: list[list[Token]] = [[toks[0]]]
    for t in toks[1:]:
        prev = frases[-1][-1]
        if t.x0 - prev.x1 <= 0.8 * max(prev.size, 1.0):
            frases[-1].append(t)
        else:
            frases.append([t])
    celdas: list[Celda] = []
    dobles: list[Celda] = []
    for frase in frases:
        por_palabra = [_campo_de_palabra(t.texto) for t in frase]
        fuertes = {c for cs in por_palabra for c in cs if c in _FUERTES}
        if len(frase) > 1 and len(fuertes) >= 2 and not ("fecha" in por_palabra[0]):
            grupos = [[t] for t in frase]          # "Débito Crédito" pegados: separar
        else:
            grupos = [frase]
        for grupo in grupos:
            campos = set().union(*(_campo_de_palabra(t.texto) for t in grupo))
            texto_grupo = _normalizar(" ".join(t.texto for t in grupo).lower())
            if re.match(r"^f(ec)?\s*\.?\s*valor\b", texto_grupo):
                campos = {"otro"}                    # "F.Valor" (fecha valor), no un importe
            doble = len(grupo) == 1 and {"debito", "credito"} <= campos
            if doble:
                campo = "importe"                    # "Débito/Crédito" = una sola columna con signo
            else:
                campo = _prioritario(campos)
            if campo is None:
                if celdas and grupo[0].x0 - celdas[-1].x1 <= 0.8 * max(grupo[0].size, 1.0):
                    celdas[-1].x1 = grupo[-1].x1
                    continue
                campo = "otro"
            celdas.append(Celda(campo, grupo[0].x0, grupo[-1].x1))
            if doble:
                dobles.append(celdas[-1])
    # "Débito/Crédito" junto a otra columna "Monto"/"Importe": dice el signo del
    # importe de la otra columna (los datos de abajo son "Débito" o "Crédito").
    if dobles and any(c.campo == "importe" and all(c is not d for d in dobles) for c in celdas):
        for c in dobles:
            c.campo = "signo"
    # Solo la primera columna de cada campo cuenta ("Fecha" y "Fecha valor").
    vistos: set[str] = set()
    for c in celdas:
        if c.campo in vistos and c.campo != "otro":
            c.campo = "otro"
        vistos.add(c.campo)
    campos = {c.campo for c in celdas}
    utiles = [c for c in celdas if c.campo != "otro"]
    if "fecha" not in campos or not (campos & set(CAMPOS_MOVIMIENTO)) or len(utiles) < 3:
        return None
    return celdas


# ── Líneas repetidas (encabezado / pie de página) ───────────────────────────

def lineas_repetidas(doc: Documento) -> set[int]:
    """ids de las líneas que se repiten en la mayoría de las páginas, a la misma
    altura, arriba o abajo de la página (membrete, "Página N de M", pie legal).
    Los números cambian de página a página ("Hoja 2"), pero los importes cuentan
    con su valor: un transporte ("SALDO ANTERIOR 933.120,00") arriba de cada hoja
    trae un importe distinto en cada una y no es membrete."""
    if doc.paginas < 2:
        return set()
    conteo: dict[tuple[str, int], set[int]] = {}
    candidatas: list[tuple[Linea, tuple[str, int]]] = []
    for ln in doc.lineas:
        h = ln.altura_relativa
        if 0.2 < h < 0.7:
            continue
        if tiene_importe(ln) and fecha_al_inicio(ln)[0] is not None:
            continue
        partes = [t.texto if t.importe is not None else re.sub(r"\d", "", t.texto) for t in tokens(ln)]
        clave = (_normalizar(" ".join(partes).lower()).strip(), round(ln.y / 3))
        if not clave[0]:
            continue
        conteo.setdefault(clave, set()).add(ln.pagina)
        candidatas.append((ln, clave))
    minimo = max(2, math.ceil(doc.paginas * 0.5))
    return {id(ln) for ln, clave in candidatas if len(conteo[clave]) >= minimo}


# ── Layouts ─────────────────────────────────────────────────────────────────

def _bandas(columnas: list[tuple[str, float, float]], ancla: str, ancla_x0: Optional[float], tipo: str) -> dict:
    """columnas = [(campo, x_min_datos, x_max_datos)] en orden x → layout con
    bandas contiguas (límite = punto medio entre columnas vecinas)."""
    cols = sorted(columnas, key=lambda c: (c[1] + c[2]) / 2)
    out = []
    for i, (campo, x0, x1) in enumerate(cols):
        if i == 0:
            lo = 0.0
        else:
            _, px0, px1 = cols[i - 1]
            if px1 < x0:
                lo = (px1 + x0) / 2
            elif campo in CAMPOS_IMPORTE:
                lo = x0 - 0.5
            else:
                lo = max(px0 + 1, x0 - 2.0)
        out.append({"campo": campo, "lo": round(lo, 1), "hi": BANDA_MAX})
    for i in range(len(out) - 1):
        out[i]["hi"] = out[i + 1]["lo"]
    return {
        "version": 1,
        "tipo": tipo,
        "columnas": out,
        "ancla": ancla,
        "ancla_x0": round(ancla_x0, 1) if ancla_x0 is not None else None,
    }


def _distancia_alineacion(t: Token, c: Celda) -> float:
    return min(abs(t.x1 - c.x1), abs(t.cx - c.cx), abs(t.x0 - c.x0))


def _columnas_de_signo(celdas: list[Celda], datos: list[tuple[Linea, int]]) -> None:
    """Corrige el campo de las columnas según lo que tienen abajo. Una columna de
    importes cuyo título es "Débito" (o "Débito/", con el "Crédito" en el renglón
    de abajo) pero que debajo tiene solo "Débito"/"Crédito" es la del signo, si
    hay otra columna con los importes. Y al revés: una columna "signo" (por el
    título) que debajo tiene importes vuelve a ser la de los importes."""
    if not datos:
        return
    marcas = {id(c): 0 for c in celdas}
    importes = {id(c): 0 for c in celdas}
    for ln, nf in datos:
        margen = max(ln.size, 1.0)
        for t in tokens(ln)[nf:]:
            debajo = [c for c in celdas if c.x0 - margen <= t.cx <= c.x1 + margen]
            if not debajo:
                continue
            c = min(debajo, key=lambda c: abs(t.cx - c.cx))
            if t.importe is not None:
                importes[id(c)] += 1
            elif signo_de_texto(t.texto) is not None:
                marcas[id(c)] += 1
    n = len(datos)
    movimiento = [c for c in celdas if c.campo in CAMPOS_MOVIMIENTO]
    for c in celdas:
        solo_marcas = marcas[id(c)] >= max(2, 0.5 * n) and importes[id(c)] <= 0.1 * marcas[id(c)]
        if c.campo in CAMPOS_MOVIMIENTO and solo_marcas and any(o is not c for o in movimiento):
            c.campo = "signo"
        elif c.campo == "signo" and not marcas[id(c)] and importes[id(c)] >= max(1, 0.5 * n):
            c.campo = "importe"
            for o in celdas:
                if o is not c and o.campo == "importe":
                    o.campo = "otro"


def _layout_desde_encabezado(doc: Documento, encabezados: list[Linea], celdas: list[Celda]) -> dict:
    """Ajusta las bandas del encabezado con la posición real de los datos."""
    celdas = sorted(celdas, key=lambda c: c.x0)
    fecha = next(c for c in celdas if c.campo == "fecha")
    # Filas de datos: debajo del primer encabezado, empiezan con fecha y tienen importes.
    ids_enc = {id(ln) for ln in encabezados}
    en_tabla = False
    datos: list[tuple[Linea, int]] = []
    for ln in doc.lineas:
        if id(ln) in ids_enc:
            en_tabla = True
            continue
        if not en_tabla:
            continue
        toks = tokens(ln)
        f, nf = fecha_al_inicio(ln)
        if f is None or toks[0].x0 > fecha.x1 + 3 * ln.size:
            continue
        if not any(t.importe is not None for t in toks[nf:]):
            continue
        datos.append((ln, nf))
    _columnas_de_signo(celdas, datos)
    numericas = [c for c in celdas if c.campo in CAMPOS_IMPORTE]
    textos = [c for c in celdas if c.campo not in CAMPOS_IMPORTE]
    # Cuánto puede correrse un importe respecto de su título (títulos centrados o
    # alineados distinto que los números): ~45% de la distancia al título vecino.
    tolerancia: dict[int, float] = {}
    for i, c in enumerate(celdas):
        vecinos = [abs(c.cx - o.cx) for j, o in enumerate(celdas) if j != i]
        tolerancia[id(c)] = max(25.0, 0.45 * min(vecinos)) if vecinos else 50.0

    extension: dict[int, list[float]] = {id(c): [c.x0, c.x1] for c in celdas}

    def extender(c: Celda, t: Token) -> None:
        ext = extension[id(c)]
        ext[0] = min(ext[0], t.x0)
        ext[1] = max(ext[1], t.x1)

    textuales: list[Token] = []
    tamanos: list[float] = []
    for ln, _ in datos:
        toks = tokens(ln)
        tamanos.append(ln.size)
        for t in toks:
            if t.importe is not None and numericas:
                c = min(numericas, key=lambda c: _distancia_alineacion(t, c))
                if _distancia_alineacion(t, c) <= tolerancia[id(c)]:
                    extender(c, t)
                    continue
            textuales.append(t)
    if textos and textuales:
        size = sorted(tamanos)[len(tamanos) // 2] or 9.0
        limites = _limites_entre_textos(textos, textuales, size)
        for t in textuales:
            extender(textos[sum(1 for lim in limites if lim <= t.cx)], t)
    columnas = [(c.campo, *extension[id(c)]) for c in celdas]
    enc = encabezados[0]
    return _bandas(columnas, texto_ancla(enc), enc.x0, "encabezado")


def _limites_entre_textos(textos: list[Celda], tokens_datos: list[Token], size: float) -> list[float]:
    """Límite entre cada par de columnas de texto vecinas: el "pasillo" vacío más
    ancho (franja donde ningún dato tiene letras) entre el comienzo del título de
    la izquierda y el centro del título de la derecha. Funciona con títulos
    alineados a la izquierda o centrados sobre la columna. Sin pasillo (textos que
    se pisan), el límite es el comienzo del título de la derecha."""
    intervalos = sorted((t.x0, t.x1) for t in tokens_datos)
    segmentos: list[list[float]] = []
    for a, b in intervalos:
        if segmentos and a - segmentos[-1][1] < 0.5 * size:
            segmentos[-1][1] = max(segmentos[-1][1], b)
        else:
            segmentos.append([a, b])
    pasillos = [(segmentos[i][1], segmentos[i + 1][0]) for i in range(len(segmentos) - 1)]
    limites: list[float] = []
    for izq, der in zip(textos, textos[1:]):
        desde = max(izq.x0, limites[-1] if limites else izq.x0)
        hasta = der.cx
        mejor: Optional[tuple[float, float]] = None
        for p0, p1 in pasillos:
            a, b = max(p0, desde), min(p1, hasta)
            if b - a > 0 and (mejor is None or b - a > mejor[0]):
                mejor = (b - a, (a + b) / 2)
        limites.append(mejor[1] if mejor else max(desde, der.x0 - 0.5 * size))
    return limites


def layouts_por_encabezado(doc: Documento, max_candidatos: int = 3) -> list[dict]:
    """Un layout por cada texto de encabezado distinto encontrado (en orden de aparición)."""
    grupos: dict[str, tuple[list[Linea], list[Celda]]] = {}
    for ln in doc.lineas:
        celdas = celdas_encabezado(ln)
        if not celdas:
            continue
        clave = texto_ancla(ln)
        if clave in grupos:
            grupos[clave][0].append(ln)
        elif len(grupos) < max_candidatos:
            grupos[clave] = ([ln], celdas)
    return [_layout_desde_encabezado(doc, lineas, celdas) for lineas, celdas in grupos.values()]


def _agrupar(valores: list[tuple[float, object]], tol: float) -> list[list[tuple[float, object]]]:
    valores = sorted(valores, key=lambda v: v[0])
    grupos: list[list[tuple[float, object]]] = []
    for v in valores:
        if grupos and v[0] - grupos[-1][-1][0] <= tol:
            grupos[-1].append(v)
        else:
            grupos.append([v])
    return grupos


def ancla_sobre(doc: Documento, linea: Linea) -> tuple[str, Optional[float]]:
    """Texto de la línea "título" inmediatamente arriba de `linea` (misma página)."""
    previa: Optional[Linea] = None
    for ln in doc.lineas:
        if ln is linea:
            break
        if ln.pagina == linea.pagina:
            previa = ln if (not tiene_importe(ln) and len(texto_ancla(ln).split()) >= 2) else previa
    if previa is None or previa.y - linea.y > 6 * max(linea.size, 6.0):
        return "", None
    return texto_ancla(previa), previa.x0


def layouts_estructurales(doc: Documento, repetidas: set[int]) -> list[dict]:
    """Layouts sin encabezado: líneas que empiezan con fecha + importes alineados."""
    filas: list[tuple[Linea, int]] = []
    for ln in doc.lineas:
        if id(ln) in repetidas:
            continue
        f, nf = fecha_al_inicio(ln)
        if f is None or ln.palabras[0].x0 > 0.45 * ln.ancho_pagina:
            continue
        toks = tokens(ln)
        if any(t.importe is not None for t in toks[nf:]):
            filas.append((ln, nf))
    if not filas:
        return []
    tamanos = sorted(ln.size for ln, _ in filas)
    size = tamanos[len(tamanos) // 2] or 9.0
    puntos: list[tuple[float, object]] = []
    for idx, (ln, nf) in enumerate(filas):
        for t in tokens(ln)[nf:]:
            if t.importe is not None:
                puntos.append((t.x1, (idx, t)))
    grupos = _agrupar(puntos, max(3.0, 0.6 * size))
    n = len(filas)
    minimo = max(1, math.ceil(0.2 * n)) if n >= 5 else 1
    clusters = []
    for g in grupos:
        lineas_g = {item[1][0] for item in g}
        if len(lineas_g) < minimo:
            continue
        toks_g = [item[1][1] for item in g]
        clusters.append({
            "lineas": lineas_g,
            "x0": min(t.x0 for t in toks_g),
            "x1": max(t.x1 for t in toks_g),
        })
    if not clusters:
        return []
    clusters = clusters[-3:]
    # Columna con la palabra "Débito"/"Crédito" (o D/C) justo antes de los importes,
    # alineada en la mayoría de las filas: dice el signo del importe.
    marcas: list[tuple[float, object]] = []
    for idx, (ln, nf) in enumerate(filas):
        resto = tokens(ln)[nf:]
        k = next((k for k, t in enumerate(resto) if t.importe is not None), None)
        if k and resto[k - 1].importe is None and signo_de_texto(resto[k - 1].texto) is not None:
            marcas.append((resto[k - 1].cx, (idx, resto[k - 1])))
    signo: list[tuple[str, float, float]] = []
    de_signo: set[int] = set()
    if marcas:
        grupo = max(_agrupar(marcas, max(3.0, size)), key=len)
        if len({item[1][0] for item in grupo}) >= max(2, math.ceil(0.5 * n)):
            toks_s = [item[1][1] for item in grupo]
            signo = [("signo", min(t.x0 for t in toks_s), max(t.x1 for t in toks_s))]
            de_signo = {id(t) for t in toks_s}
    fecha_x1 = max(tokens(ln)[nf - 1].x1 for ln, nf in filas)
    texto_x0 = [
        tokens(ln)[nf].x0 for ln, nf in filas
        if len(tokens(ln)) > nf and tokens(ln)[nf].importe is None and id(tokens(ln)[nf]) not in de_signo
    ]
    texto_x1 = [
        t.x1 for ln, nf in filas for t in tokens(ln)[nf:]
        if t.importe is None and t.x0 < clusters[0]["x0"] and id(t) not in de_signo
    ]
    desc_x0 = min(texto_x0) if texto_x0 else fecha_x1 + size
    desc_x1 = max(texto_x1) if texto_x1 else desc_x0 + size
    base = [("fecha", min(ln.palabras[0].x0 for ln, _ in filas), fecha_x1), ("descripcion", desc_x0, desc_x1),
            *signo]
    if len(clusters) == 1:
        variantes = [["importe"]]
    elif len(clusters) == 2:
        ambos = clusters[0]["lineas"] & clusters[1]["lineas"]
        variantes = [["importe", "saldo"]] if ambos else [["debito", "credito"], ["credito", "debito"]]
    else:
        variantes = [["debito", "credito", "saldo"], ["credito", "debito", "saldo"]]
    ancla, ancla_x0 = ancla_sobre(doc, filas[0][0])
    out = []
    for campos in variantes:
        cols = base + [(campo, c["x0"], c["x1"]) for campo, c in zip(campos, clusters)]
        out.append(_bandas(cols, ancla, ancla_x0, "estructural"))
    return out


# ── Lectura con un layout ───────────────────────────────────────────────────

_INICIAL = ("saldo anterior", "saldo inicial", "saldo al inicio", "saldo de apertura", "saldo inicio",
            "saldo del periodo anterior", "saldo ultimo resumen", "saldo ultimo extracto", "saldo resumen anterior")
_FINAL = ("saldo final", "saldo actual", "saldo de cierre", "saldo al cierre", "nuevo saldo", "saldo a la fecha",
          "saldo total", "saldo final del periodo")
_TRANSPORTE = ("transporte", "a transportar", "de transporte", "saldo transportado", "viene de", "vienen de",
               "pasa a", "pasan a", "subtotal", "sub total", "sub-total", "saldo a transportar")
_PALABRAS_TOTAL = {"de", "del", "los", "las", "en", "el", "la", "debitos", "creditos", "debito", "credito",
                   "movimientos", "periodo", "dia", "general", "mes", "pesos", "impuestos", "importes"}


def _especial(texto: str, fechada: bool, con_movimiento: bool) -> Optional[str]:
    """Líneas que no son movimientos: saldo_inicial | saldo_final | saldo (ambiguo,
    "Saldo al 30/09") | omitir (transporte, subtotal, saldo promedio…) | total | None.

    Una línea con fecha e importe en una columna de movimiento que empieza con
    "SALDO …" o "TOTAL …" sigue siendo un movimiento salvo que sea un rótulo
    claro ("SALDO DEUDOR INTERESES" y "TOTAL DISTRIBUIDORA SA" son movimientos)."""
    if not texto:
        return None
    if texto.startswith(_TRANSPORTE):
        return "omitir"
    if texto.startswith(_INICIAL):
        return "saldo_inicial"
    if texto.startswith(_FINAL):
        return "saldo_final"
    palabras = texto.split()
    movimiento = fechada and con_movimiento
    if palabras[0] == "saldo":
        if len(palabras) == 1 or palabras[1] in ("al", "a", "en", "del", "de"):
            return "saldo"
        return None if movimiento else "omitir"     # saldo promedio, saldo disponible, ...
    if palabras[0] in ("total", "totales"):
        if not movimiento or all(p in _PALABRAS_TOTAL for p in palabras[1:]):
            return "total"
    # "Débitos del período", "Créditos del mes": totales sin la palabra "total".
    if (
        all(p in _PALABRAS_TOTAL for p in palabras)
        and set(palabras) & {"debitos", "creditos", "debito", "credito"}
        and (not movimiento or set(palabras) & {"periodo", "mes"})
    ):
        return "total"
    return None


def _pares_rotulo_importe(toks: list[Token]) -> list[tuple[list[Token], list[Token]]]:
    """Agrupa una línea en (rótulo, importes que lo siguen): "Saldo anterior $ 1.000,00
    Total créditos $ 500,00" → [(Saldo anterior, [1.000,00]), (Total créditos, [500,00])]."""
    pares: list[tuple[list[Token], list[Token]]] = []
    for t in toks:
        if t.importe is None:
            if not pares or pares[-1][1]:
                pares.append(([t], []))
            else:
                pares[-1][0].append(t)
        elif pares:
            pares[-1][1].append(t)
        else:
            pares.append(([], [t]))
    return pares


@dataclass
class _Fila:
    fecha: Optional[date]
    fecha_parcial: Optional[FechaParcial]
    descripcion: list[str]
    referencia: list[str]
    debito: Optional[Decimal]
    credito: Optional[Decimal]
    importe: Optional[Decimal]
    importe_negativo: bool
    saldo: Optional[Decimal]
    pagina: int
    y: float
    motivos: list[str]
    heredada: bool = False             # sin fecha propia: tomó la de la fila anterior
    signo: Optional[int] = None        # −1/+1 si el PDF dice "Débito"/"Crédito" (o D/C)


@dataclass
class _Pendiente:
    """Renglón con fecha y sin importe: puede ser el primer renglón de una fila
    cuyo importe viene en el renglón de abajo."""
    parcial: FechaParcial
    fecha: Optional[date]
    descripcion: list[str]
    y: float


@dataclass
class LecturaTabla:
    filas: list[dict]
    saldo_inicial: Optional[Decimal]
    saldo_final: Optional[Decimal]
    orden: str
    signo: str                         # columnas | explicito | saldo | desconocido
    paginas_con_ancla: int
    filas_por_linea: list[int]         # id(Linea) de cada fila (para inducir/diagnosticar)
    filas_sin_anio: int = 0            # filas cuya fecha venía sin año en el PDF
    otras_cuentas: bool = False        # el PDF seguía con otra cuenta: se leyó solo la primera
    # Páginas con renglones de la tabla que tienen fecha y números ilegibles en las
    # columnas de importes (un movimiento que no se pudo leer): uno por renglón.
    renglones_ilegibles: list[int] = field(default_factory=list)


class _Bandas:
    def __init__(self, layout: dict):
        cols = layout.get("columnas") or []
        self.cols = [(float(c["lo"]), float(c["hi"]), str(c["campo"])) for c in cols]
        self.campos = {c[2] for c in self.cols}

    def campo(self, x: float, dx: float) -> Optional[str]:
        for lo, hi, campo in self.cols:
            lo_ = lo + dx if lo > 0 else -BANDA_MAX
            hi_ = hi + dx if hi < BANDA_MAX else BANDA_MAX * 10
            if lo_ <= x < hi_:
                return campo
        return None


def _abs(v: Optional[Decimal]) -> Optional[Decimal]:
    return abs(v) if v is not None else None


def _paso_entre_filas(doc: Documento, repetidas: set[int]) -> Optional[float]:
    """Mediana de la distancia vertical entre líneas seguidas (misma página) que
    empiezan con fecha y traen importe: el alto típico de una fila de la tabla."""
    por_pagina: dict[int, list[float]] = {}
    for ln in doc.lineas:
        if id(ln) not in repetidas and tiene_importe(ln) and fecha_al_inicio(ln)[0] is not None:
            por_pagina.setdefault(ln.pagina, []).append(ln.y)
    pasos = sorted(a - b for ys in por_pagina.values() for a, b in zip(ys, ys[1:]) if a - b > 0)
    if len(pasos) < 2:
        return None
    return pasos[len(pasos) // 2]


def _umbral_vecino(size: float, paso: Optional[float]) -> float:
    """Distancia vertical máxima para que un renglón pertenezca a la fila de arriba
    (continuación de la descripción, o importe sin fecha del mismo día). Con
    filas de un renglón no puede superar mucho el alto de una fila: así el título
    de un cuadro al pie de la tabla no se pega a la última descripción."""
    base = 2.6 * max(size, 6.0)
    if paso is None:
        return base
    return min(base, max(1.35 * paso, 1.1 * max(size, 6.0)))


def leer_con_layout(doc: Documento, layout: dict, ctx: ContextoFechas, repetidas: set[int]) -> LecturaTabla:
    bandas = _Bandas(layout)
    ancla = layout.get("ancla") or ""
    ancla_x0 = layout.get("ancla_x0")
    tiene_fecha = "fecha" in bandas.campos

    filas: list[_Fila] = []
    ids_linea: list[int] = []
    saldo_ini: Optional[Decimal] = None
    saldos_fin: list[tuple[int, Decimal]] = []
    ambiguos: list[tuple[int, Decimal, Optional[date]]] = []
    cortes: list[tuple[int, Decimal]] = []          # "Saldo anterior" en el medio de la tabla
    ilegibles: list[tuple[int, int]] = []           # (posición en filas, página)
    tabla_vista = False
    paginas_con_ancla = 0
    dx = 0.0
    ultima_fecha: Optional[date] = None
    ultima_parcial: Optional[FechaParcial] = None
    paso = _paso_entre_filas(doc, repetidas)

    paginas = sorted({ln.pagina for ln in doc.lineas})
    por_pagina: dict[int, list[Linea]] = {}
    for ln in doc.lineas:
        por_pagina.setdefault(ln.pagina, []).append(ln)

    for pagina in paginas:
        lineas = por_pagina[pagina]
        anclas = {i for i, ln in enumerate(lineas) if ancla and texto_ancla(ln) == ancla}
        if anclas:
            paginas_con_ancla += 1
            estado = "antes"
        elif ancla and not tabla_vista:
            estado = "antes"
        else:
            estado = "continuacion"
        ultima_fila: Optional[_Fila] = None
        y_ultima = 0.0
        # Un renglón de texto que no es fila ni continuación (título de un cuadro,
        # leyenda) corta la tabla: los importes sin fecha que siguen no son del día.
        interrumpido = False
        pendiente: Optional[_Pendiente] = None
        for i, ln in enumerate(lineas):
            if i in anclas:
                estado = "tabla"
                tabla_vista = True
                if ancla_x0 is not None and abs(ln.x0 - float(ancla_x0)) <= 60:
                    dx = ln.x0 - float(ancla_x0)
                ultima_fila = None
                interrumpido = False
                pendiente = None
                continue
            if id(ln) in repetidas:
                continue
            toks = tokens(ln)
            umbral = _umbral_vecino(ln.size, paso)
            por_campo: dict[str, list[Token]] = {}
            previo: Optional[tuple[Token, str]] = None
            basura_numerica = False
            marca_signo: Optional[int] = None
            for t in toks:
                campo = bandas.campo(t.cx, dx)
                if campo is None:
                    continue
                if (
                    t.importe is None
                    and previo is not None
                    and previo[1] == "descripcion"
                    and campo != "descripcion"
                    and (campo == "otro" or campo in CAMPOS_IMPORTE)
                    and t.x0 - previo[0].x1 <= 0.8 * max(previo[0].size, 1.0)
                ):
                    campo = "descripcion"           # descripción larga que se pasa de su columna
                if campo in CAMPOS_IMPORTE and t.importe is None:
                    if campo == "importe" and marca_signo is None:
                        marca_signo = signo_de_texto(t.texto)    # "1.234,56 D" en la columna Importe
                    basura_numerica = basura_numerica or any(ch.isdigit() for ch in t.texto)
                    continue                        # "$", "D", "C", basura en columnas numéricas
                if campo in CAMPOS_TEXTO and t.importe is not None and campo == "fecha":
                    continue
                por_campo.setdefault(campo, []).append(t)
                previo = (t, campo)
            texto_fecha = " ".join(t.texto for t in por_campo.get("fecha", []))
            parcial = None
            if tiene_fecha and texto_fecha:
                partes = texto_fecha.split()
                for n in (3, 2, 1):
                    if len(partes) >= n:
                        parcial = parsear_fecha(" ".join(partes[:n]))
                        if parcial:
                            break
            de_signo = {id(t) for t in por_campo.get("signo", [])}
            for t in por_campo.get("signo", []):
                s_ = signo_de_texto(t.texto)
                if s_ is not None:
                    marca_signo = s_
                    break
            textos = [
                t.texto for t in toks if t.importe is None and id(t) not in de_signo and not parsear_fecha(t.texto)
            ]
            importes_mov = [t for c in CAMPOS_MOVIMIENTO for t in por_campo.get(c, []) if t.importe is not None]
            especial = _especial(texto_normalizado(" ".join(textos)), parcial is not None, bool(importes_mov))
            if especial == "saldo" and importes_mov:
                especial = None        # "02/09 SALDO A FAVOR AFIP 1.000,00" es un movimiento

            if especial is not None:
                pares = [(r, imps) for r, imps in _pares_rotulo_importe(toks) if r and imps]
                if len(pares) >= 2:
                    # Cuadro de resumen con dos rótulos por renglón ("Saldo anterior $ X
                    # Total créditos $ Y"): cada importe va con el rótulo que lo precede.
                    items = []
                    for rotulo, imps in pares:
                        textos_r = [t.texto for t in rotulo]
                        fecha_r = next((f for f in map(parsear_fecha, textos_r) if f), None)
                        esp = _especial(texto_normalizado(" ".join(textos_r)), False, False)
                        items.append((esp, imps[-1].importe, fecha_r))
                else:
                    valores = por_campo.get("saldo") or [t for t in toks if t.importe is not None]
                    items = [(especial, valores[-1].importe, parcial)] if valores else []
                    if not valores and especial in ("saldo_inicial", "saldo_final", "saldo"):
                        items = [(especial, None, parcial)]
                for esp, v, fecha_item in items:
                    if v is None:
                        continue
                    if esp == "saldo_inicial":
                        if saldo_ini is None:
                            saldo_ini = v
                        elif filas:
                            cortes.append((len(filas), v))
                    elif esp == "saldo_final":
                        saldos_fin.append((len(filas), v))
                    elif esp == "saldo":
                        ambiguos.append((len(filas), v, ctx.resolver(fecha_item)))
                tipos = {esp for esp, _, _ in items} | {especial}
                if tipos & {"saldo_final", "total"} and estado == "tabla":
                    estado = "fin"
                if especial in ("saldo_inicial", "saldo_final", "saldo"):
                    ultima_fila = None
                    pendiente = None
                continue
            if estado == "antes":
                continue

            if importes_mov:
                if parcial is None and (estado == "fin" or not tabla_vista):
                    continue
                fecha = ctx.resolver(parcial) if parcial else None
                motivos: list[str] = []
                prefijo: list[str] = []
                heredada = False
                if parcial is None:
                    if pendiente is not None and pendiente.y - ln.y <= umbral:
                        # Fila de dos renglones: la fecha venía en el renglón de arriba.
                        parcial, fecha, prefijo = pendiente.parcial, pendiente.fecha, pendiente.descripcion
                        if fecha is None:
                            motivos.append(MOTIVO_SIN_FECHA)
                    elif (ultima_fila is not None and y_ultima - ln.y <= umbral) or (
                        ultima_fila is None and not interrumpido
                    ):
                        heredada = True
                        if ultima_fecha is not None or ultima_parcial is not None:
                            fecha, parcial = ultima_fecha, ultima_parcial
                        else:
                            motivos.append(MOTIVO_SIN_FECHA)
                    else:
                        # Importe suelto lejos de la tabla (pie legal, cuadro de
                        # retenciones, totales): no es un movimiento.
                        interrumpido = True
                        continue
                elif fecha is None:
                    motivos.append(MOTIVO_SIN_FECHA)
                valores: dict[str, Optional[Decimal]] = {}
                for c in CAMPOS_IMPORTE:
                    lista = [t for t in por_campo.get(c, []) if t.importe is not None]
                    if len(lista) > 1:
                        motivos.append(MOTIVO_VARIOS)
                    valores[c] = lista[-1].importe if lista else None
                imp_tok = [t for t in por_campo.get("importe", []) if t.importe is not None]
                fila = _Fila(
                    fecha=fecha,
                    fecha_parcial=parcial,
                    descripcion=prefijo + [t.texto for t in por_campo.get("descripcion", [])],
                    referencia=[t.texto for t in por_campo.get("referencia", [])],
                    debito=valores["debito"],
                    credito=valores["credito"],
                    importe=valores["importe"],
                    importe_negativo=bool(imp_tok and imp_tok[-1].negativo),
                    saldo=valores["saldo"],
                    pagina=ln.pagina,
                    y=ln.y,
                    motivos=list(dict.fromkeys(motivos)),
                    heredada=heredada,
                    signo=marca_signo,
                )
                filas.append(fila)
                ids_linea.append(id(ln))
                if fecha is not None or parcial is not None:
                    ultima_fecha, ultima_parcial = fecha, parcial
                ultima_fila, y_ultima = fila, ln.y
                interrumpido = False
                pendiente = None
                estado = "tabla"
                tabla_vista = True
                continue

            extra = [t.texto for c in ("descripcion", "referencia") for t in por_campo.get(c, [])]
            if parcial is not None and tabla_vista and estado in ("tabla", "continuacion") and basura_numerica:
                # Fecha + números que no son importes en las columnas de importes
                # (columnas pegadas, formato raro): un movimiento que no se pudo leer.
                ilegibles.append((len(filas), ln.pagina))
                ultima_fila = None
                pendiente = None
                continue
            if parcial is not None and tabla_vista and estado in ("tabla", "continuacion"):
                # Renglón con fecha y sin importe: el importe puede venir abajo.
                pendiente = _Pendiente(parcial, ctx.resolver(parcial), extra, ln.y)
                ultima_fila = None
                continue
            if pendiente is not None and parcial is None and extra and pendiente.y - ln.y <= umbral:
                pendiente.descripcion.extend(extra)
                pendiente.y = ln.y
                continue
            # Renglón de continuación de la descripción.
            if estado == "tabla" and ultima_fila is not None and parcial is None and extra:
                if y_ultima - ln.y <= umbral:
                    ultima_fila.descripcion.extend(extra)
                    y_ultima = ln.y
                    continue
            if estado == "tabla":
                ultima_fila = None
                interrumpido = True
                pendiente = None

    orden = detectar_orden([f.fecha for f in filas])
    # Al final de una tabla ascendente con saldos, la última fila siempre trae el
    # saldo (por fila o por día): importes sin fecha ni saldo después de ella son
    # de un cuadro al pie (retenciones, totales), no movimientos.
    if orden == "asc" and "saldo" in bandas.campos and sum(1 for f in filas if f.saldo is not None) >= 2:
        while filas and filas[-1].heredada and filas[-1].saldo is None:
            filas.pop()
            ids_linea.pop()
    signo, montos = _resolver_signos(filas, bandas.campos, orden, saldo_ini)

    # Otra cuenta en el mismo PDF (cuenta corriente + caja de ahorro): un "Saldo
    # anterior" en el medio que no sigue el saldo corrido. Se lee solo la primera.
    corte = _corte_de_seccion(filas, montos, cortes)
    if corte is not None:
        ilegibles = [(p, pag) for p, pag in ilegibles if p <= corte]
        filas, montos, ids_linea = filas[:corte], montos[:corte], ids_linea[:corte]
        saldos_fin = [(p, v) for p, v in saldos_fin if p <= corte]
        ambiguos = [(p, v, f) for p, v, f in ambiguos if p <= corte]

    # Saldos ambiguos ("Saldo al 30/09"): por fecha y, si no, por posición.
    fechas = [f.fecha for f in filas if f.fecha]
    ambiguos_ini: list[Decimal] = []
    ambiguos_fin: list[Decimal] = []
    for pos, v, f in ambiguos:
        if f is not None and fechas:
            if f < min(fechas) or (f == min(fechas) and f < max(fechas)):
                ambiguos_ini.append(v)
                continue
            if f >= max(fechas):
                ambiguos_fin.append(v)
                continue
        if pos == 0 and filas:
            ambiguos_ini.append(v)
        elif pos >= len(filas):
            ambiguos_fin.append(v)
    if saldo_ini is None and ambiguos_ini:
        saldo_ini = ambiguos_ini[0]
    saldo_fin = saldos_fin[-1][1] if saldos_fin else (ambiguos_fin[-1] if ambiguos_fin else None)

    salida: list[dict] = []
    ids_finales: list[int] = []
    sin_anio = 0
    for f, monto, id_ln in zip(filas, montos, ids_linea):
        if monto is None or monto == 0:
            continue
        if f.fecha_parcial is not None and f.fecha_parcial[2] is None:
            sin_anio += 1
        desc = " ".join(f.descripcion + f.referencia).strip()
        motivos = list(f.motivos)
        if ctx.periodo and f.fecha is not None:
            desde, hasta = ctx.periodo
            if f.fecha < desde - timedelta(days=7) or f.fecha > hasta + timedelta(days=7):
                motivos.append(MOTIVO_FUERA_PERIODO)
        salida.append({
            "fecha": f.fecha,
            "descripcion": re.sub(r"\s+", " ", desc),
            "monto": monto,
            "saldo": f.saldo,
            "pagina": f.pagina,
            "dudosa": bool(motivos),
            "motivos": list(dict.fromkeys(motivos)),
        })
        ids_finales.append(id_ln)
    if not salida:
        orden = "asc"
    else:
        orden = detectar_orden([m["fecha"] for m in salida], [m["monto"] for m in salida],
                               [m["saldo"] for m in salida], saldo_ini, preferido=orden)
    return LecturaTabla(salida, saldo_ini, saldo_fin, orden, signo, paginas_con_ancla, ids_finales, sin_anio,
                        corte is not None, [pag for _, pag in ilegibles])


def _saldos_en_el_limite(filas: list[_Fila], montos: list[Optional[Decimal]], pos: int) -> list[Decimal]:
    """Saldos que puede repetir un transporte entre filas[pos-1] y filas[pos], en
    orden ascendente o descendente, deducidos del saldo conocido más cercano más
    los montos del medio (con saldo diario, las filas del límite pueden no traerlo).
    En orden ascendente solo se mira hacia atrás: "el saldo antes de filas[pos]"
    deducido de las filas de abajo también es el saldo anterior de otra cuenta."""
    out: list[Decimal] = []
    acum = CERO
    for k in range(pos - 1, -1, -1):
        if filas[k].saldo is not None:
            out.append(filas[k].saldo + acum)                    # asc: después de filas[pos-1]
            if montos[k] is not None:
                out.append(filas[k].saldo - acum - montos[k])    # desc: después de filas[pos]
            break
        if montos[k] is None:
            break
        acum += montos[k]
    acum = CERO
    for j in range(pos, len(filas)):
        if filas[j].saldo is not None:
            out.append(filas[j].saldo + acum)                    # desc: después de filas[pos]
            break
        if montos[j] is None:
            break
        acum += montos[j]
    return out


def _corte_de_seccion(
    filas: list[_Fila], montos: list[Optional[Decimal]], cortes: list[tuple[int, Decimal]]
) -> Optional[int]:
    """Posición donde empieza otra cuenta: un "Saldo anterior" en el medio de la
    tabla que no es un transporte de página. Un transporte repite el saldo que
    había en ese punto de la tabla; el comienzo de otra cuenta no."""
    for pos, valor in cortes:
        if not 0 < pos < len(filas):
            continue
        vecinos = _saldos_en_el_limite(filas, montos, pos)
        if vecinos and all(abs(valor - v) > TOL for v in vecinos):
            return pos
    return None


# ── Orden y signo ───────────────────────────────────────────────────────────

def _saltos(montos: list[Decimal], saldos: list[Optional[Decimal]], previo: Optional[Decimal]) -> int:
    n = 0
    for m, s in zip(montos, saldos):
        if s is not None:
            if previo is not None and abs(previo + m - s) > TOL:
                n += 1
            previo = s
        elif previo is not None:
            previo += m
    return n


def detectar_orden(
    fechas: list[Optional[date]],
    montos: Optional[list[Decimal]] = None,
    saldos: Optional[list[Optional[Decimal]]] = None,
    saldo_inicial: Optional[Decimal] = None,
    preferido: str = "asc",
) -> str:
    """"asc" (más viejo primero) o "desc". Por fechas; si empatan, por el saldo corrido."""
    validas = [f for f in fechas if f is not None]
    sube = sum(1 for a, b in zip(validas, validas[1:]) if b > a)
    baja = sum(1 for a, b in zip(validas, validas[1:]) if b < a)
    if sube != baja:
        return "asc" if sube > baja else "desc"
    if montos and saldos and any(s is not None for s in saldos):
        asc = _saltos(montos, saldos, saldo_inicial)
        desc = _saltos(list(reversed(montos)), list(reversed(saldos)), saldo_inicial)
        if asc != desc:
            return "asc" if asc < desc else "desc"
    return preferido


def _resolver_signos(
    filas: list[_Fila], campos: set[str], orden: str, saldo_inicial: Optional[Decimal]
) -> tuple[str, list[Optional[Decimal]]]:
    """Monto con signo de cada fila (crédito +, débito −)."""
    if campos & {"debito", "credito"}:
        montos: list[Optional[Decimal]] = []
        for f in filas:
            cred = _abs(f.credito) or CERO
            deb = _abs(f.debito) or CERO
            if cred and deb:
                f.motivos.append(MOTIVO_DOBLE)
            if not cred and not deb and f.importe is not None:
                montos.append(f.importe)
                continue
            montos.append(cred - deb)
        return "columnas", montos
    if any(f.signo is not None for f in filas if f.importe is not None):
        # Columna "Débito/Crédito" (o D/C junto al importe): el signo lo dice el PDF.
        # Las filas que no lo traen salen del signo explícito o del saldo.
        faltan = [f.signo is None and f.importe is not None for f in filas]
        if not any(faltan):
            return "explicito", [f.signo * abs(f.importe) if f.importe is not None else None for f in filas]
        explicitos = any(f.importe_negativo for f in filas)
        copias = [replace(f, motivos=list(f.motivos)) for f in filas]
        deducidos = None if explicitos else _signos_por_saldo(copias, orden, saldo_inicial)
        montos = []
        for i, f in enumerate(filas):
            if f.importe is None:
                montos.append(None)
            elif f.signo is not None:
                montos.append(f.signo * abs(f.importe))
            elif deducidos is None:
                montos.append(f.importe)
            else:
                montos.append(deducidos[i])
                f.motivos[:] = copias[i].motivos
        return ("explicito" if explicitos else "saldo"), montos
    if any(f.importe_negativo for f in filas):
        return "explicito", [f.importe for f in filas]
    if not any(f.saldo is not None for f in filas):
        for f in filas:
            f.motivos.append(MOTIVO_SIGNO)
        return "desconocido", [f.importe for f in filas]
    return "saldo", _signos_por_saldo(filas, orden, saldo_inicial)


MAX_FILAS_SIN_SALDO = 24


def _signos_unicos(valores: list[Decimal], objetivo: Decimal) -> Optional[tuple[int, ...]]:
    """La ÚNICA combinación de signos (+1/−1) con Σ signo·valor = objetivo, o None
    si no hay ninguna o hay más de una. En centavos y por "encuentro a mitad de
    camino" (2 × 2^12 sumas para 24 filas), así un día con muchos movimientos y
    un solo saldo al final se resuelve en milisegundos."""
    n = len(valores)
    if n == 0 or n > MAX_FILAS_SIN_SALDO:
        return None
    cent = [int(v * 100) for v in valores]
    meta = int(objetivo * 100)
    mitad = n // 2

    def sumas(parte: list[int]) -> dict[int, list[tuple[int, ...]]]:
        out: dict[int, list[tuple[int, ...]]] = {}
        for signos in product((1, -1), repeat=len(parte)):
            total = sum(s * v for s, v in zip(signos, parte))
            lista = out.setdefault(total, [])
            if len(lista) < 2:
                lista.append(signos)
        return out

    izquierda = sumas(cent[:mitad])
    derecha = sumas(cent[mitad:])
    hallada: Optional[tuple[int, ...]] = None
    for total, combos_der in derecha.items():
        for falta in (meta - total - 1, meta - total, meta - total + 1):    # tolerancia de 1 centavo
            combos_izq = izquierda.get(falta)
            if not combos_izq:
                continue
            if len(combos_izq) > 1 or len(combos_der) > 1 or hallada is not None:
                return None
            hallada = combos_izq[0] + combos_der[0]
    return hallada


def _signos_por_saldo(filas: list[_Fila], orden: str, saldo_inicial: Optional[Decimal]) -> list[Optional[Decimal]]:
    """Importes sin signo: el signo sale de cómo se mueve el saldo. Si varias filas
    seguidas no traen saldo, se busca la única combinación de signos que llega al
    saldo siguiente (hasta `MAX_FILAS_SIN_SALDO` filas)."""
    n = len(filas)
    idx = list(range(n)) if orden != "desc" else list(range(n - 1, -1, -1))
    montos: list[Optional[Decimal]] = [None] * n
    previo = saldo_inicial
    pendientes: list[int] = []
    for i in idx:
        f = filas[i]
        a = _abs(f.importe)
        if a is None:
            continue
        pendientes.append(i)
        if f.saldo is None:
            continue
        if previo is None:
            # Primera fila sin saldo inicial conocido: no hay contra qué comparar.
            for j in pendientes:
                montos[j] = _abs(filas[j].importe)
                filas[j].motivos.append(MOTIVO_SIGNO)
        else:
            valores = [_abs(filas[j].importe) or CERO for j in pendientes]
            objetivo = f.saldo - previo
            signos = _signos_unicos(valores, objetivo)
            if signos is not None:
                for j, s in zip(pendientes, signos):
                    montos[j] = s * (_abs(filas[j].importe) or CERO)
            else:
                for j in pendientes:
                    v = _abs(filas[j].importe) or CERO
                    montos[j] = v if objetivo >= 0 else -v
                    filas[j].motivos.append(MOTIVO_SIGNO)
        previo = f.saldo
        pendientes = []
    for j in pendientes:  # filas finales sin saldo posterior
        montos[j] = _abs(filas[j].importe)
        filas[j].motivos.append(MOTIVO_SIGNO)
    return montos
