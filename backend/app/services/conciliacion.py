"""
Algoritmo de conciliacion bancaria — version mejorada.
Soporta configuracion por organizacion (multi-tenant).
Organización A sigue usando el algoritmo original (monto + CUIT/titular).
"""

import re
from decimal import Decimal
from typing import List, Optional, Tuple, Dict, Any
from datetime import date
from sqlalchemy.orm import Session
from app.models.extracto import MovimientoBanco
from app.models.planilla import PlanillaRow

# Extractores canónicos (fuente única de verdad, compartida con aprendizaje.py).
# Se re-exportan desde este módulo para no romper imports existentes.
from app.services.extractores import (
    norm_cuit,
    extraer_cuit,
    extraer_cbu,
    extraer_todos_numeros,
    numeros_de_planilla,
    normalizar_nombre,
)

# Umbral base: si un monto aparece >= N veces requiere validacion de identidad
UMBRAL_BASE = 3


def parse_importe(v) -> Optional[float]:
    if isinstance(v, (int, float, Decimal)):
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


def montos_iguales(a, b, tolerancia: float = 0.01) -> bool:
    return abs(float(a) - float(b)) < tolerancia


def es_libre(cliente_acreditado: Optional[str]) -> bool:
    if cliente_acreditado is None:
        return True
    return cliente_acreditado.strip().lower() in ('no identificado', '')


def _bonus_fecha(fecha_planilla: Optional[date], fecha_mov: Optional[date], dias_tolerancia: int) -> int:
    """
    Bonus progresivo por proximidad de fecha.
    Cubre feriados, fines de semana y demoras bancarias tipicas.

      0 dias (mismo dia)          → +5
      1-2 dias (lun-vie normal)   → +4
      3-4 dias (fin de semana)    → +3
      5-7 dias (feriado largo)    → +2
      8-10 dias (caso extremo)    → +1
      > dias_tolerancia           → 0
    """
    if not fecha_planilla or not fecha_mov or dias_tolerancia <= 0:
        return 0
    delta = abs((fecha_planilla - fecha_mov).days)
    if delta > dias_tolerancia:
        return 0
    if delta == 0:
        return 5
    if delta <= 2:
        return 4
    if delta <= 4:
        return 3
    if delta <= 7:
        return 2
    return 1


def _score_identidad(
    cuit_plan: str,
    cbu_plan: str,
    titular_plan: str,
    nums_planilla: set,
    mov: MovimientoBanco,
    fecha_planilla: Optional[date],
    dias_tolerancia: int
) -> int:
    """
    Score de similitud entre una fila de planilla y un movimiento bancario.

    Identidad (quien pago):
      12 = CUIT exacto
      10 = CBU/CVU exacto (22 digitos)
       8 = numero de cuenta largo (10+ digitos) en comun
       6 = numero de referencia/operacion (6-9 digitos) en comun
       5 = titular (primeras 2 palabras)
       3 = titular (primera palabra larga)

    Fecha (cuando pago) — bonus progresivo:
      +5 = mismo dia
      +4 = 1-2 dias (demora normal)
      +3 = 3-4 dias (fin de semana)
      +2 = 5-7 dias (feriado largo)
      +1 = 8-10 dias (caso extremo)

    La fecha nunca descarta un match por identidad fuerte —
    solo ayuda a desempatar cuando hay multiples candidatos con el mismo monto.
    """
    score = 0
    titular_mov = mov.titular or ''
    nums_mov = extraer_todos_numeros(titular_mov)

    # ── CUIT exacto ────────────────────────────────────────────
    cuit_mov = extraer_cuit(titular_mov)
    if cuit_plan and cuit_mov and cuit_plan == cuit_mov:
        score = 12 + _bonus_fecha(fecha_planilla, mov.fecha, dias_tolerancia)
        return score

    # ── CUIT planilla como substring de dígitos del mov ────────
    # Cubre formatos "20.112.233.440", "20-11223344-0", pegado a texto, etc.
    if cuit_plan and len(cuit_plan) >= 10:
        digitos_mov = re.sub(r'\D', '', titular_mov)
        if cuit_plan in digitos_mov:
            score = 12 + _bonus_fecha(fecha_planilla, mov.fecha, dias_tolerancia)
            return score

    # ── CBU/CVU exacto ─────────────────────────────────────────
    cbu_mov = extraer_cbu(titular_mov)
    if cbu_plan and cbu_mov and cbu_plan == cbu_mov:
        score = 10 + _bonus_fecha(fecha_planilla, mov.fecha, dias_tolerancia)
        return score

    # ── Cruce de todos los numeros significativos ───────────────
    # Captura: nro de cuenta, nro operacion, referencia, CBU parcial, etc.
    if nums_planilla and nums_mov:
        interseccion = nums_planilla & nums_mov
        if interseccion:
            max_len = max(len(n) for n in interseccion)
            if max_len >= 22:
                base = 10   # CBU/CVU por longitud
            elif max_len >= 10:
                base = 8    # nro cuenta largo / CUIT sin guiones
            else:
                base = 6    # nro operacion o referencia corta
            score = base + _bonus_fecha(fecha_planilla, mov.fecha, dias_tolerancia)
            return score

    # ── Titular por palabras (fallback) ────────────────────────
    if titular_plan:
        norm_plan = normalizar_nombre(titular_plan)
        norm_mov  = normalizar_nombre(titular_mov)
        # >=3 para no filtrar nombres cortos (Ana, Leo, Sol, etc.)
        palabras = [p for p in norm_plan.split() if len(p) >= 3 and p.isalpha()]

        if len(palabras) >= 2:
            patron2 = ' '.join(palabras[:2])
            if patron2 in norm_mov:
                # Ambas palabras en orden exacto → match fuerte
                score += 5
            elif all(p in norm_mov for p in palabras[:2]):
                # Ambas palabras presentes, distinto orden (GARCIA JUAN vs JUAN GARCIA)
                score += 4
            elif palabras[0] in norm_mov:
                # Solo la primera palabra → match débil
                score += 3
        elif len(palabras) == 1:
            if palabras[0] in norm_mov:
                score += 3

    if score > 0:
        score += _bonus_fecha(fecha_planilla, mov.fecha, dias_tolerancia)

    return score


