"""Moldes: formatos de extracto aprendidos por organización.

Un molde es un `layout` de `tabla.py` (bandas de columnas + ancla) más una
`firma` que permite reconocer el formato en el próximo PDF sin leerlo entero:

    firma = sha256("v1|<banco_clave>|<texto normalizado del ancla>")

El ancla es la fila de títulos de la tabla (o, si no hay títulos reconocibles,
la línea de arriba de la primera fila). Se normaliza sin dígitos ni acentos, así
"Hoja 3" o el período no cambian la firma. El banco entra en la firma para que
dos bancos con los mismos títulos ("Fecha Descripción Débito Crédito Saldo") no
se pisen el molde dentro de la misma organización.

Si el banco cambia el diseño del PDF, la firma igual coincide pero la lectura no
cierra: el lector cae a la lectura automática y, al confirmar, el molde se
reemplaza por el nuevo (lo decide el servicio).
"""

from __future__ import annotations

import hashlib
from collections import Counter
from datetime import date
from decimal import Decimal
from statistics import median
from typing import Optional, Sequence

from .fechas import FechaParcial, parsear_fecha
from .tabla import (
    CAMPOS_IMPORTE,
    CAMPOS_TEXTO,
    Token,
    _bandas,
    ancla_sobre,
    tiene_importe,
    texto_ancla,
    tokens,
)
from .texto import Documento, Linea

VERSION_LAYOUT = 1
_CAMPOS_VALIDOS = set(CAMPOS_IMPORTE) | set(CAMPOS_TEXTO)


def firma(ancla: str, banco_clave: Optional[str]) -> str:
    return hashlib.sha256(f"v1|{banco_clave or 'generico'}|{ancla}".encode("utf-8")).hexdigest()


def firmas_del_documento(doc: Documento, banco_clave: Optional[str]) -> set[str]:
    """Firmas de todas las líneas que podrían ser un ancla (texto, sin importes)."""
    textos = {
        texto_ancla(ln)
        for ln in doc.lineas
        if len(texto_ancla(ln).split()) >= 2 and not tiene_importe(ln)
    }
    return {firma(t, banco_clave) for t in textos}


def layout_valido(layout) -> bool:
    """Chequeo defensivo de un layout que viene de la base (JSON)."""
    if not isinstance(layout, dict) or layout.get("version") != VERSION_LAYOUT:
        return False
    cols = layout.get("columnas")
    if not isinstance(cols, list) or not cols or len(cols) > 20:
        return False
    campos = set()
    for c in cols:
        if not isinstance(c, dict) or c.get("campo") not in _CAMPOS_VALIDOS:
            return False
        try:
            lo, hi = float(c["lo"]), float(c["hi"])
        except (KeyError, TypeError, ValueError):
            return False
        if hi <= lo:
            return False
        campos.add(c["campo"])
    if not campos & {"debito", "credito", "importe"}:
        return False
    return isinstance(layout.get("ancla"), str) and bool(layout["ancla"].strip())


def aprendizaje_de(layout: dict, banco_clave: str) -> Optional[dict]:
    """Candidato a molde (JSON-safe) o None si el layout no tiene ancla."""
    if not layout_valido(layout):
        return None
    return {"firma": firma(layout["ancla"], banco_clave), "banco_clave": banco_clave, "layout": layout}


# ── Inducir un layout a partir de filas ya leídas (por la IA) ──────────────

def _misma_fecha(p: FechaParcial, f: date) -> bool:
    return p[0] == f.day and p[1] == f.month and (p[2] is None or p[2] == f.year)


def _fechas_de_linea(ln: Linea) -> list[tuple[FechaParcial, Token, Token]]:
    toks = tokens(ln)
    out = []
    for i, t in enumerate(toks):
        if t.importe is not None:
            continue
        for n in (3, 2, 1):
            if i + n <= len(toks):
                p = parsear_fecha(" ".join(x.texto for x in toks[i:i + n]))
                if p:
                    out.append((p, toks[i], toks[i + n - 1]))
                    break
    return out


