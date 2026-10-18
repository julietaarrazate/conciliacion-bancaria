"""Extracción de texto CON geometría de un PDF (pdfminer.six).

Se usa el intérprete de bajo nivel con `laparams=None`: devuelve cada carácter
(`LTChar`) con su posición y es ~5 veces más rápido que el análisis de layout de
pdfminer (un resumen de 40 páginas se lee en ~1 s). Con los caracteres armamos:

- **Palabras**: caracteres contiguos de un mismo renglón. Se corta la palabra en
  un espacio explícito o cuando el hueco entre letras supera ~0,2 del cuerpo de
  la fuente (muchos PDF de bancos no emiten espacios: posicionan cada palabra).
- **Líneas**: palabras con la misma línea de base (tolerancia ~0,3 del cuerpo),
  ordenadas de izquierda a derecha. Las líneas quedan en orden de lectura:
  página ascendente y de arriba hacia abajo.

Las coordenadas son las del PDF: `y` crece hacia arriba (y=0 es el pie de la
página). No se interpreta nada del negocio acá: eso es de `tabla.py`.
"""

from __future__ import annotations

import io
import logging
import unicodedata
from dataclasses import dataclass, field
from typing import Iterator, Optional

from .errores import ExtractoPdfError

logger = logging.getLogger(__name__)

MAX_PAGINAS = 80
# Menos de esto de caracteres útiles por página (en promedio) = PDF escaneado.
_MIN_CARACTERES_POR_PAGINA = 40

MENSAJE_CONTRASENA = (
    "El PDF tiene contraseña y no se puede leer. Abrilo con la contraseña y usá "
    "Imprimir → Guardar como PDF para generar una copia sin contraseña, y subí esa copia."
)
MENSAJE_DANADO = "El archivo PDF está dañado o no se puede leer. Probá descargarlo de nuevo del home banking."
MENSAJE_NO_PDF = "El archivo no es un PDF válido."


@dataclass(slots=True)
class Palabra:
    texto: str
    x0: float
    x1: float
    size: float

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2


@dataclass(slots=True)
class Linea:
    pagina: int                 # 1-based
    y: float                    # línea de base (coordenadas PDF: más alto = más arriba)
    palabras: list[Palabra]
    ancho_pagina: float
    alto_pagina: float
    size: float = 0.0           # cuerpo de fuente dominante de la línea
    texto: str = ""
    # Caches que completa tabla.py (tokens con importes ya parseados, etc.).
    cache: dict = field(default_factory=dict)

    @property
    def x0(self) -> float:
        return self.palabras[0].x0 if self.palabras else 0.0

    @property
    def altura_relativa(self) -> float:
        """0 = pie de página, 1 = borde superior."""
        return self.y / self.alto_pagina if self.alto_pagina else 0.0


@dataclass(slots=True)
class Documento:
    paginas: int
    lineas: list[Linea]
    caracteres: int                     # caracteres útiles (sin espacios ni (cid:N))
    caracteres_ilegibles: int           # glifos sin mapeo a Unicode: "(cid:N)"
    paginas_ilegibles: list[int]
    escaneado: bool

    def lineas_de_pagina(self, pagina: int) -> list[Linea]:
        return [ln for ln in self.lineas if ln.pagina == pagina]


@dataclass(slots=True)
class _Char:
    texto: str
    x0: float
    x1: float
    base: float
    size: float


def _iter_chars(contenedor) -> Iterator:
    from pdfminer.layout import LTChar, LTContainer

    for obj in contenedor:
        if isinstance(obj, LTChar):
            yield obj
        elif isinstance(obj, LTContainer):     # LTFigure (form XObjects)
            yield from _iter_chars(obj)


def _es_espacio(t: str) -> bool:
    return not t or t.isspace()


