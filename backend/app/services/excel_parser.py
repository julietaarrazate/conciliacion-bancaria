"""
Parseo de archivos Excel para extractos bancarios y planillas de clientes.
Soporta .xlsx, .xls y .csv.
Soporta Banco Macro, BBVA, Santander, Galicia, ICBC y formatos genericos.
"""

import re
import os
import tempfile
from typing import Tuple
from datetime import date, datetime
import openpyxl


def _convertir_xls_a_xlsx(filepath: str) -> str:
    """Convierte .xls (formato viejo) a .xlsx para procesarlo con openpyxl."""
    import xlrd
    from openpyxl import Workbook

    xls = xlrd.open_workbook(filepath)
    wb = Workbook()
    wb.remove(wb.active)

    for sheet_name in xls.sheet_names():
        xls_sheet = xls.sheet_by_name(sheet_name)
        ws = wb.create_sheet(title=sheet_name)
        for row in range(xls_sheet.nrows):
            for col in range(xls_sheet.ncols):
                cell = xls_sheet.cell(row, col)
                val = cell.value
                if cell.ctype == xlrd.XL_CELL_DATE:
                    try:
                        val = datetime(*xlrd.xldate_as_tuple(val, xls.datemode))
                    except Exception:
                        pass
                ws.cell(row=row + 1, column=col + 1, value=val)

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
    wb.save(tmp.name)
    wb.close()
    xls.release_resources()
    return tmp.name


def _convertir_csv_a_xlsx(filepath: str) -> str:
    """Convierte .csv a .xlsx para procesarlo con openpyxl."""
    import csv
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active

    encodings = ['utf-8', 'latin-1', 'cp1252']
    for enc in encodings:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                content = f.read()
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    else:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()

    delimiter = detectar_delimitador(content)
    # Patrón para montos argentinos: "1.234,56" o "-1.234,56"
    _ARG_MONTO_RE = re.compile(r'^-?\d{1,3}(\.\d{3})*(,\d+)?$')

    def _normalizar_numero(s: str) -> str:
        """Convierte "1.234,56" → "1234.56"; deja otros strings intactos."""
        if _ARG_MONTO_RE.match(s):
            # Quitar punto separador de miles y cambiar coma decimal por punto
            return re.sub(r'\.(?=\d{3}([,\s]|$))', '', s).replace(',', '.')
        return s

    reader = csv.reader(content.splitlines(), delimiter=delimiter)
    for row_idx, row in enumerate(reader, 1):
        for col_idx, val in enumerate(row, 1):
            val = val.strip()
            try:
                ws.cell(row=row_idx, column=col_idx, value=float(_normalizar_numero(val)))
            except ValueError:
                ws.cell(row=row_idx, column=col_idx, value=val)

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
    wb.save(tmp.name)
    wb.close()
    return tmp.name


def detectar_delimitador(content: str) -> str:
    """Separador de un CSV/TXT: `;`, `,`, tabulador o `|`. Gana el que aparece
    la misma cantidad de veces (y al menos una) en más renglones de los primeros
    30 no vacíos; ante empate, el que más aparece. Por defecto `,`."""
    lineas = [ln for ln in content.splitlines() if ln.strip()][:30]
    mejor, mejor_puntaje = ',', (0, 0)
    for d in (';', '\t', ',', '|'):
        cuentas = [ln.count(d) for ln in lineas]
        con = [c for c in cuentas if c > 0]
        if not con:
            continue
        moda = max(set(con), key=con.count)
        puntaje = (con.count(moda), sum(con))
        if puntaje > mejor_puntaje:
            mejor, mejor_puntaje = d, puntaje
    return mejor


def preparar_archivo(filepath: str) -> Tuple[str, bool]:
    """
    Si el archivo es .xls o .csv, lo convierte a .xlsx.
    Retorna (ruta_xlsx, necesita_cleanup).
    """
    ext = os.path.splitext(filepath)[1].lower()
    if ext == '.xls':
        return _convertir_xls_a_xlsx(filepath), True
    if ext in ('.csv', '.tsv', '.txt'):
        return _convertir_csv_a_xlsx(filepath), True
    return filepath, False