def inducir_layout(doc: Documento, filas: Sequence[dict], repetidas: set[int]) -> Optional[dict]:
    """Arma un layout ubicando en el PDF las filas que leyó la IA (fecha + importe
    + saldo en una misma línea). Devuelve None si no se ubican al menos el 80%."""
    filas = [f for f in filas if f.get("monto") is not None]
    if len(filas) < 2:
        return None
    lineas = [ln for ln in doc.lineas if id(ln) not in repetidas and tiene_importe(ln)]
    info = [(ln, _fechas_de_linea(ln), [t for t in tokens(ln) if t.importe is not None]) for ln in lineas]
    usadas: set[int] = set()
    encontrados = []
    puntero = 0

    def buscar(fila: dict, desde: int, hasta: int, con_saldo: bool):
        fecha: Optional[date] = fila.get("fecha")
        monto = abs(Decimal(fila["monto"]))
        saldo = fila.get("saldo")
        for k in range(desde, hasta):
            if k in usadas:
                continue
            ln, fechas, importes = info[k]
            f_tok = None
            if fecha is not None:
                f_tok = next(((a, b) for p, a, b in fechas if _misma_fecha(p, fecha)), None)
                if f_tok is None:
                    continue
            cand_monto = [t for t in importes if abs(t.importe) == monto]
            if not cand_monto:
                continue
            s_tok = None
            if con_saldo:
                if saldo is None:
                    continue
                cand_saldo = [t for t in importes if t.importe == Decimal(saldo)]
                if not cand_saldo:
                    continue
                s_tok = cand_saldo[-1]
                otros = [t for t in cand_monto if t is not s_tok]
                if not otros:
                    continue
                cand_monto = otros
            return k, f_tok, cand_monto[0], s_tok
        return None

    for fila in filas:
        hallado = None
        for con_saldo in ((True, False) if fila.get("saldo") is not None else (False,)):
            hallado = buscar(fila, puntero, len(info), con_saldo) or buscar(fila, 0, puntero, con_saldo)
            if hallado:
                break
        if not hallado:
            continue
        k, f_tok, m_tok, s_tok = hallado
        usadas.add(k)
        puntero = k + 1
        encontrados.append((fila, info[k][0], f_tok, m_tok, s_tok))

    if len(encontrados) < max(2, 0.8 * len(filas)):
        return None

    columnas: list[tuple[str, float, float]] = []
    fechas_tok = [f for _, _, f, _, _ in encontrados if f is not None]
    if fechas_tok:
        columnas.append(("fecha", min(a.x0 for a, _ in fechas_tok), max(b.x1 for _, b in fechas_tok)))
    creditos = [m for fila, _, _, m, _ in encontrados if Decimal(fila["monto"]) > 0]
    debitos = [m for fila, _, _, m, _ in encontrados if Decimal(fila["monto"]) < 0]
    separadas = False
    if creditos and debitos:
        ancho = median([t.x1 - t.x0 for t in creditos + debitos])
        separadas = (
            max(t.x1 for t in creditos) < min(t.x0 for t in debitos)
            or max(t.x1 for t in debitos) < min(t.x0 for t in creditos)
            or abs(median([t.cx for t in creditos]) - median([t.cx for t in debitos])) > 0.6 * ancho
        )
    if separadas:
        columnas.append(("credito", min(t.x0 for t in creditos), max(t.x1 for t in creditos)))
        columnas.append(("debito", min(t.x0 for t in debitos), max(t.x1 for t in debitos)))
    else:
        todos = creditos + debitos
        columnas.append(("importe", min(t.x0 for t in todos), max(t.x1 for t in todos)))
    saldos = [s for *_, s in encontrados if s is not None]
    if len(saldos) >= 0.5 * len(encontrados):
        columnas.append(("saldo", min(t.x0 for t in saldos), max(t.x1 for t in saldos)))
    if not fechas_tok:
        return None

    # Descripción: lo que queda entre la fecha y la primera columna de importes.
    fecha_x1 = columnas[0][2]
    primer_importe = min(c[1] for c in columnas if c[0] in CAMPOS_IMPORTE)
    textos = [
        t for _, ln, _, _, _ in encontrados for t in tokens(ln)
        if t.importe is None and t.x0 > fecha_x1 and t.x1 < primer_importe and not parsear_fecha(t.texto)
    ]
    if textos:
        columnas.append(("descripcion", min(t.x0 for t in textos), max(t.x1 for t in textos)))
    else:
        columnas.append(("descripcion", fecha_x1 + 1, max(fecha_x1 + 2, primer_importe - 1)))

    posicion = {id(ln): i for i, ln in enumerate(doc.lineas)}
    primera = min((ln for _, ln, _, _, _ in encontrados), key=lambda ln: posicion[id(ln)])
    ancla, ancla_x0 = ancla_sobre(doc, primera)
    if not ancla:
        return None
    return _bandas(columnas, ancla, ancla_x0, "ia")


def mismas_filas(a: Sequence[dict], b: Sequence[dict]) -> bool:
    """True si ambas lecturas tienen las mismas filas (fecha, monto), sin importar el orden."""
    def clave(filas):
        return Counter((f.get("fecha"), Decimal(f["monto"]) if f.get("monto") is not None else None) for f in filas)
    return len(a) == len(b) and clave(a) == clave(b)
