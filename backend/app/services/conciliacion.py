"""
Migración de la lógica de conciliación desde watcher.py
Algoritmo de matching de movimientos bancarios contra planillas de clientes
"""

import re
from typing import List, Optional, Tuple
from collections import defaultdict
from sqlalchemy.orm import Session
from app.models.extracto import MovimientoBanco
from app.models.planilla import PlanillaRow

UMBRAL_COMUN = 3  # Si un monto aparece 3+ veces, requiere validación CUIT

def norm_cuit(v) -> str:
    """Normaliza CUIT/CUIL a string de solo dígitos"""
    if v is None:
        return ''
    return re.sub(r'\D', '', str(v))

def parse_importe(v) -> Optional[float]:
    """Acepta int, float, y strings con $, espacios, format ES/EN"""
    if isinstance(v, (int, float)):
        return round(float(v), 2)
    if isinstance(v, str):
        s = v.strip().replace('$', '').replace('\xa0', '').replace(' ', '')
        if not s:
            return None
        if ',' in s and '.' in s:
            if s.rfind(',') > s.rfind('.'):
                s = s.replace('.', '').replace(',', '.')
            else:
                s = s.replace(',', '')
        elif ',' in s:
            s = s.replace(',', '.')
        try:
            return round(float(s), 2)
        except ValueError:
            pass
    return None

def extraer_cuit_titular(titular: str) -> str:
    """Extrae CUIT del campo titular del extracto"""
    if not titular:
        return ''
    nums = re.findall(r'\d{10,11}', str(titular))
    return nums[0] if nums else ''

def es_libre(cliente_acreditado: Optional[str]) -> bool:
    """Verifica si un movimiento está disponible para acreditar"""
    if cliente_acreditado is None:
        return True
    if isinstance(cliente_acreditado, str) and cliente_acreditado.strip().lower() in ('no identificado', ''):
        return True
    return False

def buscar_match(
    monto: float,
    cuit_planilla: Optional[str],
    titular_planilla: Optional[str],
    movimientos: List[MovimientoBanco],
    movimientos_procesados: set
) -> Tuple[Optional[MovimientoBanco], str]:
    """
    Busca un movimiento bancario que coincida con una fila de planilla.

    Retorna: (movimiento_encontrado, status)
    - status: "ok", "no está", "duplicado", "faltan datos", o "acreditado DD/MM"
    """

    # Candidatos: movimientos con el mismo monto
    candidatos = [m for m in movimientos if m.monto == monto]

    if not candidatos:
        return None, "no está"

    # Separar en usados y libres en esta sesión
    no_usados = [m for m in candidatos if m.id not in movimientos_procesados]
    libres = [m for m in no_usados if es_libre(m.cliente_acreditado)]

    if libres:
        # Hay al menos uno libre
        if len(candidatos) < UMBRAL_COMUN:
            # Monto poco frecuente → acreditar al primero libre
            return libres[0], "ok"
        else:
            # Monto común → validar CUIT o titular
            cuit_ex = extraer_cuit_titular(candidatos[0].titular or '')
            cuit_plan = norm_cuit(cuit_planilla)

            # Buscar por CUIT exacto
            if cuit_ex and cuit_plan and cuit_ex == cuit_plan:
                for mov in libres:
                    mov_cuit = extraer_cuit_titular(mov.titular or '')
                    if mov_cuit == cuit_plan:
                        return mov, "ok"

            # Buscar por titular parcial (primeras 2 palabras)
            if titular_planilla:
                palabras = titular_planilla.split()[:2]
                patron = ' '.join(palabras).lower()
                for mov in libres:
                    if mov.titular and patron.lower() in mov.titular.lower():
                        return mov, "ok"

            # No hay match por CUIT ni titular
            return None, "faltan datos"
    else:
        # No hay libres
        if not no_usados:
            # Todos están acreditados (en sesión anterior)
            primer_acreditado = candidatos[0]
            fecha_str = primer_acreditado.fecha_acred.strftime('%d/%m') if primer_acreditado.fecha_acred else 'desconocida'
            return None, f"acreditado {fecha_str}"
        else:
            # Hay no-usados pero todos están ya acreditados
            return None, "duplicado"

def conciliar_planilla(
    db: Session,
    planilla_rows: List[PlanillaRow],
    movimientos: List[MovimientoBanco],
    cliente_nombre: str,
    fecha_acred_str: str
) -> dict:
    """
    Ejecuta la conciliación de una planilla contra los movimientos bancarios.
    Retorna estadísticas del proceso.
    """

    movimientos_procesados = set()
    resultados = {
        "acreditadas": 0,
        "no_encontradas": 0,
        "duplicadas": 0,
        "sin_datos": 0,
        "filas_procesadas": 0
    }

    for row in planilla_rows:
        resultados["filas_procesadas"] += 1

        # Parsear monto de la fila
        monto = parse_importe(row.monto)
        if monto is None:
            row.status = "faltan datos"
            resultados["sin_datos"] += 1
            continue

        # Buscar match
        mov_encontrado, status = buscar_match(
            monto=monto,
            cuit_planilla=row.cuit,
            titular_planilla=row.titular,
            movimientos=movimientos,
            movimientos_procesados=movimientos_procesados
        )

        row.status = status

        if mov_encontrado:
            # Acreditar el movimiento
            mov_encontrado.cliente_acreditado = cliente_nombre
            # Parsear fecha de acreditación
            from datetime import datetime
            if fecha_acred_str.lower() == 'hoy':
                mov_encontrado.fecha_acred = datetime.now().date()
            elif fecha_acred_str.lower() == 'ayer':
                from datetime import timedelta
                mov_encontrado.fecha_acred = (datetime.now() - timedelta(days=1)).date()
            else:
                try:
                    mov_encontrado.fecha_acred = datetime.fromisoformat(fecha_acred_str).date()
                except:
                    pass

            row.orden_movimiento_acreditado = mov_encontrado.id
            movimientos_procesados.add(mov_encontrado.id)
            resultados["acreditadas"] += 1
        else:
            if status == "no está":
                resultados["no_encontradas"] += 1
            elif status == "duplicado":
                resultados["duplicadas"] += 1
            elif status == "faltan datos":
                resultados["sin_datos"] += 1
            elif "acreditado" in status:
                resultados["duplicadas"] += 1

    db.commit()
    return resultados