def buscar_match_referencia(
    referencia: str,
    monto: float,
    movimientos: List[MovimientoBanco],
    procesados: set,
    tolerancia: float
) -> Optional[MovimientoBanco]:
    """Match por referencia exacta en el campo titular del extracto."""
    if not referencia:
        return None
    ref_norm = referencia.strip().lower()
    for mov in movimientos:
        if mov.id in procesados or not es_libre(mov.cliente_acreditado):
            continue
        if mov.titular and ref_norm in mov.titular.lower():
            if montos_iguales(mov.monto, monto, tolerancia):
                return mov
    return None


def buscar_match(
    monto: float,
    cuit_planilla: Optional[str],
    titular_planilla: Optional[str],
    referencia_planilla: Optional[str],
    fecha_planilla: Optional[date],
    movimientos: List[MovimientoBanco],
    procesados: set,
    org_config: Dict[str, Any],
    cliente_nombre: str = "",
) -> Tuple[Optional[MovimientoBanco], str]:
    """
    Busca el movimiento bancario que mejor coincide con la fila de planilla.
    Usa scoring para desempatar cuando hay multiples candidatos con identidad similar.
    """
    match_rules     = org_config.get("match_rules", ["monto_cuit"])
    tolerancia      = org_config.get("tolerancia_monto", 0.01)
    dias_tolerancia = org_config.get("dias_tolerancia_fecha", 0)

    # 1. Match por referencia (si habilitado)
    if "referencia" in match_rules and referencia_planilla:
        mov = buscar_match_referencia(referencia_planilla, monto, movimientos, procesados, tolerancia)
        if mov:
            return mov, "ok"

    # 2. Candidatos por monto
    candidatos = [m for m in movimientos if montos_iguales(m.monto, monto, tolerancia)]

    if not candidatos:
        return None, "no está"

    no_usados = [m for m in candidatos if m.id not in procesados]
    cliente_norm = cliente_nombre.strip().lower() if cliente_nombre else ""
    libres = [
        m for m in no_usados
        if es_libre(m.cliente_acreditado)
        or (cliente_norm and (m.cliente_acreditado or '').strip().lower() == cliente_norm)
    ]

    if not libres:
        if not no_usados:
            # Todos los candidatos ya fueron usados en esta misma corrida:
            # la misma fila aparece dos veces en esta planilla → duplicado real
            return None, "duplicado"
        # Hay candidatos no usados en esta corrida pero todos ya tienen cliente_acreditado:
        # el movimiento ya fue acreditado en una corrida anterior
        primer = next((m for m in no_usados if m.fecha_acred), no_usados[0])
        fecha_s = primer.fecha_acred.strftime('%d/%m') if primer.fecha_acred else '?'
        return None, f"acreditado {fecha_s}"

    # Regla fundamental para extractos de alto volumen:
    #   - Monto UNICO (aparece 1 sola vez) → acreditar directo, no hay ambiguedad
    #   - Monto REPETIDO (2+ veces)        → SIEMPRE exigir identidad
    #
    # Razon: en un extracto real puede haber 30 movimientos de $50.000 el mismo dia
    # de clientes distintos. Acreditar sin validar CUIT/CBU seria incorrecto.
    if len(candidatos) == 1:
        return libres[0], "ok"

    # Monto repetido → scoring por identidad (CUIT, CBU, numeros, titular)
    cuit_plan_raw = norm_cuit(cuit_planilla or '')
    if not cuit_plan_raw and titular_planilla:
        cuit_plan_raw = extraer_cuit(titular_planilla)

    cbu_plan = ''
    if titular_planilla:
        cbu_plan = extraer_cbu(titular_planilla)
    if not cbu_plan and cuit_planilla:
        cbu_plan = extraer_cbu(cuit_planilla)

    # Todos los numeros significativos de la planilla (CUIT, CBU, nro cuenta, referencia, etc.)
    nums_plan = numeros_de_planilla(cuit_planilla, titular_planilla, referencia_planilla)

    # Calcular score para cada candidato libre
    candidatos_scored = []
    for mov in libres:
        score = _score_identidad(
            cuit_plan_raw, cbu_plan, titular_planilla or '',
            nums_plan,
            mov, fecha_planilla, dias_tolerancia
        )
        if score > 0:
            candidatos_scored.append((score, mov))

    if candidatos_scored:
        candidatos_scored.sort(key=lambda x: x[0], reverse=True)
        mejor_score, mejor_mov = candidatos_scored[0]

        # Empate con score bajo entre dos candidatos = ambiguo, no arriesgar
        if (len(candidatos_scored) > 1
                and candidatos_scored[1][0] == mejor_score
                and mejor_score < 5):
            n = len(candidatos)
            return None, f"ambiguo ({n} candidatos, mismo score)"

        return mejor_mov, "ok"

    # Sin ningún dato identificatorio → explicar qué falta
    n = len(candidatos)
    tiene_algo = any([cuit_plan_raw, cbu_plan, nums_plan, titular_planilla, referencia_planilla])
    if not tiene_algo:
        return None, f"sin datos ({n} mov. del mismo monto — agregar CUIT/CBU/titular)"
    return None, f"no coincide ({n} mov. del mismo monto — revisar CUIT/CBU/titular)"