INDICADORES_BANCO = {
    "macro":       ["macro", "banco macro"],
    "bbva":        ["bbva", "frances", "banco frances"],
    "santander":   ["santander", "rio", "santander rio"],
    "galicia":     ["galicia", "banco galicia"],
    "icbc":        ["icbc", "industrial"],
    "nacion":      ["nacion", "banco de la nacion"],
    "provincia":   ["provincia", "bapro"],
    "ciudad":      ["ciudad", "banco ciudad"],
    "hsbc":        ["hsbc"],
    # ── Bancos agregados (v3.13+): Mercado Pago + 6 bancos regionales ──────
    "mercadopago": ["mercado pago", "mercadopago", "mercado libre",
                    "mercadolibre", "money_release", "dineromp"],
    "credicoop":   ["credicoop", "banco credicoop"],
    "supervielle": ["supervielle", "banco supervielle"],
    "patagonia":   ["patagonia", "banco patagonia"],
    "bancor":      ["bancor", "banco de cordoba",
                    "banco de la provincia de cordoba"],
    "rioja":       ["banco rioja", "banco de la rioja",
                    "nuevo banco de la rioja"],
    "lapampa":     ["banco de la pampa", "bancodelapampa", "banco la pampa"],
}

def _kw_en_texto(keyword: str, texto: str) -> bool:
    """Matchea `keyword` como palabra/frase completa (con \\b), no como substring
    suelto — evita falsos positivos como "rio" adentro de "periodo", "anterior",
    "horario", "prioridad", etc."""
    return re.search(r'\b' + re.escape(keyword) + r'\b', texto) is not None

def detectar_banco(ws) -> str:
    """Banco de una hoja de openpyxl (ver `detectar_banco_filas`)."""
    filas = [
        [ws.cell(r, c).value for c in range(1, min(40, ws.max_column) + 1)]
        for r in range(1, min(10, ws.max_row) + 1)
    ]
    return detectar_banco_filas(filas)


def detectar_banco_filas(filas) -> str:
    """Banco a partir de las primeras filas de la planilla (lista de listas de
    valores). Lo usan el parser de Excel y el lector de extractos con mapeo."""
    texto = ""
    # Escanea más filas/columnas: algunos formatos (Credicoop, Supervielle,
    # Patagonia) ponen el nombre del banco recién en la fila 3-8.
    for fila in list(filas)[:9]:
        for v in list(fila)[:11]:
            if v:
                texto += " " + str(v).lower()
    texto = _normalizar(texto)
    # Matchear primero las keywords MÁS LARGAS/específicas para evitar que un
    # token corto y goloso (ej. "rio" de Santander) capture a otro banco
    # (ej. "Banco de La Rioja"). Se ordena (banco, keyword) por longitud desc.
    candidatos = []
    for banco, palabras in INDICADORES_BANCO.items():
        for p in palabras:
            candidatos.append((banco, _normalizar(p)))
    candidatos.sort(key=lambda bp: len(bp[1]), reverse=True)
    for banco, p in candidatos:
        if _kw_en_texto(p, texto):
            return banco
    # Mercado Pago por estructura: el CSV de liberaciones no siempre
    # contiene el texto "Mercado Pago", pero sí columnas características.
    if _es_mercadopago_por_headers(filas):
        return "mercadopago"
    return "generico"


def _es_mercadopago_por_headers(filas) -> bool:
    """True si la planilla tiene 2+ cabeceras típicas del reporte MP."""
    hits = set()
    for fila in list(filas)[:5]:
        for v in list(fila)[:39]:
            if not v:
                continue
            h = _normalizar(str(v).lower().strip())
            for kw in KEYWORDS_MP_HEADER:
                if kw in h:
                    hits.add(kw)
        if len(hits) >= 2:
            return True
    return len(hits) >= 2

