"""Defensas para archivos de planilla: inyección de fórmulas al exportar y zip bombs al leer.

Inyección de fórmulas (CSV/Excel injection): un titular, concepto o descripción que viene
del extracto o de la planilla de un cliente puede empezar con `=`, `+`, `-` o `@`. Si se
escribe tal cual, Excel lo toma como fórmula cuando el contador abre el archivo (por ejemplo
`=HYPERLINK("http://...")`). `safe_cell` le antepone un apóstrofo a ese texto para que quede
como texto. Solo toca `str`: números, fechas y Decimal pasan sin cambios, así que los formatos
numéricos de las celdas no cambian.

Zip bomb: un .xlsx es un ZIP. Un archivo chico puede descomprimir a gigas y tumbar el proceso
cuando openpyxl/pandas lo abren. `verificar_xlsx` mira el índice del ZIP (sin descomprimir)
antes de parsear y responde 413 si el tamaño descomprimido o la tasa de compresión son absurdos.
"""
import io
import re
import zipfile

from fastapi import HTTPException

# Caracteres con los que Excel/LibreOffice arrancan una fórmula (o la inyectan vía DDE).
_PREFIJOS_FORMULA = ("=", "+", "-", "@", "\t", "\r")

# Texto que es solo un número ("-1234,56", "+12", "-") no puede armar una fórmula: se deja igual.
_SOLO_NUMERO = re.compile(r"^[-+]?[\d.,]*$")

# Límites de un .xlsx subido (ver `verificar_xlsx`).
MAX_XLSX_DESCOMPRIMIDO = 100 * 1024 * 1024   # 100 MB descomprimido en total
MAX_TASA_COMPRESION = 200                    # descomprimido / comprimido por archivo interno


def safe_cell(valor):
    """Neutraliza un valor de texto que Excel interpretaría como fórmula.

    Devuelve el mismo valor si no es `str` o si no empieza con un carácter peligroso."""
    if not isinstance(valor, str) or not valor:
        return valor
    if not valor.startswith(_PREFIJOS_FORMULA):
        return valor
    if _SOLO_NUMERO.match(valor):
        return valor
    return "'" + valor


def sanear_workbook(wb) -> None:
    """Aplica `safe_cell` a todas las celdas de texto del libro (llamar justo antes de `save`).

    Los exports no escriben fórmulas a propósito: si alguno lo necesitara, tiene que escribirla
    después de llamar a esta función."""
    for ws in wb.worksheets:
        for fila in ws.iter_rows():
            for celda in fila:
                v = celda.value
                if isinstance(v, str):
                    nuevo = safe_cell(v)
                    if nuevo is not v:
                        celda.value = nuevo


def verificar_xlsx(contenido: bytes) -> None:
    """Rechaza con 413 un .xlsx que descomprime a demasiado (zip bomb).

    No descomprime nada: suma `file_size` del índice del ZIP. Si el contenido no es un ZIP
    válido no hace nada (lo rechaza después el parser con su propio mensaje)."""
    if not contenido or not contenido.startswith(b"PK"):
        return
    try:
        with zipfile.ZipFile(io.BytesIO(contenido)) as zf:
            infos = zf.infolist()
    except (zipfile.BadZipFile, ValueError):
        return
    total = 0
    for info in infos:
        total += info.file_size
        if total > MAX_XLSX_DESCOMPRIMIDO:
            raise HTTPException(
                413,
                f"El Excel descomprimido supera el máximo de {MAX_XLSX_DESCOMPRIMIDO // (1024 * 1024)} MB. "
                "Revisá que sea el archivo correcto.",
            )
        # Tasa absurda en un archivo interno de más de 1 MB → zip bomb.
        if info.file_size > 1024 * 1024 and info.file_size > MAX_TASA_COMPRESION * max(info.compress_size, 1):
            raise HTTPException(413, "El Excel tiene una compresión anómala y no se puede abrir.")
