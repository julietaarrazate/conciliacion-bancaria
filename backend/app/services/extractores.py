"""Extractores canónicos de identificadores para el motor de conciliación.

Fuente única de verdad para la extracción de CUIT/CBU/números/nombres desde el
texto libre del extracto bancario y de las planillas de clientes.

IMPORTANTE: la implementación de estas funciones es la que históricamente vivía en
`services/conciliacion.py` y de la que depende la Organización A en producción. NO
cambiar la lógica (regex, longitudes, normalización) sin re-validar el motor: son
behavior-preserving. `services/aprendizaje.py` pasó a consumir estas mismas
funciones para garantizar que aprende con EXACTAMENTE la misma extracción que
usa el matcher (antes tenía copias locales del mismo regex).
"""

import re
from typing import Optional


def norm_cuit(v) -> str:
    """Solo digitos, sin guiones ni espacios."""
    if v is None:
        return ''
    return re.sub(r'\D', '', str(v))


def extraer_cuit(texto: str) -> str:
    """Extrae el primer CUIT/CUIL (10-11 digitos) que aparezca en el texto."""
    if not texto:
        return ''
    nums = re.findall(r'\b\d{10,11}\b', str(texto))
    return nums[0] if nums else ''


def extraer_cbu(texto: str) -> str:
    """Extrae el primer CBU/CVU (22 digitos exactos) del texto."""
    if not texto:
        return ''
    nums = re.findall(r'\b\d{22}\b', str(texto))
    return nums[0] if nums else ''


def extraer_todos_numeros(texto: str) -> set:
    """
    Extrae TODOS los numeros significativos de un texto sin formato fijo.
    Incluye: CUIT (10-11), CBU/CVU (22), numeros de cuenta/operacion (6-21).
    Util para el campo 'titular' del extracto Banco Macro que mezcla todo.
    Ej: "TRANSF 20112233440 GARCIA MARIA" -> {"20112233440"}
        "CBU 2850590940090418135201 EMPRESA" -> {"2850590940090418135201"}
        "ACRED 00001234567 RODRIGUEZ JUAN" -> {"1234567"}
    """
    if not texto:
        return set()
    # Todos los numeros de 6+ digitos (excluye numeros cortos tipo dia/mes)
    return set(re.findall(r'\b\d{6,22}\b', str(texto)))


def numeros_de_planilla(cuit: Optional[str], titular: Optional[str], referencia: Optional[str]) -> set:
    """
    Reune todos los identificadores numericos de una fila de planilla.
    Incluye CUIT, CBU, numeros de cuenta u operacion que el cliente haya anotado.
    """
    nums = set()
    for campo in [cuit, titular, referencia]:
        if campo:
            nums.update(extraer_todos_numeros(campo))
    return nums


def normalizar_nombre(texto: str) -> str:
    """Normaliza nombre para comparacion: minusculas, sin tildes basicas, sin doble espacio."""
    if not texto:
        return ''
    t = texto.lower().strip()
    for a, b in [('á','a'),('é','e'),('í','i'),('ó','o'),('ú','u'),('ñ','n')]:
        t = t.replace(a, b)
    return re.sub(r'\s+', ' ', t)