def _parse_fecha(v):
    if v is None:
        return None
    if isinstance(v, (date, datetime)):
        return v.date() if isinstance(v, datetime) else v
    s = str(v).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None

def _parse_monto(v):
    # Devuelve float; la conversión a Decimal la hace SQLAlchemy en columnas Numeric(12,2).
    if isinstance(v, (int, float)):
        return round(float(v), 2)
    if isinstance(v, str):
        s = v.strip().replace("$","").replace("\xa0","").replace(" ","")
        if not s or s in ("-",""):
            return None
        if "," in s and "." in s:
            if s.rfind(",") > s.rfind("."):
                s = s.replace(".","").replace(",",".")
            else:
                s = s.replace(",","")
        elif "," in s:
            s = s.replace(",",".")
        try:
            return round(float(s), 2)
        except ValueError:
            return None
    return None

KEYWORDS_MONTO   = ["importe","monto","amount","transaction_amount","net_amount"]
KEYWORDS_CREDITO = ["credito","haber","credit"]
KEYWORDS_DEBITO  = ["debito","debe","debit","cargo"]
KEYWORDS_FECHA   = ["fecha","date","vencimiento","release_date","date_created","money_release_date"]
KEYWORDS_TITULAR = ["titular","concepto","descripcion","glosa","detalle","nombre","beneficiario","ordenante",
                    "transaction_type","payer_name","description","tipo de transferencia","tipo de movimiento"]
KEYWORDS_ORDEN   = ["orden","nro. de referencia","nro","numero","secuencia","referencia",
                    "operation_id","source_id","external_reference","payment_id"]
KEYWORDS_SALDO   = ["saldo","balance","balance_amount"]
KEYWORDS_MES     = ["mes","period","periodo"]
KEYWORDS_CUIT    = ["cuit","cuil","cdi"]

# Cabeceras características del CSV de liberaciones/settlement de Mercado Pago.
# Si aparecen 2+ de estas, es un reporte MP aunque no diga "Mercado Pago".
KEYWORDS_MP_HEADER = ["transaction_amount", "transaction_type", "balance_amount",
                      "source_id", "release_date", "money_release_date",
                      "external_reference", "payment_method_type"]
KEYWORDS_CLIENTE_ACRED = ["cliente acreditado", "cliente acredit"]
KEYWORDS_FECHA_ACRED   = ["fecha acred", "fecha de acred"]

# Bloquear "cliente" / "acred" como TITULAR (no confundir con concepto),
# pero seguir permitiendolos como columnas propias de cliente_acred/fecha_acred.
BLOCKLIST = {"acred", "acreditad", "cliente"}

def _normalizar(s: str) -> str:
    """Quita acentos y diacríticos para que 'Débitos' matchee 'debito'."""
    import unicodedata
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')

def _match_kw(header, keywords):
    h = _normalizar(header.lower().strip())
    if any(b in h for b in BLOCKLIST):
        return False
    return any(k in h for k in keywords)

def _match_kw_raw(header, keywords):
    h = _normalizar(header.lower().strip())
    return any(k in h for k in keywords)

def _fila_valida_como_header(ws, row, encontrados):
    """Confirma que la fila candidata a header tenga datos reales en la fila
    siguiente (no sea una línea de resumen tipo "Total débitos: $X" que matchea
    keywords por casualidad pero no es una fila de encabezado de tabla)."""
    nxt = row + 1
    if nxt > ws.max_row:
        return False
    # Columnas numéricas (monto/credito/debito/saldo): alcanza con que UNA tenga
    # un valor real en la fila siguiente — en formatos con crédito/débito
    # separados, cada fila solo llena una de las dos columnas.
    numericas = [c for campo, c in encontrados.items() if campo in ("monto", "credito", "debito", "saldo")]
    if numericas:
        if not any(
            (v := ws.cell(nxt, c).value) is not None and not (isinstance(v, str) and _parse_monto(v) is None)
            for c in numericas
        ):
            return False
    if "fecha" in encontrados:
        v = ws.cell(nxt, encontrados["fecha"]).value
        if v is None or _parse_fecha(v) is None:
            return False
    if "indicador_dc" in encontrados:
        v = ws.cell(nxt, encontrados["indicador_dc"]).value
        if not v or not str(v).strip():
            return False
    return True

