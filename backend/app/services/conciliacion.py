"""
Algoritmo de conciliacion bancaria (portado de watcher.py).
El CUIT puede venir en la columna CUIT de la planilla O embebido en el titular.
"""

import re
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from app.models.extracto import MovimientoBanco
from app.models.planilla import PlanillaRow

UMBRAL_COMUN = 3  # Si un monto aparece 3+ veces en el extracto requiere CUIT/titular


def norm_cuit(v) -> str:
    """Solo digitos, sin guiones ni espacios"""
    if v is None:
        return ''
    return re.sub(r'\D', '', str(v))


def extraer_cuit(texto: str) -> str:
    """Extrae el primer CUIT/CUIL (10-11 digitos) que aparezca en el texto"""
    if not texto:
        return ''
    nums = re.findall(r'\d{10,11}', str(texto))
    return nums[0] if nums else ''


def parse_importe(v) -> Optional[float]:
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


def montos_iguales(a: float, b: float) -> bool:
    """Comparacion con tolerancia para evitar errores de float"""
    return abs(a - b) < 0.01


def es_libre(cliente_acreditado: Optional[str]) -> bool:
    if cliente_acreditado is None:
        return True
    return cliente_acreditado.strip().lower() in ('no identificado', '')


def buscar_match(
    monto: float,
    cuit_planilla: Optional[str],
    titular_planilla: Optional[str],
    movimientos: List[MovimientoBanco],
    procesados: set
) -> Tuple[Optional[MovimientoBanco], str]:
    """
    Busca el movimiento bancario que mejor coincide con la fila de planilla.

    CUIT lookup: el CUIT puede venir en:
      - columna CUIT de la planilla  (cuit_planilla)
      - columna titular de la planilla (titular_planilla — puede tener el CUIT embebido)
      - campo titular del extracto (cuit embebido en "TRANSF 20112233440 GARCIA MARIA")
    """
    # Candidatos con el mismo monto (tolerancia 1 centavo)
    candidatos = [m for m in movimientos if montos_iguales(m.monto, monto)]

    if not candidatos:
        return None, "no está"

    no_usados = [m for m in candidatos if m.id not in procesados]
    libres    = [m for m in no_usados  if es_libre(m.cliente_acreditado)]

    if not libres:
        if not no_usados:
            primer = candidatos[0]
            fecha_s = primer.fecha_acred.strftime('%d/%m') if primer.fecha_acred else '?'
            return None, f"acreditado {fecha_s}"
        return None, "duplicado"

    # Monto poco frecuente → acreditar directamente al primer libre
    if len(candidatos) < UMBRAL_COMUN:
        return libres[0], "ok"

    # Monto comun → requiere validar CUIT o titular
    # Obtener el CUIT de la planilla desde cualquiera de los dos campos
    cuit_plan_raw = norm_cuit(cuit_planilla or '')
    if not cuit_plan_raw and titular_planilla:
        cuit_plan_raw = extraer_cuit(titular_planilla)

    # Buscar por CUIT en TODOS los candidatos libres
    if cuit_plan_raw:
        for mov in libres:
            cuit_mov = extraer_cuit(mov.titular or '')
            if cuit_mov and cuit_mov == cuit_plan_raw:
                return mov, "ok"

    # Buscar por coincidencia de primeras 2 palabras del titular
    if titular_planilla:
        palabras = [p for p in titular_planilla.split() if len(p) > 2][:2]
        if palabras:
            patron = ' '.join(palabras).lower()
            for mov in libres:
                if mov.titular and patron in mov.titular.lower():
                    return mov, "ok"

    return None, "faltan datos"


def conciliar_planilla(
    db: Session,
    planilla_rows: List[PlanillaRow],
    movimientos: List[MovimientoBanco],
    cliente_nombre: str,
    fecha_acred_str: str
) -> dict:
    from datetime import datetime, timedelta

    procesados = set()
    res = {"acreditadas": 0, "no_encontradas": 0, "duplicadas": 0, "sin_datos": 0, "filas_procesadas": 0}

    for row in planilla_rows:
        res["filas_procesadas"] += 1
        monto = parse_importe(row.monto)
        if monto is None:
            row.status = "faltan datos"
            res["sin_datos"] += 1
            continue

        mov, status = buscar_match(
            monto=monto,
            cuit_planilla=row.cuit,
            titular_planilla=row.titular,
            movimientos=movimientos,
            procesados=procesados
        )
        row.status = status

        if mov:
            mov.cliente_acreditado = cliente_nombre
            if fecha_acred_str.lower() == 'hoy':
                mov.fecha_acred = datetime.now().date()
            elif fecha_acred_str.lower() == 'ayer':
                mov.fecha_acred = (datetime.now() - timedelta(days=1)).date()
            else:
                try:
                    mov.fecha_acred = datetime.fromisoformat(fecha_acred_str).date()
                except Exception:
                    mov.fecha_acred = datetime.now().date()

            row.orden_movimiento_acreditado = mov.id
            procesados.add(mov.id)
            res["acreditadas"] += 1
        else:
            if status == "no está":
                res["no_encontradas"] += 1
            elif "acreditado" in status or status == "duplicado":
                res["duplicadas"] += 1
            else:
                res["sin_datos"] += 1

    db.commit()
    return res