# Palabras genéricas de bancos que NO constituyen identidad del pagador.
# Ej: Banco Comercio acredita todo como "CRÉDITO POR CREDIN" / "CRÉDITO POR
# TRANSFERENCIA" — no dice quién pagó, solo se puede conciliar por monto.
_PALABRAS_GENERICAS_BANCO = frozenset({
    "credito", "transferencia", "credin", "deposito", "pago", "transf",
    "cuenta", "proveedores", "haberes", "varios", "sircreb", "imp", "ley",
})


def _mov_tiene_identidad(titular: Optional[str]) -> bool:
    """True si el titular del movimiento identifica a quién pagó.

    Tiene identidad si aparece un CUIT, o si el titular normalizado tiene >=2
    palabras alfabéticas de >=3 letras que NO sean palabras genéricas de banco.
    Read-only: no muta nada.
    """
    if not titular:
        return False
    if extraer_cuit(titular):
        return True
    norm = normalizar_nombre(titular)
    palabras = [
        p for p in norm.split()
        if len(p) >= 3 and p.isalpha() and p not in _PALABRAS_GENERICAS_BANCO
    ]
    return len(palabras) >= 2


def diagnostico_conciliacion(rows, movimientos) -> Dict[str, Any]:
    """Diagnóstico read-only del contexto de una conciliación.

    Se calcula DESPUÉS de conciliar para explicar en la UI por qué muchas filas
    pueden quedar sin conciliar (banco sin identidad, monto ausente del extracto,
    fechas que no solapan). NO altera qué fila matchea ni los status: es 100%
    aditivo y no tiene efectos secundarios (no toca rows, movimientos ni la DB).

    Args:
        rows: PlanillaRow con .monto, .cuit, .titular, .fecha (o .fecha_acred).
        movimientos: MovimientoBanco del extracto con .titular, .monto, .fecha.

    Returns dict con:
        banco_trae_identidad: bool | None (None si no hay movimientos)
        cobertura_montos: {"en_extracto": int, "total": int}
        periodo_planilla / periodo_extracto: {"desde": date|None, "hasta": date|None}
        solapan_fechas: bool
    """
    movs = list(movimientos or [])
    lista_rows = list(rows or [])

    # ── banco_trae_identidad ───────────────────────────────────────
    if not movs:
        banco_trae_identidad: Optional[bool] = None
    else:
        con_identidad = sum(1 for m in movs if _mov_tiene_identidad(getattr(m, "titular", None)))
        fraccion = con_identidad / len(movs)
        banco_trae_identidad = fraccion >= 0.30

    # ── cobertura_montos (Decimal, tolerancia 1 peso) ──────────────
    tol = Decimal("1")
    montos_mov = []
    for m in movs:
        mm = getattr(m, "monto", None)
        if mm is not None:
            try:
                montos_mov.append(abs(Decimal(str(mm))))
            except Exception:
                pass

    total = 0
    en_extracto = 0
    for r in lista_rows:
        rm = getattr(r, "monto", None)
        if rm is None:
            continue
        total += 1
        try:
            monto_row = abs(Decimal(str(rm)))
        except Exception:
            continue
        if any(abs(monto_row - mv) <= tol for mv in montos_mov):
            en_extracto += 1

    # ── periodos ───────────────────────────────────────────────────
    def _rango(objetos, *attrs):
        fechas = []
        for o in objetos:
            f = None
            for a in attrs:
                f = getattr(o, a, None)
                if f is not None:
                    break
            if f is not None:
                fechas.append(f)
        if not fechas:
            return None, None
        return min(fechas), max(fechas)

    plan_desde, plan_hasta = _rango(lista_rows, "fecha", "fecha_acred")
    ext_desde, ext_hasta = _rango(movs, "fecha")

    # ── solapan_fechas (si falta algún dato → True, no alarmar) ─────
    if None in (plan_desde, plan_hasta, ext_desde, ext_hasta):
        solapan = True
    else:
        solapan = plan_desde <= ext_hasta and ext_desde <= plan_hasta

    return {
        "banco_trae_identidad": banco_trae_identidad,
        "cobertura_montos": {"en_extracto": en_extracto, "total": total},
        "periodo_planilla": {"desde": plan_desde, "hasta": plan_hasta},
        "periodo_extracto": {"desde": ext_desde, "hasta": ext_hasta},
        "solapan_fechas": solapan,
    }