# Encabezados cortos de la columna que dice si la fila es débito o crédito.
ENCABEZADOS_INDICADOR = {"d/c", "db/cr", "deb/cred", "d-c", "dc", "debe/haber", "tipo d/c", "signo"}


def rol_por_encabezado(header) -> "str | None":
    """Rol de una columna según el texto de su encabezado (por palabras clave).

    Devuelve una de: cliente_acred, fecha_acred, indicador_dc, monto, credito,
    debito, fecha, cuit, titular, orden, saldo, mes — o None. Única fuente de la
    detección por palabras: la usan `detectar_columnas` y el lector de extractos
    con mapeo (`extracto_mapper`)."""
    h = str(header or "").lower().strip()
    if not h:
        return None
    # Cliente acreditado / Fecha acred (columnas propias del extracto exportado)
    if _match_kw_raw(h, KEYWORDS_CLIENTE_ACRED):
        return "cliente_acred"
    if _match_kw_raw(h, KEYWORDS_FECHA_ACRED):
        return "fecha_acred"
    h_norm = _normalizar(h)
    # Columna indicadora de texto "Débito/Crédito" por fila (no son dos
    # columnas de monto separadas, sino una sola columna clasificadora
    # que acompaña a una columna "Monto" única siempre positiva).
    if ("debito" in h_norm and "credito" in h_norm) or h_norm in ENCABEZADOS_INDICADOR:
        return "indicador_dc"
    if _match_kw(h, KEYWORDS_MONTO):
        return "monto"
    if _match_kw(h, KEYWORDS_CREDITO):
        return "credito"
    if _match_kw(h, KEYWORDS_DEBITO):
        return "debito"
    if _match_kw(h, KEYWORDS_FECHA):
        return "fecha"
    if _match_kw_raw(h, KEYWORDS_CUIT):
        return "cuit"
    if _match_kw(h, KEYWORDS_TITULAR):
        return "titular"
    if _match_kw(h, KEYWORDS_ORDEN):
        return "orden"
    if _match_kw(h, KEYWORDS_SALDO):
        return "saldo"
    if _match_kw(h, KEYWORDS_MES):
        return "mes"
    return None


def detectar_columnas(ws):
    """Columnas de un extracto por palabras clave del encabezado.

    Si ninguna fila parece encabezado devuelve todo en None (sin `monto` ni
    `credito`/`debito`): antes se asumían en silencio las posiciones fijas de
    Banco Macro, y un archivo de otro banco se leía mal sin avisar. Ahora quien
    llama tiene que pedirle el mapeo a la persona (ver `extracto_mapper`)."""
    cols = {"hdr_row":1,"monto":None,"credito":None,"debito":None,"fecha":None,
            "titular":None,"orden":None,"saldo":None,"mes":None,
            "cliente_acred":None,"fecha_acred":None,"indicador_dc":None}
    for r in range(1, min(13, ws.max_row + 1)):
        encontrados = {}
        for c in range(1, ws.max_column + 1):
            rol = rol_por_encabezado(ws.cell(r, c).value)
            if rol and rol != "cuit":
                encontrados.setdefault(rol, c)
        # Fila de headers válida si tiene monto unitario O par crédito/débito,
        # y además los datos de la fila siguiente confirman que es un header real.
        if ("monto" in encontrados or "credito" in encontrados or "debito" in encontrados) \
                and _fila_valida_como_header(ws, r, encontrados):
            cols["hdr_row"] = r
            cols.update(encontrados)
            return cols
    return cols

