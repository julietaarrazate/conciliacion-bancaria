"""Conciliación en grupos: un movimiento ↔ varias filas (A) y varios movimientos ↔ una fila (B).

Corre DESPUÉS de la pasada 1:1 de `conciliacion.conciliar_planilla`, solo sobre lo
que quedó sin conciliar. Reglas (BUSINESS_RULES.md §1.10):

- A: para cada movimiento libre (crédito, sin cliente, no usado), se buscan filas
  sin conciliar de la MISMA planilla cuya suma da el monto del movimiento (con la
  tolerancia de la org). B es el espejo: una fila contra varios movimientos.
- Cada candidato necesita apoyo: identidad (CUIT/CBU/números/titular, mismas
  reglas que el scoring 1:1) o fecha cercana. Fuera de la ventana de fechas no
  entra aunque coincida la identidad.
- Búsqueda acotada: máximo 6 items por grupo, 20 candidatos por objetivo (los de
  más apoyo) y un presupuesto total de nodos por corrida.
- Nunca se confirma solo un grupo ambiguo. Lo encontrado queda "sugerido" (filas
  en SUGERIDO_GRUPO) y lo confirma una persona. Solo si la org activa
  `auto_confirmar_grupos` y la combinación es única y TODAS las filas comparten el
  CUIT del movimiento, el motor lo confirma.
- Una combinación descartada (o deshecha) no se vuelve a sugerir.

Plata: todo en Decimal. Las filas de un grupo no usan
`orden_movimiento_acreditado`; la contabilidad suma los grupos confirmados por
el monto de sus movimientos (`totales_grupos_por_origen`).
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from sqlalchemy.orm import Session

from app.models.conciliacion_grupo import (
    ESTADOS_GRUPO_ACTIVOS,
    GRUPO_CONFIRMADO,
    GRUPO_DESCARTADO,
    GRUPO_SUGERIDO,
    ConciliacionGrupo,
    ConciliacionGrupoItem,
)
from app.models.extracto import MovimientoBanco
from app.models.planilla import SUGERIDO_GRUPO, PlanillaRow
from app.services.conciliacion import _score_identidad, es_libre
from app.services.extractores import extraer_cbu, extraer_cuit, norm_cuit, numeros_de_planilla

logger = logging.getLogger(__name__)

MAX_ITEMS_GRUPO = 6          # filas (A) o movimientos (B) por grupo automático
MAX_CANDIDATOS = 20          # candidatos por objetivo, los de más apoyo
MAX_SOLUCIONES = 10          # combinaciones que se juntan para ver si hay ambigüedad
PRESUPUESTO_NODOS = 200_000  # nodos de búsqueda por corrida de conciliación
VENTANA_MIN_DIAS = 5         # ventana de fechas mínima para el apoyo por fecha
MAX_ITEMS_MANUAL = 100       # tope de filas/movimientos en un grupo armado a mano

ESTADO_OK = "ok"
ESTADO_DIFERENCIA = "CONCILIADO_CON_DIFERENCIA"

# Estados de fila que cuentan como "sin conciliar" para buscar grupos.
_PREFIJOS_SIN_CONCILIAR = ("no está", "no esta", "no coincide", "ambiguo", "sin datos", "pendiente", "EN_REVISION")

_CERO = Decimal("0")


class GrupoError(ValueError):
    """Error de validación al armar/confirmar/deshacer un grupo (mensaje para la UI)."""

    def __init__(self, mensaje: str, status_code: int = 400):
        super().__init__(mensaje)
        self.status_code = status_code


# ── Helpers de monto / fecha / identidad ─────────────────────────────────────

def _dec(v) -> Decimal:
    if v is None:
        return _CERO
    return v if isinstance(v, Decimal) else Decimal(str(v))


def tolerancia_de(config: Optional[dict]) -> Decimal:
    return Decimal(str((config or {}).get("tolerancia_monto", 0.01) or 0.01))


def cuadra(a: Decimal, b: Decimal, tol: Decimal) -> bool:
    """Mismo criterio que `montos_iguales` (estrictamente menor que la tolerancia), en Decimal."""
    return abs(_dec(a) - _dec(b)) < tol


def _ventana(config: Optional[dict]) -> int:
    return max(int((config or {}).get("dias_tolerancia_fecha", 0) or 0), VENTANA_MIN_DIAS)


def _dias(a: Optional[date], b: Optional[date]) -> Optional[int]:
    if not a or not b:
        return None
    if isinstance(a, datetime):
        a = a.date()
    if isinstance(b, datetime):
        b = b.date()
    return abs((a - b).days)


def _identidad(row: PlanillaRow, mov: MovimientoBanco) -> int:
    """Score de identidad fila↔movimiento SIN bonus de fecha (mismas reglas que el 1:1)."""
    cuit_plan = norm_cuit(row.cuit or '')
    if not cuit_plan and row.titular:
        cuit_plan = extraer_cuit(row.titular)
    cbu_plan = extraer_cbu(row.titular or '') or extraer_cbu(row.cuit or '')
    nums = numeros_de_planilla(row.cuit, row.titular, getattr(row, "referencia", None))
    return _score_identidad(cuit_plan, cbu_plan, row.titular or '', nums, mov, None, 0)


def cuit_coincide(row: PlanillaRow, mov: MovimientoBanco) -> bool:
    """Identidad fuerte: el CUIT completo (10-11 dígitos) de la fila está en el movimiento."""
    cuit_plan = norm_cuit(row.cuit or '') or extraer_cuit(row.titular or '')
    if len(cuit_plan) < 10:
        return False
    return _score_identidad(cuit_plan, '', '', set(), mov, None, 0) == 12


def _apoyo(row: PlanillaRow, mov: MovimientoBanco, ventana: int) -> Optional[int]:
    """Cuánto apoya que la fila y el movimiento vayan juntos. None = no candidato.

    Identidad pesa más que la fecha. Fuera de la ventana de fechas no hay apoyo
    (aunque coincida la identidad): un grupo junta pagos del mismo momento."""
    delta = _dias(getattr(row, "fecha", None), mov.fecha)
    if delta is not None and delta > ventana:
        return None
    ident = _identidad(row, mov)
    cercania = (ventana - delta + 1) if delta is not None else 0
    if ident > 0:
        return ident * 100 + cercania
    if delta is not None:
        return cercania
    return None


def fila_sin_conciliar(row: PlanillaRow) -> bool:
    if row.orden_movimiento_acreditado:
        return False
    s = (row.status or "").strip()
    return any(s.startswith(p) for p in _PREFIJOS_SIN_CONCILIAR)


# ── Búsqueda de subconjuntos (subset-sum acotado) ────────────────────────────

class _Presupuesto:
    def __init__(self, nodos: int):
        self.nodos = nodos

    @property
    def agotado(self) -> bool:
        return self.nodos <= 0


def buscar_subconjuntos(
    objetivo: Decimal,
    candidatos: Sequence[Tuple[object, Decimal, int]],
    tol: Decimal,
    max_items: int = MAX_ITEMS_GRUPO,
    presupuesto: Optional[_Presupuesto] = None,
    max_soluciones: int = MAX_SOLUCIONES,
) -> Tuple[List[Tuple[int, ...]], bool]:
    """Combinaciones de 2..max_items candidatos cuya suma cuadra con `objetivo`.

    `candidatos`: (item, monto > 0, apoyo). Devuelve (índices de cada solución
    sobre `candidatos`, se_corto) — `se_corto` = se agotó el presupuesto o se
    llegó a `max_soluciones`, o sea que puede haber más combinaciones."""
    presupuesto = presupuesto or _Presupuesto(PRESUPUESTO_NODOS)
    orden = sorted(range(len(candidatos)), key=lambda i: candidatos[i][1], reverse=True)
    montos = [candidatos[i][1] for i in orden]
    sufijo = [_CERO] * (len(montos) + 1)
    for i in range(len(montos) - 1, -1, -1):
        sufijo[i] = sufijo[i + 1] + montos[i]

    soluciones: List[Tuple[int, ...]] = []
    cortado = False

    def dfs(inicio: int, resto: Decimal, elegidos: List[int]) -> None:
        nonlocal cortado
        if cortado:
            return
        presupuesto.nodos -= 1
        if presupuesto.agotado:
            cortado = True
            return
        if len(elegidos) >= 2 and abs(resto) < tol:
            soluciones.append(tuple(sorted(orden[j] for j in elegidos)))
            if len(soluciones) >= max_soluciones:
                cortado = True
            return
        if len(elegidos) >= max_items:
            return
        for j in range(inicio, len(montos)):
            if sufijo[j] < resto - tol:   # ni sumando todo lo que queda llega
                return
            if montos[j] - resto >= tol:  # se pasa
                continue
            elegidos.append(j)
            dfs(j + 1, resto - montos[j], elegidos)
            elegidos.pop()
            if cortado:
                return

    dfs(0, _dec(objetivo), [])
    return soluciones, cortado


def _elegir(
    soluciones: List[Tuple[int, ...]],
    candidatos: Sequence[Tuple[object, Decimal, int]],
    cortado: bool,
) -> Tuple[Optional[Tuple[int, ...]], bool]:
    """(mejor solución, ambigua). None si hay empate en el apoyo (no se adivina)."""
    if not soluciones:
        return None, False
    if len(soluciones) == 1 and not cortado:
        return soluciones[0], False
    puntaje = sorted(
        ((sum(candidatos[i][2] for i in s), s) for s in soluciones),
        key=lambda x: x[0], reverse=True,
    )
    if len(puntaje) > 1 and puntaje[0][0] == puntaje[1][0]:
        return None, True
    return puntaje[0][1], True


# ── Consultas ────────────────────────────────────────────────────────────────

def grupos_activos_de_planilla(db: Session, planilla_id: int) -> List[ConciliacionGrupo]:
    return (
        db.query(ConciliacionGrupo)
        .filter(ConciliacionGrupo.planilla_id == planilla_id,
                ConciliacionGrupo.estado.in_(ESTADOS_GRUPO_ACTIVOS))
        .order_by(ConciliacionGrupo.id)
        .all()
    )


def grupo_por_fila(db: Session, row_ids: Iterable[int]) -> Dict[int, ConciliacionGrupo]:
    """{row_id: grupo activo} para las filas dadas (una query)."""
    ids = list({i for i in row_ids if i})
    if not ids:
        return {}
    pares = (
        db.query(ConciliacionGrupoItem.planilla_row_id, ConciliacionGrupo)
        .join(ConciliacionGrupo, ConciliacionGrupoItem.grupo_id == ConciliacionGrupo.id)
        .filter(ConciliacionGrupoItem.planilla_row_id.in_(ids),
                ConciliacionGrupo.estado.in_(ESTADOS_GRUPO_ACTIVOS))
        .all()
    )
    return {rid: g for rid, g in pares}


def movimientos_en_grupos_activos(db: Session, org_id: int, mov_ids: Optional[Iterable[int]] = None) -> set:
    q = (
        db.query(ConciliacionGrupoItem.movimiento_id)
        .join(ConciliacionGrupo, ConciliacionGrupoItem.grupo_id == ConciliacionGrupo.id)
        .filter(ConciliacionGrupo.organizacion_id == org_id,
                ConciliacionGrupo.estado.in_(ESTADOS_GRUPO_ACTIVOS),
                ConciliacionGrupoItem.movimiento_id.isnot(None))
    )
    if mov_ids is not None:
        ids = list(mov_ids)
        if not ids:
            return set()
        q = q.filter(ConciliacionGrupoItem.movimiento_id.in_(ids))
    return {m for (m,) in q.all()}


def _ids_items(grupo: ConciliacionGrupo) -> Tuple[List[int], List[int]]:
    filas = [it.planilla_row_id for it in grupo.items if it.planilla_row_id]
    movs = [it.movimiento_id for it in grupo.items if it.movimiento_id]
    return filas, movs


def filas_y_movimientos(db: Session, grupo: ConciliacionGrupo) -> Tuple[List[PlanillaRow], List[MovimientoBanco]]:
    fila_ids, mov_ids = _ids_items(grupo)
    filas = db.query(PlanillaRow).filter(PlanillaRow.id.in_(fila_ids)).order_by(PlanillaRow.id).all() if fila_ids else []
    movs = (db.query(MovimientoBanco).filter(MovimientoBanco.id.in_(mov_ids))
            .order_by(MovimientoBanco.fecha, MovimientoBanco.id).all()) if mov_ids else []
    return filas, movs


def _firmas_descartadas(db: Session, planilla_id: int) -> set:
    grupos = (
        db.query(ConciliacionGrupo)
        .filter(ConciliacionGrupo.planilla_id == planilla_id, ConciliacionGrupo.estado == GRUPO_DESCARTADO)
        .all()
    )
    firmas = set()
    for g in grupos:
        f, m = _ids_items(g)
        firmas.add((frozenset(f), frozenset(m)))
    return firmas


def borrar_sugeridos(db: Session, planilla_id: int) -> int:
    """Borra las sugerencias pendientes de la planilla (se recalculan en cada
    conciliación). Las filas sugeridas vuelven a "pendiente" para que la pasada 1:1
    las procese de nuevo. Los confirmados y descartados no se tocan."""
    sugeridos = (
        db.query(ConciliacionGrupo)
        .filter(ConciliacionGrupo.planilla_id == planilla_id, ConciliacionGrupo.estado == GRUPO_SUGERIDO)
        .all()
    )
    for g in sugeridos:
        fila_ids, _ = _ids_items(g)
        if fila_ids:
            for row in db.query(PlanillaRow).filter(PlanillaRow.id.in_(fila_ids)).all():
                if row.status == SUGERIDO_GRUPO:
                    row.status = "pendiente"
        db.delete(g)
    if sugeridos:
        db.flush()
    return len(sugeridos)


# ── Crear / confirmar / deshacer ─────────────────────────────────────────────

def _nuevo_grupo(
    db: Session,
    planilla_id: int,
    org_id: int,
    filas: Sequence[PlanillaRow],
    movs: Sequence[MovimientoBanco],
    origen: str,
    ambiguo: bool = False,
    usuario_id: Optional[int] = None,
) -> ConciliacionGrupo:
    total_filas = sum((_dec(r.monto) for r in filas), _CERO)
    total_movs = sum((_dec(m.monto) for m in movs), _CERO)
    g = ConciliacionGrupo(
        organizacion_id=org_id, planilla_id=planilla_id, estado=GRUPO_SUGERIDO, origen=origen,
        total_filas=total_filas, total_movimientos=total_movs, diferencia=total_movs - total_filas,
        ambiguo=ambiguo, creado_por=usuario_id,
    )
    for r in filas:
        g.items.append(ConciliacionGrupoItem(organizacion_id=org_id, planilla_row_id=r.id, monto=_dec(r.monto)))
    for m in movs:
        g.items.append(ConciliacionGrupoItem(organizacion_id=org_id, movimiento_id=m.id, monto=_dec(m.monto)))
    db.add(g)
    for r in filas:
        r.status = SUGERIDO_GRUPO
        r.orden_movimiento_acreditado = None
    db.flush()
    return g


def confirmar(
    db: Session,
    grupo: ConciliacionGrupo,
    cliente_nombre: str,
    tol: Decimal,
    fecha_acred: Optional[date] = None,
) -> ConciliacionGrupo:
    """Confirma un grupo: filas en "ok" (o CONCILIADO_CON_DIFERENCIA si no cuadra)
    y movimientos acreditados al cliente. Sin commit."""
    filas, movs = filas_y_movimientos(db, grupo)
    total_filas = sum((_dec(r.monto) for r in filas), _CERO)
    total_movs = sum((_dec(m.monto) for m in movs), _CERO)
    estado_fila = ESTADO_OK if cuadra(total_filas, total_movs, tol) else ESTADO_DIFERENCIA
    for m in movs:
        m.cliente_acreditado = cliente_nombre
        m.fecha_acred = m.fecha_acred or fecha_acred or m.fecha
    fecha_fila = max((m.fecha_acred or m.fecha for m in movs if (m.fecha_acred or m.fecha)), default=fecha_acred)
    for r in filas:
        r.status = estado_fila
        r.orden_movimiento_acreditado = None
        r.fecha_acred = fecha_fila
        r.monto_acreditado = total_movs if len(filas) == 1 else None
    grupo.total_filas = total_filas
    grupo.total_movimientos = total_movs
    grupo.diferencia = total_movs - total_filas
    grupo.estado = GRUPO_CONFIRMADO
    grupo.confirmado_at = datetime.utcnow()
    db.flush()
    return grupo


def deshacer(db: Session, grupo: ConciliacionGrupo, cliente_nombre: str) -> ConciliacionGrupo:
    """Deshace un grupo confirmado o descarta uno sugerido. Las filas vuelven a
    "pendiente"; los movimientos se liberan (solo si seguían acreditados a este
    cliente). El grupo queda "descartado" para que no se vuelva a sugerir. Sin commit."""
    if grupo.estado not in ESTADOS_GRUPO_ACTIVOS:
        raise GrupoError("Este grupo ya estaba deshecho", 409)
    filas, movs = filas_y_movimientos(db, grupo)
    era_confirmado = grupo.estado == GRUPO_CONFIRMADO
    for r in filas:
        if r.status in (ESTADO_OK, ESTADO_DIFERENCIA, SUGERIDO_GRUPO):
            r.status = "pendiente"
        r.fecha_acred = None
        r.monto_acreditado = None
    if era_confirmado:
        nombre = (cliente_nombre or "").strip().lower()
        for m in movs:
            if (m.cliente_acreditado or "").strip().lower() == nombre:
                m.cliente_acreditado = None
                m.fecha_acred = None
    grupo.estado = GRUPO_DESCARTADO
    db.flush()
    return grupo


def crear_grupo_manual(
    db: Session,
    planilla,
    movimientos_extracto: Sequence[MovimientoBanco],
    row_ids: Sequence[int],
    mov_ids: Sequence[int],
    config: Optional[dict],
    usuario_id: Optional[int],
    con_diferencia: bool = False,
) -> ConciliacionGrupo:
    """Arma y confirma un grupo elegido a mano. Valida todo y levanta GrupoError."""
    org_id = planilla.organizacion_id or 1
    row_ids = list(dict.fromkeys(int(i) for i in row_ids or []))
    mov_ids = list(dict.fromkeys(int(i) for i in mov_ids or []))
    if not row_ids or not mov_ids:
        raise GrupoError("Elegí al menos una fila y un movimiento")
    if len(row_ids) > 1 and len(mov_ids) > 1:
        raise GrupoError("Un grupo es varias filas contra UN movimiento, o UNA fila contra varios movimientos")
    if len(row_ids) + len(mov_ids) < 3:
        raise GrupoError("Para una fila contra un movimiento usá \"Asignar movimiento\" (🔗)")
    if len(row_ids) > MAX_ITEMS_MANUAL or len(mov_ids) > MAX_ITEMS_MANUAL:
        raise GrupoError(f"Un grupo puede tener hasta {MAX_ITEMS_MANUAL} filas o movimientos")

    filas = (
        db.query(PlanillaRow)
        .filter(PlanillaRow.id.in_(row_ids), PlanillaRow.planilla_id == planilla.id)
        .all()
    )
    if len(filas) != len(row_ids):
        raise GrupoError("Alguna fila no es de esta planilla", 404)
    ya_en_grupo = grupo_por_fila(db, row_ids)
    if ya_en_grupo:
        raise GrupoError("Alguna fila ya está en un grupo: confirmalo o deshacelo primero", 409)
    for r in filas:
        if r.orden_movimiento_acreditado or r.status in (ESTADO_OK, ESTADO_DIFERENCIA):
            raise GrupoError("Alguna fila ya está conciliada. Cambiale el estado antes de agruparla", 409)
        if _dec(r.monto) <= 0:
            raise GrupoError("Las filas del grupo tienen que tener un monto mayor a cero")

    por_id = {m.id: m for m in movimientos_extracto}
    movs = [por_id.get(i) for i in mov_ids]
    if any(m is None for m in movs):
        raise GrupoError("Algún movimiento no es del extracto de esta planilla", 404)
    if any((m.organizacion_id or 1) != org_id for m in movs):
        raise GrupoError("Algún movimiento no es del extracto de esta planilla", 404)
    for m in movs:
        if _dec(m.monto) <= 0:
            raise GrupoError("Solo se agrupan créditos (movimientos con monto positivo)")
        if not es_libre(m.cliente_acreditado):
            raise GrupoError(f"Un movimiento ya está acreditado a {m.cliente_acreditado}", 409)
    if movimientos_en_grupos_activos(db, org_id, mov_ids):
        raise GrupoError("Algún movimiento ya está en otro grupo", 409)
    usados = db.query(PlanillaRow.id).filter(PlanillaRow.orden_movimiento_acreditado.in_(mov_ids)).first()
    if usados:
        raise GrupoError("Algún movimiento ya está conciliado con otra fila", 409)

    tol = tolerancia_de(config)
    total_filas = sum((_dec(r.monto) for r in filas), _CERO)
    total_movs = sum((_dec(m.monto) for m in movs), _CERO)
    if not cuadra(total_filas, total_movs, tol) and not con_diferencia:
        raise GrupoError(
            f"No cuadra: las filas suman {total_filas} y los movimientos {total_movs} "
            f"(diferencia {total_movs - total_filas}). Para conciliarlo igual, confirmalo como "
            "\"conciliado con diferencia\"."
        )
    grupo = _nuevo_grupo(db, planilla.id, org_id, filas, movs, origen="manual", usuario_id=usuario_id)
    return confirmar(db, grupo, planilla.cliente.nombre, tol)


# ── Sugerencias automáticas ──────────────────────────────────────────────────

def sugerir_grupos(
    db: Session,
    planilla_id: int,
    org_id: int,
    rows: Sequence[PlanillaRow],
    movimientos: Sequence[MovimientoBanco],
    procesados: set,
    config: Optional[dict],
    cliente_nombre: str,
    fecha_acred: Optional[date] = None,
) -> Dict[str, int]:
    """Busca grupos A y B entre lo que quedó sin conciliar y los deja sugeridos
    (o confirmados, si la org lo habilita y es seguro). Sin commit."""
    res = {"grupos_sugeridos": 0, "grupos_confirmados": 0}
    tol = tolerancia_de(config)
    ventana = _ventana(config)
    auto = bool((config or {}).get("auto_confirmar_grupos", False))
    presupuesto = _Presupuesto(PRESUPUESTO_NODOS)

    rows = [r for r in rows if getattr(r, "id", None)]
    en_grupo = set(grupo_por_fila(db, [r.id for r in rows]).keys())
    filas = [
        r for r in rows
        if r.id not in en_grupo and fila_sin_conciliar(r) and _dec(r.monto) > 0
    ]
    mov_ocupados = movimientos_en_grupos_activos(db, org_id, [m.id for m in movimientos])
    movs = [
        m for m in movimientos
        if _dec(m.monto) > 0 and m.id not in procesados and m.id not in mov_ocupados
        and es_libre(m.cliente_acreditado)
    ]
    if len(filas) < 1 or len(movs) < 1 or len(filas) + len(movs) < 3:
        return res
    descartadas = _firmas_descartadas(db, planilla_id)

    filas_libres = {r.id: r for r in filas}
    movs_libres = {m.id: m for m in movs}

    def _registrar(filas_g, movs_g, unica, ambigua, fuerte):
        g = _nuevo_grupo(db, planilla_id, org_id, filas_g, movs_g, origen="auto", ambiguo=ambigua)
        if auto and unica and fuerte:
            confirmar(db, g, cliente_nombre, tol, fecha_acred)
            for m in movs_g:
                procesados.add(m.id)
            res["grupos_confirmados"] += 1
        else:
            res["grupos_sugeridos"] += 1
        for r in filas_g:
            filas_libres.pop(r.id, None)
        for m in movs_g:
            movs_libres.pop(m.id, None)

    # A: un movimiento ↔ varias filas
    for mov in sorted(movs, key=lambda m: (m.fecha or date.min, m.id)):
        if presupuesto.agotado:
            break
        if mov.id not in movs_libres:
            continue
        objetivo = _dec(mov.monto)
        cands = []
        for r in filas_libres.values():
            monto = _dec(r.monto)
            if not monto < objetivo:
                continue
            ap = _apoyo(r, mov, ventana)
            if ap is not None:
                cands.append((r, monto, ap))
        if len(cands) < 2:
            continue
        cands.sort(key=lambda c: (-c[2], c[0].id))
        cands = cands[:MAX_CANDIDATOS]
        sols, cortado = buscar_subconjuntos(objetivo, cands, tol, MAX_ITEMS_GRUPO, presupuesto)
        sols = [s for s in sols if (frozenset(cands[i][0].id for i in s), frozenset([mov.id])) not in descartadas]
        mejor, ambigua = _elegir(sols, cands, cortado)
        if mejor is None:
            continue
        filas_g = [cands[i][0] for i in mejor]
        fuerte = all(cuit_coincide(r, mov) for r in filas_g)
        _registrar(filas_g, [mov], unica=not ambigua, ambigua=ambigua, fuerte=fuerte)

    # B: una fila ↔ varios movimientos
    for row in sorted(list(filas_libres.values()), key=lambda r: r.id):
        if presupuesto.agotado:
            break
        if row.id not in filas_libres:
            continue
        objetivo = _dec(row.monto)
        cands = []
        for m in movs_libres.values():
            monto = _dec(m.monto)
            if not monto < objetivo:
                continue
            ap = _apoyo(row, m, ventana)
            if ap is not None:
                cands.append((m, monto, ap))
        if len(cands) < 2:
            continue
        cands.sort(key=lambda c: (-c[2], c[0].id))
        cands = cands[:MAX_CANDIDATOS]
        sols, cortado = buscar_subconjuntos(objetivo, cands, tol, MAX_ITEMS_GRUPO, presupuesto)
        sols = [s for s in sols if (frozenset([row.id]), frozenset(cands[i][0].id for i in s)) not in descartadas]
        mejor, ambigua = _elegir(sols, cands, cortado)
        if mejor is None:
            continue
        movs_g = [cands[i][0] for i in mejor]
        fuerte = all(cuit_coincide(row, m) for m in movs_g)
        _registrar([row], movs_g, unica=not ambigua, ambigua=ambigua, fuerte=fuerte)

    if presupuesto.agotado:
        logger.info("sugerir_grupos: presupuesto de búsqueda agotado (planilla %s)", planilla_id)
    return res


# ── Contabilidad ─────────────────────────────────────────────────────────────

def totales_grupos_por_origen(db: Session, planilla_id: int) -> Dict[str, Tuple[Decimal, Optional[date]]]:
    """Plata conciliada por grupos confirmados de la planilla, por origen del
    movimiento ("extracto" | "um"): (total de los movimientos, fecha más reciente).

    Se suma el monto de los MOVIMIENTOS (lo que entró al banco y quedó en No
    identificado 2-1-1-1), no el de las filas: en un grupo con diferencia, la
    reclasificación cancela exactamente lo que acreditó el banco. Cada
    movimiento va a su bucket, así un grupo que mezcla extracto y UM reparte bien."""
    out: Dict[str, Tuple[Decimal, Optional[date]]] = {}
    filas = (
        db.query(MovimientoBanco.monto, MovimientoBanco.source, MovimientoBanco.fecha_acred, MovimientoBanco.fecha)
        .join(ConciliacionGrupoItem, ConciliacionGrupoItem.movimiento_id == MovimientoBanco.id)
        .join(ConciliacionGrupo, ConciliacionGrupoItem.grupo_id == ConciliacionGrupo.id)
        .filter(ConciliacionGrupo.planilla_id == planilla_id, ConciliacionGrupo.estado == GRUPO_CONFIRMADO)
        .all()
    )
    for monto, source, f_acred, f_mov in filas:
        origen = "um" if source == "um" else "extracto"
        total, fecha = out.get(origen, (_CERO, None))
        f = f_acred or f_mov
        out[origen] = (total + abs(_dec(monto)), max(fecha, f) if (fecha and f) else (fecha or f))
    return out


def serializar_grupo(grupo: ConciliacionGrupo, movs: Sequence[MovimientoBanco], n_filas: int) -> dict:
    return {
        "id": grupo.id,
        "estado": grupo.estado,
        "origen": grupo.origen,
        "ambiguo": bool(grupo.ambiguo),
        "n_filas": n_filas,
        "total_filas": _dec(grupo.total_filas),
        "total_movimientos": _dec(grupo.total_movimientos),
        "diferencia": _dec(grupo.diferencia),
        "movimientos": [
            {"id": m.id, "orden": m.orden, "fecha": m.fecha, "titular": m.titular, "monto": _dec(m.monto)}
            for m in movs
        ],
    }