# Config por defecto (org principal — comportamiento original)
CONFIG_DEFAULT_ORG = {
    "match_rules": ["monto_cuit"],
    "tolerancia_monto": 0.01,
    "dias_tolerancia_fecha": 5,  # cubre fin de semana + feriado (vie→lun + 1 dia)
    "estados_habilitados": ["pendiente", "ok", "no está", "duplicado", "faltan datos"],
    "requiere_cierre_periodo": False,
}


def conciliar_planilla(
    db: Session,
    planilla_rows: List[PlanillaRow],
    movimientos: List[MovimientoBanco],
    cliente_nombre: str,
    fecha_acred_str: str,
    org_config: Optional[Dict[str, Any]] = None,
    org_id: int = 1,
    solo_pendientes: bool = False,
    cliente_id: Optional[int] = None,
) -> dict:
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    _ARG = ZoneInfo("America/Argentina/Buenos_Aires")

    config = org_config or CONFIG_DEFAULT_ORG
    estados_habilitados = config.get("estados_habilitados", [])

    procesados = set()
    res = {
        "acreditadas": 0,
        "no_encontradas": 0,
        "duplicadas": 0,
        "sin_datos": 0,
        "filas_procesadas": 0
    }

    # Pre-cargar en procesados todos los movimientos ya asignados a filas "ok"
    # antes de iterar, sin importar el orden de las filas en la planilla.
    if solo_pendientes:
        for row in planilla_rows:
            if row.status == "ok" and row.orden_movimiento_acreditado:
                procesados.add(row.orden_movimiento_acreditado)

    for row in planilla_rows:
        res["filas_procesadas"] += 1
        # Modo re-conciliar: proteger filas ya ok y seguir con las demás
        if solo_pendientes and row.status == "ok":
            res["acreditadas"] += 1
            if row.orden_movimiento_acreditado:
                procesados.add(row.orden_movimiento_acreditado)
            continue
        monto = parse_importe(row.monto)
        if monto is None:
            row.status = "faltan datos"
            res["sin_datos"] += 1
            continue

        # Fecha de la fila (si existe) para scoring
        fecha_fila = getattr(row, 'fecha_acred', None) or None

        mov, status = buscar_match(
            monto=monto,
            cuit_planilla=row.cuit,
            titular_planilla=row.titular,
            referencia_planilla=getattr(row, 'referencia', None),
            fecha_planilla=fecha_fila,
            movimientos=movimientos,
            procesados=procesados,
            org_config=config,
            cliente_nombre=cliente_nombre,
        )

        # ── Nivel 2: consultar patrones aprendidos antes de fallar ──────────
        if status not in ("ok", "no está", "duplicado") and "acreditado" not in status:
            try:
                from app.services.aprendizaje import buscar_por_patrones
                libres_actuales = [m for m in movimientos
                                   if m.id not in procesados
                                   and es_libre(m.cliente_acreditado)
                                   and montos_iguales(m.monto, monto, config.get("tolerancia_monto", 0.01))]
                mov_aprendido = buscar_por_patrones(
                    db=db,
                    org_id=org_id,
                    cliente_nombre=cliente_nombre,
                    monto=monto,
                    cuit=row.cuit,
                    titular=row.titular,
                    referencia=getattr(row, 'referencia', None),
                    movimientos_libres=libres_actuales,
                    procesados=procesados
                )
                if mov_aprendido:
                    mov = mov_aprendido
                    status = "ok (aprendido)"
            except Exception:
                pass

        # Estados ricos: EN_REVISION en vez de "faltan datos" si la org lo habilita
        if status not in ("ok", "ok (aprendido)", "no está", "duplicado") and "acreditado" not in status and "EN_REVISION" in estados_habilitados:
            row.status = "EN_REVISION"
            res["sin_datos"] += 1
            continue

        row.status = status if status != "ok (aprendido)" else "ok"

        if mov:
            mov.cliente_acreditado = cliente_nombre
            if fecha_acred_str.lower() == 'hoy':
                mov.fecha_acred = datetime.now(_ARG).date()
            elif fecha_acred_str.lower() == 'ayer':
                mov.fecha_acred = (datetime.now(_ARG) - timedelta(days=1)).date()
            else:
                try:
                    mov.fecha_acred = datetime.fromisoformat(fecha_acred_str).date()
                except Exception:
                    mov.fecha_acred = datetime.now(_ARG).date()

            row.fecha_acred = mov.fecha_acred or mov.fecha
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

    # Asiento agrupado por planilla: se recomputa el total sobre TODAS las filas
    # ya conciliadas contra movimientos UM (no solo las de esta pasada). Así el
    # upsert refleja el total real en re-conciliaciones y es idempotente —
    # mismo criterio que usa "Empezar limpio" (reset-y-rebuild).
    if cliente_id and planilla_rows:
        try:
            um_mov_ids = {m.id for m in movimientos if getattr(m, "source", None) == "um"}
            total_um = Decimal("0")
            fecha_ref = None
            for r in planilla_rows:
                if (r.status or "") == "ok" and getattr(r, "orden_movimiento_acreditado", None) in um_mov_ids:
                    total_um += abs(Decimal(str(r.monto or 0)))
                    rf = getattr(r, "fecha_acred", None)
                    if rf and (fecha_ref is None or rf > fecha_ref):
                        fecha_ref = rf
            if total_um > 0:
                from app.services.motor_contable import registrar_reclasificacion_planilla
                from app.services.tz import hoy_art as _hoy_art
                planilla_id = planilla_rows[0].planilla_id
                nombre_archivo = ""
                try:
                    if getattr(planilla_rows[0], "planilla", None):
                        nombre_archivo = planilla_rows[0].planilla.nombre_archivo or ""
                except Exception:
                    pass
                registrar_reclasificacion_planilla(
                    db=db,
                    planilla_id=planilla_id,
                    org_id=org_id,
                    usuario_id=None,
                    cliente_id=cliente_id,
                    cliente_nombre=cliente_nombre,
                    total_monto=total_um,
                    fecha=fecha_ref or _hoy_art(),
                    nombre_archivo=nombre_archivo,
                )
        except Exception as _ex:
            import logging
            logging.getLogger(__name__).warning("Error asiento agrupado planilla: %s", _ex)

    db.commit()
    return res