def parsear_generico(ws, cols):
    movimientos = []
    hdr = cols["hdr_row"]
    for row in range(hdr + 1, ws.max_row + 1):
        if cols["monto"]:
            # Columna única de monto (Banco Macro y formato genérico)
            monto = _parse_monto(ws.cell(row, cols["monto"]).value)
            # Si además hay una columna indicadora "Débito/Crédito" por fila
            # (monto siempre positivo, el signo lo da esa columna de texto),
            # usarla para determinar el signo real del movimiento.
            if monto is not None and cols.get("indicador_dc"):
                ind = _normalizar(str(ws.cell(row, cols["indicador_dc"]).value or "").lower().strip())
                if "debito" in ind:
                    monto = -abs(monto)
                elif "credito" in ind:
                    monto = abs(monto)
        else:
            # Columnas separadas crédito/débito (BBVA, Santander, Galicia)
            credito = _parse_monto(ws.cell(row, cols["credito"]).value) if cols.get("credito") else None
            debito  = _parse_monto(ws.cell(row, cols["debito"]).value)  if cols.get("debito")  else None
            credito = abs(credito) if credito is not None else 0.0
            debito  = abs(debito)  if debito  is not None else 0.0
            if credito == 0.0 and debito == 0.0:
                monto = None
            elif credito > 0.0 and debito == 0.0:
                monto = credito
            elif debito > 0.0 and credito == 0.0:
                monto = -debito
            else:
                # Ambas columnas con valor: neto (poco común, pero posible)
                monto = round(credito - debito, 2)
        if monto is None or abs(monto) < 0.01:
            continue
        fecha   = _parse_fecha(ws.cell(row, cols["fecha"]).value)   if cols["fecha"]   else None
        titular = str(ws.cell(row, cols["titular"]).value or "")     if cols["titular"] else ""
        orden   = ws.cell(row, cols["orden"]).value                  if cols["orden"]   else None
        saldo   = _parse_monto(ws.cell(row, cols["saldo"]).value)    if cols["saldo"]   else None
        mes_val = str(ws.cell(row, cols["mes"]).value or "")         if cols["mes"]     else None

        cliente_acred = None
        fecha_acred = None
        if cols.get("cliente_acred"):
            v = ws.cell(row, cols["cliente_acred"]).value
            if v is not None and str(v).strip():
                cliente_acred = str(v).strip()
        if cols.get("fecha_acred"):
            fecha_acred = _parse_fecha(ws.cell(row, cols["fecha_acred"]).value)

        # Mes: SOLO el numero (ej "5"), no "Mayo 2026".
        # Si en el Excel viene "Mayo" o "5" o "05/2026", normalizamos a numero.
        def _mes_normalizado(v, f):
            if v:
                s = str(v).strip()
                # si ya es un numero
                try:
                    n = int(float(s))
                    if 1 <= n <= 12:
                        return str(n)
                except ValueError:
                    pass
            return str(f.month) if f else None

        movimientos.append({
            "orden":   int(orden) if isinstance(orden,(int,float)) else None,
            "fecha":   fecha,
            "mes":     _mes_normalizado(mes_val, fecha),
            "titular": titular.strip() or None,
            "monto":   monto,
            "saldo":   saldo,
            "cliente_acreditado": cliente_acred,
            "fecha_acred": fecha_acred,
        })
    return movimientos

