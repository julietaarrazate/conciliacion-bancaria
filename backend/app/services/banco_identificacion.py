"""Reconocer de qué banco es un extracto (Excel/CSV o PDF). Una sola fuente.

Antes el banco salía solo del nombre escrito en las primeras filas
(`excel_parser.detectar_banco_filas`) o en el membrete del PDF
(`extracto_pdf.bancos`): un archivo que no nombra a su banco quedaba "genérico".
Ahora se combinan varias señales, de la más fuerte a la más débil:

1. **CBU/CVU de la cuenta** (encabezado del archivo, primeras hojas del PDF,
   propiedades del Excel y nombre del archivo). Se valida con sus dos dígitos
   verificadores (algoritmo del BCRA) y los 3 primeros dígitos son el código de
   entidad del BCRA (`BANCOS_POR_CODIGO`). Un CVU (empieza con 000) es una
   billetera; el de Mercado Pago empieza con 0000003.
2. **CUIT del banco** si aparece en el encabezado (`CUIT_BANCOS`).
3. **Formato del archivo**: títulos de columnas y conceptos típicos de cada banco.
4. **Confirmado antes**: el banco que la persona eligió para ese formato
   (plantilla de Excel o molde de PDF de su organización).
5. **Nombre** del banco en el encabezado o en el nombre del archivo (lo de
   siempre): la señal más débil; nunca le gana a un CBU válido.

Un banco que la persona **confirmó** para ese formato le gana a todo (es su
cuenta: si eligió otro banco es porque el CBU del encabezado era de otra cuenta);
si alguna señal automática dice otra cosa, se avisa en `conflicto`.
Entre señales automáticas que no coinciden gana la más fuerte (el CBU) y también
se avisa.

Solo se miran las zonas de encabezado: las descripciones de los movimientos
nombran a OTROS bancos y traen CBU/CUIT de terceros ("TRANSF. DESDE CBU …").

Puro: no toca la base. La firma de plantillas y moldes NO usa este resultado
(sigue con el nombre, `detectar_banco_filas` / `extracto_pdf.bancos`) para que
los formatos ya guardados sigan reconociéndose.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Iterable, Optional

GENERICO = "generico"

# ── Código de entidad del BCRA → banco ───────────────────────────────────────
#
# Fuente: BCRA, Comunicación "A" 8367 (12/12/2025), "Listado de Entidades
# Financieras. Grupo A y B" — https://www.bcra.gob.ar/archivos/Pdfs/comytexord/A8367.pdf
# (verificado el 30/10/2026). En el CBU van los 3 primeros dígitos (código con
# ceros a la izquierda: Galicia 7 → "007"). Las compañías financieras con código de
# 5 dígitos (44xxx/45xxx) no tienen CBU de 3 dígitos propio y no van acá.
#
# Excepción: HSBC (150) no figura en el listado de 2025 (lo compró Galicia en 2024 y
# se fusionó); el código sale de la Com. "A" 6538 (2018) —
# https://www.bcra.gob.ar/archivos/Pdfs/comytexord/A6538.pdf — y se deja para
# los extractos viejos de esas cuentas. NO VERIFICADO en el listado vigente.
#
# (clave interna, nombre visible). Las claves de los 16 bancos que ya reconocía el
# parser se mantienen iguales (macro, bbva, …) para no cambiar lo guardado.
BANCOS_POR_CODIGO: dict[str, tuple[str, str]] = {
    "007": ("galicia", "Galicia"),
    "011": ("nacion", "Banco Nación"),
    "014": ("provincia", "Bapro"),
    "015": ("icbc", "ICBC"),
    "016": ("citi", "Citibank"),
    "017": ("bbva", "BBVA"),
    "020": ("bancor", "Bancor"),
    "027": ("supervielle", "Supervielle"),
    "029": ("ciudad", "Banco Ciudad"),
    "034": ("patagonia", "Patagonia"),
    "044": ("hipotecario", "Banco Hipotecario"),
    "045": ("sanjuan", "Banco San Juan"),
    "065": ("municipalrosario", "Banco Municipal de Rosario"),
    "072": ("santander", "Santander"),
    "083": ("chubut", "Banco del Chubut"),
    "086": ("santacruz", "Banco Santa Cruz"),
    "093": ("lapampa", "Banco La Pampa"),
    "094": ("corrientes", "Banco de Corrientes"),
    "097": ("neuquen", "Banco Provincia del Neuquén"),
    "131": ("bankofchina", "Bank of China"),
    "143": ("brubank", "Brubank"),
    "147": ("bibank", "Bibank"),
    "150": ("hsbc", "HSBC"),                      # histórico, ver arriba
    "165": ("jpmorgan", "JPMorgan"),
    "191": ("credicoop", "Credicoop"),
    "198": ("valores", "Banco de Valores"),
    "247": ("roela", "Banco Roela"),
    "254": ("mariva", "Banco Mariva"),
    "266": ("bnp", "BNP Paribas"),
    "268": ("tierradelfuego", "Banco de Tierra del Fuego"),
    "269": ("republicauruguay", "Banco República Oriental del Uruguay"),
    "277": ("saenz", "Banco Saenz"),
    "281": ("meridian", "Banco Meridian"),
    "285": ("macro", "Banco Macro"),
    "299": ("comafi", "Banco Comafi"),
    "300": ("bice", "BICE"),
    "301": ("piano", "Banco Piano"),
    "305": ("julio", "Banco Julio"),
    "309": ("rioja", "Banco Rioja"),
    "310": ("bancodelsol", "Banco del Sol"),
    "311": ("chaco", "Nuevo Banco del Chaco"),
    "312": ("voii", "Banco Voii"),
    "315": ("formosa", "Banco de Formosa"),
    "319": ("cmf", "Banco CMF"),
    "321": ("santiago", "Banco de Santiago del Estero"),
    "322": ("bind", "Banco Industrial (BIND)"),
    "330": ("santafe", "Nuevo Banco de Santa Fe"),
    "331": ("cetelem", "Banco Cetelem"),
    "332": ("bsf", "Banco de Servicios Financieros"),
    "338": ("bst", "Banco de Servicios y Transacciones"),
    "339": ("rci", "RCI Banque"),
    "340": ("bacs", "BACS"),
    "341": ("masventas", "Banco Masventas"),
    "384": ("uala", "Ualá Bank"),
    "386": ("entrerios", "Nuevo Banco de Entre Ríos"),
    "389": ("columbia", "Banco Columbia"),
    "426": ("bica", "Banco Bica"),
    "431": ("coinag", "Banco Coinag"),
    "432": ("comercio", "Banco de Comercio"),
    "435": ("sucredito", "Banco Sucrédito Regional"),
    "448": ("dino", "Banco Dino"),
}

# CVU de billeteras (código de PSP en los dígitos 4-7). Mercado Pago: sus CVU
# empiezan con 0000003. Fuentes (no del BCRA, que no publica la tabla de PSP):
# https://ikiwi.net.ar/medios-de-pago/transferencias-bancarias/cvu/ y
# https://hacecuentas.com/calculadora-validar-cbu-cvu-identificar-banco (coinciden).
CVU_PREFIJOS: dict[str, tuple[str, str]] = {
    "0000003": ("mercadopago", "Mercado Pago"),
}

# CUIT de los bancos. Fuente: BCRA, "Transportadoras de caudales"
# (https://www.bcra.gob.ar/transportadoras-de-caudales/, consultado el 30/10/2026),
# que lista razón social y CUIT; todos pasan el dígito verificador. Solo se cargan
# los que se pudieron verificar ahí (falta, p. ej., Credicoop, ICBC, Supervielle,
# Ciudad, Patagonia, HSBC, Bancor, La Pampa, Mercado Pago).
CUIT_BANCOS: dict[str, str] = {
    "30500010084": "macro",
    "30500001735": "galicia",
    "30500010912": "nacion",
    "33999242109": "provincia",
    "30500003193": "bbva",
    "30500008454": "santander",
    "30671859339": "rioja",
    "30500009442": "sanjuan",
    "30500010602": "corrientes",
    "30500098801": "santacruz",
    "30500012990": "chubut",
    "30500014047": "neuquen",
    "30692432661": "santafe",
    "30671375900": "formosa",
}

# Nombres visibles de las claves (las de la tabla + Mercado Pago).
NOMBRES: dict[str, str] = {clave: nombre for clave, nombre in BANCOS_POR_CODIGO.values()}
NOMBRES.update({clave: nombre for clave, nombre in CVU_PREFIJOS.values()})

# Nombres de los bancos que NO están en `excel_parser.INDICADORES_BANCO`. Se miran
# acá y no allá: la firma de plantillas/moldes usa ese diccionario, y sumarle
# palabras cambiaría la firma de formatos ya guardados.
NOMBRES_EXTRA: dict[str, list[str]] = {
    "brubank": ["brubank"],
    "comafi": ["banco comafi"],
    "hipotecario": ["banco hipotecario"],
    "bind": ["banco industrial", "bind banco industrial"],
    "citi": ["citibank"],
    "sanjuan": ["banco de san juan", "banco san juan"],
    "santafe": ["nuevo banco de santa fe"],
    "entrerios": ["nuevo banco de entre rios"],
    "uala": ["uala bank", "uala"],
    "chubut": ["banco del chubut"],
    "neuquen": ["banco provincia del neuquen"],
    "corrientes": ["banco de corrientes"],
    "santacruz": ["banco de santa cruz"],
    "tierradelfuego": ["banco de tierra del fuego", "banco provincia de tierra del fuego"],
    "municipalrosario": ["banco municipal de rosario"],
    "formosa": ["banco de formosa"],
    "santiago": ["banco de santiago del estero"],
    "chaco": ["nuevo banco del chaco"],
}

CONFIANZA = {
    "confirmado": 0.97,
    "cbu": 0.95,
    "cuit": 0.9,
    "aprendido": 0.75,
    "estructura": 0.65,
    "nombre": 0.55,
}
# Debajo de esto la pantalla pide que la persona elija el banco.
CONFIANZA_MINIMA = 0.6

MOTIVOS = {
    "confirmado": "confirmado antes",
    "cbu": "por el CBU de la cuenta",
    "cvu": "por el CVU de la cuenta",
    "cuit": "por el CUIT del banco",
    "aprendido": "por un archivo igual que ya subiste",
    "estructura": "por el formato del archivo",
    "nombre": "por el nombre en el encabezado",
    "nombre_archivo": "por el nombre del archivo",
}


def _sin_acentos(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def nombre_de(clave: Optional[str]) -> Optional[str]:
    """Nombre visible de una clave (None si es genérico/desconocida)."""
    from app.services.extracto_import import nombre_banco
    return nombre_banco(clave)


def lista_bancos() -> list[dict]:
    """Bancos para el desplegable de la pantalla (ordenados por nombre)."""
    from app.services.excel_parser import INDICADORES_BANCO
    claves = set(NOMBRES) | set(INDICADORES_BANCO)
    out = [{"clave": c, "nombre": nombre_de(c) or c} for c in claves]
    return sorted(out, key=lambda b: _sin_acentos(b["nombre"]).lower())


def clave_valida(clave: Optional[str]) -> bool:
    if not clave:
        return False
    from app.services.excel_parser import INDICADORES_BANCO
    return clave == GENERICO or clave in NOMBRES or clave in INDICADORES_BANCO


# ── CBU / CVU ────────────────────────────────────────────────────────────────

_PESOS_BLOQUE1 = (7, 1, 3, 9, 7, 1, 3)
_PESOS_BLOQUE2 = (3, 9, 7, 1, 3, 9, 7, 1, 3, 9, 7, 1, 3)


def _digito(digitos: str, pesos: tuple) -> int:
    suma = sum(int(d) * p for d, p in zip(digitos, pesos))
    return (10 - suma % 10) % 10


def cbu_valido(cbu: str) -> bool:
    """22 dígitos con sus dos verificadores bien (algoritmo del BCRA):
    bloque 1 = entidad (3) + sucursal (4) + verificador; bloque 2 = cuenta (13) +
    verificador. Vale igual para un CVU."""
    s = re.sub(r"\D", "", cbu or "")
    if len(s) != 22 or s == "0" * 22:
        return False
    return _digito(s[:7], _PESOS_BLOQUE1) == int(s[7]) and _digito(s[8:21], _PESOS_BLOQUE2) == int(s[21])


def banco_de_cbu(cbu: str) -> Optional[tuple[str, str, str]]:
    """(clave, nombre, "cbu"|"cvu") del CBU/CVU válido, o None si no es válido o
    la entidad no está en la tabla."""
    s = re.sub(r"\D", "", cbu or "")
    if not cbu_valido(s):
        return None
    if s.startswith("000"):
        for prefijo, (clave, nombre) in CVU_PREFIJOS.items():
            if s.startswith(prefijo):
                return clave, nombre, "cvu"
        return None
    dato = BANCOS_POR_CODIGO.get(s[:3])
    return (dato[0], dato[1], "cbu") if dato else None


# 22 dígitos seguidos, o en grupos separados por un espacio, guión o punto
# ("0170 0999 2000 0012 3456 78", "285-0590-9…"). Sin dígitos pegados a los lados.
_RE_CBU = re.compile(r"(?<![\d])(\d(?:[ \-.]?\d){21})(?![\d])")
_RE_CUIT = re.compile(r"(?<!\d)(\d{2})[- .]?(\d{8})[- .]?(\d)(?!\d)")


def buscar_cbus(texto: str) -> list[str]:
    """CBU/CVU válidos (22 dígitos, verificadores bien) que aparecen en el texto."""
    out = []
    for m in _RE_CBU.finditer(texto or ""):
        s = re.sub(r"\D", "", m.group(1))
        if len(s) == 22 and cbu_valido(s) and s not in out:
            out.append(s)
    return out


def cuit_valido(cuit: str) -> bool:
    d = re.sub(r"\D", "", cuit or "")
    if len(d) != 11:
        return False
    pesos = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)
    v = 11 - sum(int(a) * b for a, b in zip(d[:10], pesos)) % 11
    v = 0 if v == 11 else v
    return v == int(d[10])


def buscar_cuits_banco(texto: str) -> list[str]:
    """Claves de banco cuyo CUIT aparece en el texto."""
    out = []
    for m in _RE_CUIT.finditer(texto or ""):
        d = "".join(m.groups())
        clave = CUIT_BANCOS.get(d)
        if clave and cuit_valido(d) and clave not in out:
            out.append(clave)
    return out


# ── Formato del archivo (huella estructural) ─────────────────────────────────
#
# Solo lo que se sabe de verdad de cada banco (lo que ya usaban el parser y los
# tests). Para sumar un banco: un conjunto de títulos de columna y/o una regex de
# concepto que solo use ese banco.

# Títulos de columna normalizados (minúsculas, sin acentos): todos tienen que estar.
ENCABEZADOS_TIPICOS: dict[str, list[set[str]]] = {
    # "Extracto conciliado" de Banco Macro: Orden, Fecha, Mes, Titular, Importe/Monto, Saldo.
    "macro": [{"orden", "fecha", "mes", "titular", "importe", "saldo"},
              {"orden", "fecha", "mes", "titular", "monto", "saldo"}],
}
# Conceptos típicos (sobre la descripción de los movimientos, ya en mayúsculas).
CONCEPTOS_TIPICOS: dict[str, re.Pattern] = {
    "macro": re.compile(r"\bING\.?\s*TRANSF\s*:"),
}
MIN_CONCEPTOS = 2


def _norm(v) -> str:
    return re.sub(r"\s+", " ", _sin_acentos(str(v or "")).lower()).strip()


def banco_por_estructura(encabezados: Iterable = (), conceptos: Iterable[str] = (),
                         filas_cabecera: Optional[list[list]] = None) -> Optional[str]:
    """Banco por títulos de columna, conceptos típicos o (Mercado Pago) las
    columnas del reporte de liberaciones. None si no se reconoce."""
    titulos = {_norm(v) for v in encabezados if _norm(v)}
    if titulos:
        for clave, conjuntos in ENCABEZADOS_TIPICOS.items():
            if any(c <= titulos for c in conjuntos):
                return clave
    if filas_cabecera:
        from app.services.excel_parser import _es_mercadopago_por_headers
        if _es_mercadopago_por_headers(filas_cabecera):
            return "mercadopago"
    conteo: dict[str, int] = {}
    for c in conceptos:
        t = _sin_acentos(str(c or "")).upper()
        for clave, rx in CONCEPTOS_TIPICOS.items():
            if rx.search(t):
                conteo[clave] = conteo.get(clave, 0) + 1
    mejores = [k for k, n in conteo.items() if n >= MIN_CONCEPTOS]
    return mejores[0] if len(mejores) == 1 else None


def banco_por_nombre_extra(texto: str) -> Optional[str]:
    """Bancos que no están en el detector por nombre de siempre."""
    t = _norm(texto)
    if not t:
        return None
    pares = sorted(((c, k) for c, ks in NOMBRES_EXTRA.items() for k in ks), key=lambda p: -len(p[1]))
    for clave, kw in pares:
        if re.search(r"\b" + re.escape(kw) + r"\b", t):
            return clave
    return None


def eleccion_confirmada(deteccion: Optional[dict], detectado: Optional[str], elegido: Optional[str]) -> bool:
    """La persona decidió el banco en la pantalla: lo cambió, o el sistema no
    estaba seguro y ella lo eligió/aceptó. Solo eso se recuerda como "confirmado
    antes" (aceptar un banco que salió por el CBU no enseña nada)."""
    if not elegido or elegido == GENERICO:
        return False
    return elegido != detectado or bool((deteccion or {}).get("pedir_confirmacion", True))


