"""
Algoritmo de conciliacion bancaria — version mejorada.
Soporta configuracion por organizacion (multi-tenant).
Caneland sigue usando el algoritmo original (monto + CUIT/titular).
"""

import re
from typing import List, Optional, Tuple, Dict, Any
from datetime import date
from sqlalchemy.orm import Session
from app.models.extracto import MovimientoBanco
from app.models.planilla import PlanillaRow

# Umbral base: si un monto aparece >= N veces requiere validacion de identidad
UMBRAL_BASE = 3


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
    org_config: Dict[str, Any]
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
    libres    = [m for m in no_usados  if es_libre(m.cliente_acreditado)]

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


# Config por defecto (Caneland — comportamiento original)
CONFIG_CANELAND = {
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
) -> dict:
    from datetime import datetime, timedelta

    config = org_config or CONFIG_CANELAND
    estados_habilitados = config.get("estados_habilitados", [])

    procesados = set()
    res = {
        "acreditadas": 0,
        "no_encontradas": 0,
        "duplicadas": 0,
        "sin_datos": 0,
        "filas_procesadas": 0
    }

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
            org_config=config
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
                mov.fecha_acred = datetime.now().date()
            elif fecha_acred_str.lower() == 'ayer':
                mov.fecha_acred = (datetime.now() - timedelta(days=1)).date()
            else:
                try:
                    mov.fecha_acred = datetime.fromisoformat(fecha_acred_str).date()
                except Exception:
                    mov.fecha_acred = datetime.now().date()

            row.fecha_acred = mov.fecha_acred
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