def parsear_extracto_bancario(filepath: str, *, plantillas: "dict | None" = None,
                              mapeo: "dict | None" = None, nombre_archivo: "str | None" = None) -> dict:
    """
    Parsea un extracto bancario (.xlsx, .xls, .csv, .tsv, .txt) de cualquier banco.

    Delegado en `extracto_mapper.analizar_extracto`: mapeo confirmado por la
    persona → plantilla guardada de la org → detección por encabezado →
    sugerencia por contenido. Montos en Decimal. Los movimientos salen siempre
    del más nuevo al más viejo (un archivo ascendente se da vuelta). Si no se reconoce nada devuelve
    0 movimientos y `analisis["necesita_mapeo"] = True` (antes se asumían en
    silencio las columnas de Banco Macro).
    """
    from app.services.extracto_mapper import analizar_extracto

    res = analizar_extracto(filepath, plantillas=plantillas, mapeo=mapeo, nombre_archivo=nombre_archivo)
    movs = res["movimientos"]
    # Una sugerencia por contenido nunca se importa sin confirmación.
    if res["origen"] in ("sugerencia", "ninguno"):
        movs = []
    # Todo el resto del sistema (numeración de `orden` en
    # `crear_extracto_con_movimientos`, corte del merge de UM, huella) espera los
    # movimientos del MÁS NUEVO al más viejo, como los exporta Macro. Si el
    # archivo viene del más viejo al más nuevo (y el sentido se pudo detectar),
    # se da vuelta acá: así un banco "ascendente" se comporta igual que Macro.
    cuadre = res["cuadre"]
    if movs and cuadre.get("orden") == "asc" and cuadre.get("orden_detectado"):
        movs = list(reversed(movs))
    return {
        "movimientos": movs,
        "total": len(movs),
        "banco_detectado": res["banco_clave"] or "generico",
        "analisis": res,
    }

def detectar_header(ws):
    for r in range(1, 6):
        for c in range(1, ws.max_column + 1):
            h = str(ws.cell(r, c).value or '').lower().strip()
            if 'monto' in h or 'importe' in h:
                data_start = r + 1
                for test_col in [c, c + 1]:
                    hits = sum(
                        1 for dr in range(data_start, min(data_start + 6, ws.max_row + 1))
                        if isinstance(ws.cell(dr, test_col).value, (int, float))
                        and 0 < ws.cell(dr, test_col).value < 5_000_000
                    )
                    if hits >= 1:
                        return r, test_col
    return 2, 6

def detectar_cuit_col(ws, hdr_row):
    for c in range(1, ws.max_column + 1):
        h = str(ws.cell(hdr_row, c).value or '').lower().strip()
        if 'cuit' in h or 'cuil' in h:
            return c
    return None

def detectar_titular_col(ws, hdr_row):
    for c in range(1, ws.max_column + 1):
        h = str(ws.cell(hdr_row, c).value or '').lower().strip()
        if 'titular' in h or 'nombre' in h or 'cliente' in h:
            return c
    return None

def parsear_planilla_cliente(filepath: str) -> dict:
    xlsx_path, necesita_cleanup = preparar_archivo(filepath)
    try:
        wb = openpyxl.load_workbook(xlsx_path, data_only=True)
        ws = wb.active
        hdr_row, imp_col = detectar_header(ws)
        cuit_col    = detectar_cuit_col(ws, hdr_row)
        titular_col = detectar_titular_col(ws, hdr_row)
        filas = []
        for row in range(hdr_row + 1, ws.max_row + 1):
            fila_vacia = all(c.value in (None, "") for c in ws[row])
            if fila_vacia:
                # Una fila completamente vacía puede ser un separador accidental
                # en medio de la tabla (seguir) o el fin de la tabla real, con un
                # bloque de resumen/notas debajo (ej. "Suma"/"Comi"/"Transfer N")
                # que no tiene cuit ni titular — ahí cortamos.
                nxt = row + 1
                tiene_identidad_despues = nxt <= ws.max_row and (
                    (cuit_col and ws.cell(nxt, cuit_col).value)
                    or (titular_col and ws.cell(nxt, titular_col).value)
                )
                if tiene_identidad_despues:
                    continue
                break
            monto = ws.cell(row, imp_col).value
            if monto is None or not isinstance(monto, (int, float)):
                continue
            cuit    = ws.cell(row, cuit_col).value    if cuit_col    else None
            titular = ws.cell(row, titular_col).value if titular_col else None
            filas.append({"monto": monto, "cuit": str(cuit) if cuit else None, "titular": str(titular) if titular else None})
        wb.close()
        return {"filas": filas, "total": len(filas), "header_row": hdr_row, "imp_col": imp_col, "cuit_col": cuit_col, "titular_col": titular_col}
    finally:
        if necesita_cleanup and os.path.exists(xlsx_path):
            os.remove(xlsx_path)