# ── Identificación ───────────────────────────────────────────────────────────

def _resultado(clave: str, origen: str, motivo_clave: str, conflicto: Optional[str] = None) -> dict:
    confianza = CONFIANZA.get(origen, 0.0) if clave != GENERICO else 0.0
    if conflicto and origen not in ("confirmado",):
        confianza = min(confianza, 0.8)
    return {
        "banco_clave": clave,
        "nombre": nombre_de(clave),
        "confianza": round(confianza, 2),
        "motivo": MOTIVOS.get(motivo_clave, "") if clave != GENERICO
        else "no encontramos el banco en el archivo: elegilo de la lista",
        "origen": origen if clave != GENERICO else "ninguno",
        "conflicto": conflicto,
        "pedir_confirmacion": clave == GENERICO or confianza < CONFIANZA_MINIMA or bool(conflicto),
    }


def identificar_banco(
    *,
    textos_encabezado: Iterable[str] = (),
    nombre_archivo: Optional[str] = None,
    metadatos: Iterable[str] = (),
    por_nombre: Optional[str] = None,
    por_estructura: Optional[str] = None,
    aprendido: Optional[str] = None,
    aprendido_confirmado: bool = False,
) -> dict:
    """Banco del extracto con `{banco_clave, nombre, confianza, motivo, origen,
    conflicto, pedir_confirmacion}`.

    - `textos_encabezado`: textos de las zonas de encabezado (NO las descripciones
      de los movimientos): ahí se buscan CBU/CVU, CUIT y nombres extra.
    - `por_nombre`: lo que dijo el detector por nombre de siempre (o None).
    - `por_estructura`: `banco_por_estructura(...)` (o None).
    - `aprendido`: el banco guardado en la plantilla/molde que coincidió;
      `aprendido_confirmado` si lo eligió la persona."""
    encabezado = [str(t) for t in textos_encabezado if t]
    extra = [str(t) for t in metadatos if t]
    zonas = encabezado + extra + ([nombre_archivo] if nombre_archivo else [])

    # 1) CBU/CVU: el más repetido (si hay dos cuentas de bancos distintos, gana la
    # que más aparece; empate → la primera) y se avisa.
    por_cbu: list[tuple[str, str]] = []
    for z in zonas:
        for cbu in buscar_cbus(z):
            dato = banco_de_cbu(cbu)
            if dato:
                por_cbu.append((dato[0], dato[2]))
    cbu_clave = cbu_tipo = None
    if por_cbu:
        cuentas: dict[str, int] = {}
        for clave, _ in por_cbu:
            cuentas[clave] = cuentas.get(clave, 0) + 1
        cbu_clave = max(cuentas, key=lambda k: (cuentas[k], -[c for c, _ in por_cbu].index(k)))
        cbu_tipo = next(t for c, t in por_cbu if c == cbu_clave)
    # 2) CUIT del banco.
    cuits = [c for z in encabezado + extra for c in buscar_cuits_banco(z)]
    cuit_clave = max(set(cuits), key=cuits.count) if cuits else None
    # 5) Nombre: el de siempre, si no los bancos extra; por último el nombre del archivo.
    nombre_clave, nombre_motivo = None, "nombre"
    if por_nombre and por_nombre != GENERICO:
        nombre_clave = por_nombre
        # "Banco Industrial" (BIND) lo agarraba "industrial" de ICBC.
        if por_nombre == "icbc" and any(
            re.search(r"\bbanco industrial\b", _norm(t)) and "commercial" not in _norm(t) for t in encabezado
        ):
            nombre_clave = "bind"
    else:
        nombre_clave = banco_por_nombre_extra(" ".join(encabezado + extra))
    if not nombre_clave and nombre_archivo:
        from app.services.excel_parser import detectar_banco_filas
        base = re.sub(r"[_\-.]+", " ", nombre_archivo)
        nombre_clave = detectar_banco_filas([[base]])
        if nombre_clave == GENERICO:
            nombre_clave = banco_por_nombre_extra(base)
        nombre_motivo = "nombre_archivo"

    automaticas = [
        ("cbu", cbu_clave, "cvu" if cbu_tipo == "cvu" else "cbu"),
        ("cuit", cuit_clave, "cuit"),
        ("estructura", por_estructura if por_estructura != GENERICO else None, "estructura"),
        ("aprendido", aprendido if (aprendido and aprendido != GENERICO and not aprendido_confirmado) else None,
         "aprendido"),
        ("nombre", nombre_clave if nombre_clave != GENERICO else None, nombre_motivo),
    ]
    automaticas = [(o, c, m) for o, c, m in automaticas if c]

    def _conflicto(ganador: str, señales) -> Optional[str]:
        otras = []
        for o, c, m in señales:
            if c != ganador:
                n = nombre_de(c) or c
                if f"{n} ({MOTIVOS[m]})" not in otras:
                    otras.append(f"{n} ({MOTIVOS[m]})")
        if por_cbu and len({c for c, _ in por_cbu}) > 1:
            otros_cbu = sorted({nombre_de(c) or c for c, _ in por_cbu if c != ganador})
            for n in otros_cbu:
                txt = f"{n} (otro CBU en el encabezado)"
                if txt not in otras:
                    otras.append(txt)
        if not otras:
            return None
        return "El archivo también indica " + ", ".join(otras) + "."

    if aprendido_confirmado and aprendido and aprendido != GENERICO:
        return _resultado(aprendido, "confirmado", "confirmado", _conflicto(aprendido, automaticas))
    if not automaticas:
        return _resultado(GENERICO, "ninguno", "")
    origen, clave, motivo = automaticas[0]
    return _resultado(clave, origen, motivo, _conflicto(clave, automaticas[1:]))