def _armar_lineas(chars: list[_Char], pagina: int, ancho: float, alto: float) -> list[Linea]:
    if not chars:
        return []
    chars.sort(key=lambda c: (-c.base, c.x0))
    grupos: list[list[_Char]] = []
    ref = None
    for c in chars:
        tol = max(1.0, 0.3 * c.size)
        if ref is None or abs(c.base - ref) > tol:
            grupos.append([c])
            ref = c.base
        else:
            grupos[-1].append(c)

    lineas: list[Linea] = []
    for grupo in grupos:
        grupo.sort(key=lambda c: c.x0)
        palabras: list[Palabra] = []
        actual: list[_Char] = []
        prev: Optional[_Char] = None
        for c in grupo:
            if _es_espacio(c.texto):
                if actual:
                    palabras.append(_palabra(actual))
                    actual = []
                prev = None
                continue
            if prev is not None:
                ancho_prev = max(prev.x1 - prev.x0, 0.1)
                # Negrita "simulada": el mismo glifo dibujado dos veces corrido.
                if c.texto == prev.texto and abs(c.x0 - prev.x0) < 0.35 * ancho_prev:
                    continue
                hueco = c.x0 - prev.x1
                if hueco > 0.2 * max(prev.size, c.size, 1.0):
                    palabras.append(_palabra(actual))
                    actual = []
            actual.append(c)
            prev = c
        if actual:
            palabras.append(_palabra(actual))
        if not palabras:
            continue
        tamanos = sorted(p.size for p in palabras)
        linea = Linea(
            pagina=pagina,
            y=grupo[0].base,
            palabras=palabras,
            ancho_pagina=ancho,
            alto_pagina=alto,
            size=tamanos[len(tamanos) // 2],
            texto=" ".join(p.texto for p in palabras),
        )
        lineas.append(linea)
    return lineas


def _palabra(chars: list[_Char]) -> Palabra:
    texto = unicodedata.normalize("NFKC", "".join(c.texto for c in chars))
    return Palabra(
        texto=texto,
        x0=chars[0].x0,
        x1=max(c.x1 for c in chars),
        size=max(c.size for c in chars),
    )


def _abrir(contenido: bytes):
    from pdfminer.pdfdocument import PDFDocument, PDFEncryptionError
    from pdfminer.pdfpage import PDFPage
    from pdfminer.pdfparser import PDFParser

    if not contenido or b"%PDF-" not in contenido[:1024]:
        raise ExtractoPdfError(MENSAJE_NO_PDF, 400)
    try:
        documento = PDFDocument(PDFParser(io.BytesIO(contenido)))
    except PDFEncryptionError as ex:   # incluye PDFPasswordIncorrect
        raise ExtractoPdfError(MENSAJE_CONTRASENA, 400) from ex
    except Exception as ex:            # PDFSyntaxError, PSEOF, falta de cifrado soportado, etc.
        logger.info("PDF ilegible: %s", ex)
        raise ExtractoPdfError(MENSAJE_DANADO, 400) from ex
    try:
        paginas = list(PDFPage.create_pages(documento))
    except PDFEncryptionError as ex:
        raise ExtractoPdfError(MENSAJE_CONTRASENA, 400) from ex
    except Exception as ex:
        logger.info("PDF sin árbol de páginas legible: %s", ex)
        raise ExtractoPdfError(MENSAJE_DANADO, 400) from ex
    if not paginas:
        raise ExtractoPdfError("El PDF no tiene páginas.", 400)
    if len(paginas) > MAX_PAGINAS:
        raise ExtractoPdfError(
            f"El PDF tiene {len(paginas)} páginas y el máximo es {MAX_PAGINAS}. "
            "Descargá el resumen por mes (o por período más corto) y subilo por partes.",
            413,
        )
    return paginas


def contar_paginas(contenido: bytes) -> int:
    """Cantidad de páginas (valida que sea un PDF legible; lanza ExtractoPdfError)."""
    return len(_abrir(contenido))


def extraer_documento(contenido: bytes) -> Documento:
    """Lee el PDF y devuelve sus líneas con geometría.

    Lanza `ExtractoPdfError` si no es un PDF, está dañado, tiene contraseña de
    apertura o supera `MAX_PAGINAS`. Un PDF protegido solo "contra copia" (sin
    contraseña de apertura) se lee igual: es el resumen del propio usuario."""
    from pdfminer.converter import PDFPageAggregator
    from pdfminer.pdfdocument import PDFEncryptionError
    from pdfminer.pdfinterp import PDFPageInterpreter, PDFResourceManager

    paginas = _abrir(contenido)
    gestor = PDFResourceManager(caching=True)
    dispositivo = PDFPageAggregator(gestor, laparams=None)
    interprete = PDFPageInterpreter(gestor, dispositivo)

    lineas: list[Linea] = []
    utiles = ilegibles = 0
    paginas_ilegibles: list[int] = []
    for n, pagina in enumerate(paginas, start=1):
        try:
            interprete.process_page(pagina)
            layout = dispositivo.get_result()
        except PDFEncryptionError as ex:
            raise ExtractoPdfError(MENSAJE_CONTRASENA, 400) from ex
        except Exception as ex:  # una página rota no tumba todo el resumen
            logger.info("No se pudo interpretar la página %s del PDF: %s", n, ex)
            paginas_ilegibles.append(n)
            continue
        chars: list[_Char] = []
        for obj in _iter_chars(layout):
            a, b, c, d, _e, f = obj.matrix
            # Solo texto horizontal y derecho (los textos girados de los márgenes
            # suelen ser leyendas legales o códigos de control).
            if abs(b) > 1e-3 or abs(c) > 1e-3 or a <= 0 or d <= 0:
                continue
            t = obj.get_text()
            if t.startswith("(cid:"):
                ilegibles += 1
                continue
            if not _es_espacio(t):
                utiles += 1
            chars.append(_Char(t, float(obj.x0), float(obj.x1), float(f), float(obj.size)))
        lineas.extend(_armar_lineas(chars, n, float(layout.width), float(layout.height)))

    total = len(paginas)
    escaneado = utiles < _MIN_CARACTERES_POR_PAGINA * total or ilegibles > utiles
    return Documento(
        paginas=total,
        lineas=lineas,
        caracteres=utiles,
        caracteres_ilegibles=ilegibles,
        paginas_ilegibles=paginas_ilegibles,
        escaneado=escaneado,
    )


def texto_con_columnas(doc: Documento, paginas: Optional[set[int]] = None, puntos_por_columna: float = 4.0) -> str:
    """Texto plano que respeta la posición horizontal de cada palabra (para la IA):
    así distingue las columnas de débito/crédito/saldo sin ver el PDF."""
    salida: list[str] = []
    pagina_actual = None
    for ln in doc.lineas:
        if paginas is not None and ln.pagina not in paginas:
            continue
        if ln.pagina != pagina_actual:
            pagina_actual = ln.pagina
            salida.append(f"--- Página {ln.pagina} ---")
        renglon = ""
        for p in ln.palabras:
            col = int(p.x0 / puntos_por_columna)
            if len(renglon) < col:
                renglon += " " * (col - len(renglon))
            elif renglon:
                renglon += " "
            renglon += p.texto
        salida.append(renglon.rstrip())
    return "\n".join(salida)
