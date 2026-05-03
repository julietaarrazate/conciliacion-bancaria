"""
Algoritmo de conciliacion bancaria.
Soporta configuracion por organizacion (multi-tenant).
Caneland (org 1) usa el algoritmo original: monto + CUIT.
"""

import re
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session
from app.models.extracto import MovimientoBanco
from app.models.planilla import PlanillaRow

UMBRAL_COMUN = 3


def norm_cuit(v) -> str:
    if v is None:
        return ''
    return re.sub(r'\D', '', str(v))


def extraer_cuit(texto: str) -> str:
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


def montos_iguales(a: float, b: float, tolerancia: float = 0.01) -> bool:
    return abs(a - b) < tolerancia


def es_libre(cliente_acreditado: Optional[str]) -> bool:
    if cliente_acreditado is None:
        return True
    return cliente_acreditado.strip().lower() in ('no identificado', '')


def buscar_match_referencia(
    referencia: str,
    movimientos: List[MovimientoBanco],
    procesados: set
) -> Optional[MovimientoBanco]:
    """Match por referencia exacta en el campo titular del extracto."""
    if not referencia:
        return None
    ref_norm = referencia.strip().lower()
    for mov in movimientos:
        if mov.id in procesados:
            continue
        if not es_libre(mov.cliente_acreditado):
            continue
        if mov.titular and ref_norm in mov.titular.lower():
            return mov
    return None


def buscar_match(
    monto: float,
    cuit_planilla: Optional[str],
    titular_planilla: Optional[str],
    referencia_planilla: Optional[str],
    movimientos: List[MovimientoBanco],
    procesados: set,
    org_config: Dict[str, Any]
) -> Tuple[Optional[MovimientoBanco], str]:
    """
    Busca el movimiento bancario que mejor coincide con la fila de planilla.
    Respeta match_rules de la configuracion de la organizacion.
    """
    match_rules = org_config.get("match_rules", ["monto_cuit"])
    tolerancia = org_config.get("tolerancia_monto", 0.01)

    # 1. Match por referencia (si la org lo habilita)
    if "referencia" in match_rules and referencia_planilla:
        mov = buscar_match_referencia(referencia_planilla, movimientos, procesados)
        if mov and montos_iguales(mov.monto, monto, tolerancia):
            return mov, "ok"

    # 2. Match por monto
    candidatos = [m for m in movimientos if montos_iguales(m.monto, monto, tolerancia)]

    if not candidatos:
        return None, "no está"

    no_usados = [m for m in candidatos if m.id not in procesados]
    libres = [m for m in no_usados if es_libre(m.cliente_acreditado)]

    if not libres:
        if not no_usados:
            primer = candidatos[0]
            fecha_s = primer.fecha_acred.strftime('%d/%m') if primer.fecha_acred else '?'
            return None, f"acreditado {fecha_s}"
        return None, "duplicado"

    # Monto poco frecuente → acreditar directamente
    if len(candidatos) < UMBRAL_COMUN:
        return libres[0], "ok"

    # Monto comun → validar CUIT o titular
    cuit_plan_raw = norm_cuit(cuit_planilla or '')
    if not cuit_plan_raw and titular_planilla:
        cuit_plan_raw = extraer_cuit(titular_planilla)

    if cuit_plan_raw:
        for mov in libres:
            cuit_mov = extraer_cuit(mov.titular or '')
            if cuit_mov and cuit_mov == cuit_plan_raw:
                return mov, "ok"

    if titular_planilla:
        palabras = [p for p in titular_planilla.split() if len(p) > 2][:2]
        if palabras:
            patron = ' '.join(palabras).lower()
            for mov in libres:
                if mov.titular and patron in mov.titular.lower():
                    return mov, "ok"

    return None, "faltan datos"


# Config por defecto (Caneland - comportamiento original)
CONFIG_CANELAND = {
    "match_rules": ["monto_cuit"],
    "tolerancia_monto": 0.01,
    "dias_tolerancia_fecha": 0,
    "estados_habilitados": ["pendiente", "ok", "no está", "duplicado", "faltan datos"],
    "requiere_cierre_periodo": False,
}


def conciliar_planilla(
    db: Session,
    planilla_rows: List[PlanillaRow],
    movimientos: List[MovimientoBanco],
    cliente_nombre: str,
    fecha_acred_str: str,
    org_config: Optional[Dict[str, Any]] = None
) -> dict:
    from datetime import datetime, timedelta

    config = org_config or CONFIG_CANELAND
    estados_habilitados = config.get("estados_habilitados", [])

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
            referencia_planilla=getattr(row, 'referencia', None),
            movimientos=movimientos,
            procesados=procesados,
            org_config=config
        )

        # Para orgs con estados ricos: marcar EN_REVISION si faltan datos
        if status == "faltan datos" and "EN_REVISION" in estados_habilitados:
            row.status = "EN_REVISION"
            res["sin_datos"] += 1
            continue

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
