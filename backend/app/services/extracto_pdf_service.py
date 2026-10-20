"""Importador de extractos bancarios en PDF: borradores, duplicados, confirmación y aprendizaje.

Flujo:

1. `importar_pdf` — valida el archivo, lee el PDF con las capas deterministas
   (formato aprendido → lectura automática) y guarda un **borrador**. Si la lectura
   no alcanza (no hay filas o el saldo no cierra) y la IA está configurada, el
   borrador queda `procesando` y `procesar_en_fondo` lo relee con IA en segundo
   plano. Nada toca `extractos_bancarios` todavía.
2. `borrador_out` — lo que ve la pantalla de revisión: filas, cuadre de saldos,
   alertas y si ya hay un extracto con esos movimientos (`duplicado`).
3. `confirmar_borrador` — valida las filas que confirmó la persona, recalcula el
   cuadre con la MISMA función que el lector (`validar_saldos`) y:
     - destino `nuevo`: crea el extracto con el mismo código que el upload de Excel
       (`crear_extracto_con_movimientos`), o lo vincula si ya existía;
     - destino `existente`: agrega solo los movimientos nuevos con el merge de UM
       (`mergear_movimientos`) y su asiento (`registrar_asiento_um`).
   Es idempotente: la transición `listo → confirmando` es atómica y un borrador
   `confirmado` devuelve el resultado guardado.
4. Aprendizaje — si la lectura fue buena (cierra y se corrigió ≤ 10 % de las filas)
   se guarda o refuerza el **formato aprendido** (molde) de la organización, para
   leer ese banco sin IA la próxima vez.

El lector (`app.services.extracto_pdf`) se importa de forma diferida: este módulo no
depende de él para importar, y los tests lo reemplazan con `lector` / `validador_saldos`.

Dinero en Decimal de punta a punta; en el JSON del borrador y de la API, string
con dos decimales (`"-1234.56"`).
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
from collections import Counter
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Callable, Optional

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.extracto import ExtractoBancario, MovimientoBanco
from app.models.extracto_pdf import (
    ESTADOS_BORRADOR_PDF, ESTADOS_PENDIENTES_PDF, ORIGENES_MOLDE,
    BorradorExtractoPdf, MoldeExtractoPdf,
)
from app.services.auditoria import registrar_log
from app.services.cierre_periodo import periodo_esta_cerrado
from app.services.extracto_import import (
    crear_extracto_con_movimientos, fingerprint, nombre_banco, registrar_asiento_um, resolver_banco,
)
from app.services.extracto_merger import _normalizar_titular, mergear_movimientos
from app.services.tz import hoy_art

logger = logging.getLogger(__name__)

CENT = Decimal("0.01")
# movimientos_banco.monto / saldo son NUMERIC(12,2): |x| < 10^10.
TOPE_MOVIMIENTO = Decimal("10000000000")
# Saldos del borrador: NUMERIC(16,2).
TOPE_SALDO_BORRADOR = Decimal("100000000000000")
MAX_MOVIMIENTOS = 5000
MAX_DESCRIPCION = 500
MINUTOS_COLGADO = 10
UMBRAL_CAMBIOS_APRENDIZAJE = Decimal("0.10")
MAX_EXTRACTOS_SOLAPADO = 10
# Extractos con fechas que se pisan con las del PDF que se comparan (activos o archivados).
MAX_EXTRACTOS_POR_FECHA = 30
MAX_MOLDES_LECTOR = 200
# Mismo default que el upload de Excel (`banco` del query) → `resolver_banco` igual.
BANCO_DEFAULT = "Banco Macro"
METODOS = ("molde", "automatico", "ia")
MSG_COLGADO = "Se interrumpió la lectura: volvé a subir el PDF"
MSG_ERROR_LECTURA = "No se pudo leer el PDF. Probá de nuevo o cargá los movimientos a mano."


class ExtractoPdfServicioError(Exception):
    """Error de negocio con status HTTP (el router lo traduce a HTTPException)."""

    def __init__(self, mensaje: str, status: int = 400):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.status = status


# ── Costuras inyectables (tests) ─────────────────────────────────────

# (contenido, *, moldes, usar_ia, forzar_ia, hoy) -> ResultadoLectura. None = lector real.
lector: Optional[Callable[..., dict]] = None
# (movimientos, *, orden, saldo_inicial, saldo_final) -> cuadre. None = validar_saldos real.
validador_saldos: Optional[Callable[..., dict]] = None


def _ia_configurada_default() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY", "").strip())


# () -> bool: hay IA para releer (feature flag GEMINI_API_KEY, ADR-008).
ia_configurada: Callable[[], bool] = _ia_configurada_default


def _lector() -> Callable[..., dict]:
    if lector is not None:
        return lector
    from app.services.extracto_pdf import leer_extracto_pdf
    return leer_extracto_pdf


def _validar_saldos(movimientos: list[dict], *, orden: str, saldo_inicial: Optional[Decimal],
                    saldo_final: Optional[Decimal]) -> dict:
    fn = validador_saldos
    if fn is None:
        from app.services.extracto_pdf.saldos import validar_saldos as fn
    return fn(movimientos, orden=orden, saldo_inicial=saldo_inicial, saldo_final=saldo_final)


def _error_de_lectura(ex: Exception) -> Optional[ExtractoPdfServicioError]:
    """Traduce un `ExtractoPdfError` del lector (PDF roto, con clave, demasiadas páginas)."""
    try:
        from app.services.extracto_pdf import ExtractoPdfError
    except ImportError:  # pragma: no cover - el paquete siempre lo exporta en producción
        try:
            from app.services.extracto_pdf.errores import ExtractoPdfError
        except ImportError:
            return None
    if isinstance(ex, ExtractoPdfError):
        mensaje = getattr(ex, "mensaje", None) or str(ex) or "No se pudo leer el PDF."
        return ExtractoPdfServicioError(mensaje, int(getattr(ex, "status", 400) or 400))
    return None


# ── Dinero / fechas / JSON ───────────────────────────────────────────

_RE_CANONICO = re.compile(r"^[+-]?\d+(\.\d{1,2})?$")


def a_dinero(raw: Any) -> Optional[Decimal]:
    """Monto de la API o del lector → Decimal al centavo (None si vacío o inválido).

    `"-1234.56"` / `1234.5` / `Decimal` se toman tal cual; cualquier otro texto
    (`"1.234,56"`, `"$ 1.234,56-"`, …) pasa por `parse_importe_ar`, el parser canónico."""
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, Decimal):
        d = raw
    elif isinstance(raw, (int, float)):
        try:
            d = Decimal(str(raw))
        except InvalidOperation:
            return None
    elif isinstance(raw, str):
        s = raw.strip()
        if not s:
            return None
        if _RE_CANONICO.match(s):
            d = Decimal(s)
        else:
            try:
                from app.services.decimal_utils import parse_importe_ar
            except ImportError:  # pragma: no cover
                logger.error("Falta decimal_utils.parse_importe_ar")
                return None
            d = parse_importe_ar(s)
            if d is None:
                return None
    else:
        return None
    if not d.is_finite():
        return None
    try:
        # Un número con más dígitos que la precisión de Decimal (1E+40) no se
        # puede redondear al centavo: es basura de la lectura, no un importe.
        return d.quantize(CENT, rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None


def dinero_str(d: Optional[Decimal]) -> Optional[str]:
    """Decimal → `"-1234.56"` (sin notación científica, sin `-0.00`)."""
    if d is None:
        return None
    d = d.quantize(CENT, rounding=ROUND_HALF_UP)
    if d == 0:
        d = Decimal("0.00")
    return format(d, "f")


def formato_ar(d: Decimal) -> str:
    """`Decimal("-1234.5")` → `"-1.234,50"` (para mensajes)."""
    d = d.quantize(CENT, rounding=ROUND_HALF_UP)
    s = f"{abs(d):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"-{s}" if d < 0 else s


_FORMATOS_FECHA = ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y")


def a_fecha(raw: Any) -> Optional[date]:
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    if not isinstance(raw, str):
        return None
    s = raw.strip()
    if len(s) > 10 and s[4:5] == "-" and s[10:11] in ("T", " "):
        s = s[:10]
    for fmt in _FORMATOS_FECHA:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _iso(d: Optional[date]) -> Optional[str]:
    return d.isoformat() if d else None


def _json_safe(v: Any) -> Any:
    """Convierte Decimal/fecha/tupla a tipos JSON (para `datos` / `layout`)."""
    if isinstance(v, Decimal):
        return format(v, "f") if v.is_finite() else None
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, float):
        return v if v == v and v not in (float("inf"), float("-inf")) else None
    if isinstance(v, dict):
        return {str(k): _json_safe(x) for k, x in v.items()}
    if isinstance(v, (list, tuple, set)):
        return [_json_safe(x) for x in v]
    if v is None or isinstance(v, (str, int, bool)):
        return v
    return str(v)


def _utcnow() -> datetime:
    # Marcas de tiempo internas en UTC (mismo criterio que creado_at).
    return datetime.utcnow()


# ── Serialización de la lectura ──────────────────────────────────────

_CUADRE_DINERO = ("saldo_inicial", "saldo_final", "total_creditos", "total_debitos",
                  "saldo_final_calculado", "diferencia")
_CUADRE_DEFAULT = {
    "saldo_inicial": None, "saldo_inicial_inferido": False,
    "saldo_final": None, "saldo_final_inferido": False,
    "total_creditos": "0.00", "total_debitos": "0.00", "cantidad": 0,
    "saldo_final_calculado": None, "diferencia": None, "cierra": False, "filas_con_salto": [],
}


def _serializar_movimiento(m: dict) -> dict:
    motivos = m.get("motivos") or []
    pagina = m.get("pagina")
    return {
        "fecha": _iso(a_fecha(m.get("fecha"))),
        "descripcion": str(m.get("descripcion") or "").strip()[:MAX_DESCRIPCION],
        "monto": dinero_str(a_dinero(m.get("monto"))),
        "saldo": dinero_str(a_dinero(m.get("saldo"))),
        "pagina": pagina if isinstance(pagina, int) and not isinstance(pagina, bool) else None,
        "dudosa": bool(m.get("dudosa")),
        "motivos": [str(x) for x in motivos if x] if isinstance(motivos, (list, tuple)) else [str(motivos)],
    }


def serializar_cuadre(c: Optional[dict]) -> dict:
    out = dict(_CUADRE_DEFAULT)
    for k, v in (c or {}).items():
        if k in _CUADRE_DINERO:
            out[k] = dinero_str(a_dinero(v))
        elif k == "filas_con_salto":
            out[k] = [int(i) for i in (v or []) if isinstance(i, int) and not isinstance(i, bool)]
        elif k in ("cierra", "saldo_inicial_inferido", "saldo_final_inferido"):
            out[k] = bool(v)
        elif k == "cantidad":
            out[k] = int(v or 0)
        else:
            out[k] = _json_safe(v)
    if out["total_creditos"] is None:
        out["total_creditos"] = "0.00"
    if out["total_debitos"] is None:
        out["total_debitos"] = "0.00"
    return out


def _alerta(a: Any) -> Optional[dict]:
    if isinstance(a, dict):
        mensaje = str(a.get("mensaje") or "").strip()
        if not mensaje:
            return None
        nivel = a.get("nivel") if a.get("nivel") in ("info", "aviso", "error") else "aviso"
        return {"nivel": nivel, "codigo": str(a.get("codigo") or ""), "mensaje": mensaje}
    if isinstance(a, str) and a.strip():
        return {"nivel": "aviso", "codigo": "", "mensaje": a.strip()}
    return None


def _saldo_borrador(*candidatos: Any) -> Optional[Decimal]:
    for c in candidatos:
        d = a_dinero(c)
        if d is not None:
            return d if abs(d) < TOPE_SALDO_BORRADOR else None
    return None


def _alerta_periodo_cerrado(db: Session, org_id: int, movimientos: list[dict]) -> Optional[dict]:
    """Aviso (no bloqueo) si hay filas en un período cerrado — igual que Excel/UM, que no bloquean."""
    cache: dict[date, bool] = {}
    n = 0
    for m in movimientos:
        f = a_fecha(m.get("fecha"))
        if not f:
            continue
        if f not in cache:
            cache[f] = periodo_esta_cerrado(db, org_id, f)
        if cache[f]:
            n += 1
    if not n:
        return None
    filas = "1 movimiento" if n == 1 else f"{n} movimientos"
    return {"nivel": "aviso", "codigo": "periodo_cerrado",
            "mensaje": f"Hay {filas} con fecha en un período ya cerrado. Se pueden guardar igual; revisá que corresponda."}


def valores_de_lectura(db: Session, org_id: int, res: dict, *, banco_usuario: Optional[str]) -> dict:
    """Resultado del lector → columnas del borrador (todo JSON-safe, dinero en string)."""
    movs = [_serializar_movimiento(m) for m in (res.get("movimientos") or []) if isinstance(m, dict)]
    cuadre = serializar_cuadre(res.get("cuadre"))
    metodo = res.get("metodo") if res.get("metodo") in METODOS else None
    clave = str(res.get("banco_clave") or "generico")[:40]
    molde_id = res.get("molde_id") if metodo == "molde" and isinstance(res.get("molde_id"), int) else None
    fechas = [a_fecha(m["fecha"]) for m in movs if m["fecha"]]
    alertas = [x for x in (_alerta(a) for a in (res.get("alertas") or [])) if x]
    cerrado = _alerta_periodo_cerrado(db, org_id, movs)
    if cerrado:
        alertas.append(cerrado)
    aprendizaje = res.get("aprendizaje")
    return {
        "metodo": metodo,
        "banco_clave": clave,
        "banco": resolver_banco((banco_usuario or "").strip()[:120] or BANCO_DEFAULT, clave)[:120],
        "molde_id": molde_id,
        "periodo_desde": a_fecha(res.get("periodo_desde")) or (min(fechas) if fechas else None),
        "periodo_hasta": a_fecha(res.get("periodo_hasta")) or (max(fechas) if fechas else None),
        "saldo_inicial": _saldo_borrador(res.get("saldo_inicial"), cuadre.get("saldo_inicial")),
        "saldo_final": _saldo_borrador(res.get("saldo_final"), cuadre.get("saldo_final")),
        "datos": {
            "movimientos": movs,
            "orden": "desc" if res.get("orden") == "desc" else "asc",
            "cuadre": cuadre,
            "paginas": int(res.get("paginas") or 0),
            "escaneado": bool(res.get("escaneado")),
            "ia_usada": bool(res.get("ia_usada")),
            "ia_disponible": bool(ia_configurada()),
            "aprendizaje": _json_safe(aprendizaje) if isinstance(aprendizaje, dict) else None,
            "banco_usuario": (banco_usuario or "").strip()[:120] or None,
        },
        "alertas": alertas,
        "error": None,
    }


def _aplicar(b: BorradorExtractoPdf, valores: dict) -> None:
    for k, v in valores.items():
        setattr(b, k, v)


# ── Lectura de filas del borrador / formato del merge ────────────────

def _filas_guardadas(b: BorradorExtractoPdf) -> list[dict]:
    """Filas del borrador (orden del PDF) con Decimal/fecha; omite las que no tienen importe."""
    filas = []
    for m in (b.datos or {}).get("movimientos") or []:
        monto = a_dinero(m.get("monto"))
        if monto is None or monto == 0:
            continue
        filas.append({"fecha": a_fecha(m.get("fecha")), "descripcion": m.get("descripcion") or "",
                      "monto": monto, "saldo": a_dinero(m.get("saldo"))})
    return filas


def a_filas_parser(filas: list[dict], orden: str) -> list[dict]:
    """Filas en el orden mostrado → forma del parser de Excel, **del más reciente al más
    antiguo** (lo que esperan `crear_extracto_con_movimientos` y `mergear_movimientos`).

    No se reordena por fecha: se respeta el orden del PDF (el saldo corrido depende de él)."""
    newest_first = list(reversed(filas)) if orden != "desc" else list(filas)
    out = []
    for f in newest_first:
        fecha = f.get("fecha")
        out.append({
            "orden": None,
            "fecha": fecha,
            "mes": str(fecha.month) if fecha else None,
            "titular": (f.get("descripcion") or "").strip() or None,
            "monto": f["monto"],
            "saldo": f.get("saldo"),
            "cliente_acreditado": None,
            "fecha_acred": None,
        })
    return out


def huella(filas_parser: list[dict]) -> str:
    """Misma huella que el upload de Excel. Se calcula con floats (como los entrega el
    parser de Excel) para que el mismo extracto en Excel y en PDF dé la misma huella."""
    return fingerprint([{"orden": f.get("orden"), "monto": float(f["monto"])} for f in filas_parser])


def _huella_por_contenido(filas_parser: list[dict]) -> str:
    """Huella alternativa (fecha, monto, saldo de cada fila) para cuando la huella del
    Excel choca con OTRO extracto (misma cantidad de filas y misma suma: p. ej. una
    cuenta sin movimiento que solo cobra la misma comisión todos los meses)."""
    raw = "pdf|" + "|".join(f"{_iso(f.get('fecha')) or ''}:{dinero_str(f['monto'])}:{dinero_str(f.get('saldo')) or ''}"
                            for f in filas_parser)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _huella_libre(db: Session, org_id: int, filas_parser: list[dict]) -> str:
    """Huella para un extracto NUEVO: la del Excel, salvo que ya la use otro extracto activo
    de la org (el índice único `uq_extracto_fp_org` no dejaría guardarlo)."""
    fp = huella(filas_parser)
    ocupada = db.query(ExtractoBancario.id).filter(
        ExtractoBancario.organizacion_id == org_id, ExtractoBancario.fingerprint == fp,
        ExtractoBancario.deleted_at.is_(None),
    ).first()
    return _huella_por_contenido(filas_parser) if ocupada else fp


def _filas_de_extracto(db: Session, extracto_ids: list[int]) -> dict[int, list[tuple]]:
    """`{extracto_id: [(orden, monto, saldo, fecha, titular), ...]}` (forma de `simular_merge`)."""
    por_extracto: dict[int, list[tuple]] = {eid: [] for eid in extracto_ids}
    if not extracto_ids:
        return por_extracto
    rows = (db.query(MovimientoBanco.extracto_id, MovimientoBanco.orden, MovimientoBanco.monto,
                     MovimientoBanco.saldo, MovimientoBanco.fecha, MovimientoBanco.titular)
            .filter(MovimientoBanco.extracto_id.in_(extracto_ids)).all())
    for (eid, orden, monto, saldo, fecha, titular) in rows:
        por_extracto[eid].append((orden, monto, saldo, fecha, titular))
    return por_extracto


# ── Duplicados / solapamiento ────────────────────────────────────────

def _cent(v: Any) -> Optional[Decimal]:
    if v is None:
        return None
    try:
        return Decimal(str(v)).quantize(CENT, rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None


def _fecha_iso_merger(f: Any) -> str:
    # Mismo criterio que extracto_merger: isoformat si es fecha, "" si no hay.
    return f.isoformat() if isinstance(f, date) else (str(f) if f else "")


def simular_merge(existentes: list[tuple], filas_parser: list[dict]) -> tuple[int, int]:
    """Predice, sin escribir nada, qué haría `mergear_movimientos` con estas filas.

    `existentes`: tuplas `(orden, monto, saldo, fecha, titular)` del extracto destino.
    Devuelve `(coincidencias, nuevos)`: filas que ya están (criterio `_match_existente`:
    (saldo, monto) o (fecha, monto, titular normalizado), al centavo) y filas que el merge
    agregaría (solo las MÁS NUEVAS que el último movimiento del extracto, como el UM).

    Es un espejo de lectura del corte del merger (ancla → primer match). Si cambia el
    merger hay que cambiar esto: `test_prediccion_igual_al_merge_real` lo vigila."""
    idx_saldo: set = set()
    idx_fecha: set = set()
    max_orden = 0
    ancla = None
    for (orden, monto, saldo, fecha, titular) in existentes:
        m, s = _cent(monto), _cent(saldo)
        f_iso, t = _fecha_iso_merger(fecha), _normalizar_titular(titular)
        if m is not None and s is not None:
            idx_saldo.add((m, s))
        if m is not None:
            idx_fecha.add((f_iso, m, t))
        if (orden or 0) > max_orden:
            max_orden = orden or 0
            ancla = (s, m, f_iso, t)

    def _coincide(f: dict) -> bool:
        m, s = _cent(f.get("monto")), _cent(f.get("saldo"))
        if m is not None and s is not None and (m, s) in idx_saldo:
            return True
        return m is not None and (_fecha_iso_merger(f.get("fecha")), m, _normalizar_titular(f.get("titular"))) in idx_fecha

    coincide = [_coincide(f) for f in filas_parser]
    corte: Optional[int] = None
    if ancla is not None and ancla[0] is not None:
        a_s, a_m, a_f, a_t = ancla
        mejor = 0
        for i, f in enumerate(filas_parser):
            s = _cent(f.get("saldo"))
            if s is None or s != a_s:
                continue
            score = 1
            m = _cent(f.get("monto"))
            if m is not None and a_m is not None and m == a_m:
                score += 1
            if a_f and _fecha_iso_merger(f.get("fecha")) == a_f:
                score += 1
            if a_t and _normalizar_titular(f.get("titular")) == a_t:
                score += 1
            if score > mejor:
                mejor, corte = score, i
    if corte is None:
        corte = next((i for i, c in enumerate(coincide) if c), None)
    candidatos = range(corte) if corte is not None else range(len(filas_parser))
    nuevos = sum(1 for i in candidatos if not coincide[i])
    return sum(coincide), nuevos


def coincidencias_por_fecha(existentes: list[tuple], filas_parser: list[dict]) -> int:
    """Filas del PDF que están en el extracto con la MISMA fecha y el mismo importe
    (multiconjunto). `simular_merge` mira (saldo, importe) sin fecha, como el merge
    de UM, y una cuenta que repite los mismos importes y saldos todos los meses
    (comisión fija + transferencia que la cubre) haría pasar octubre por septiembre."""
    disponibles = Counter(
        (_fecha_iso_merger(fecha), _cent(monto)) for (_orden, monto, _saldo, fecha, _titular) in existentes
    )
    n = 0
    for f in filas_parser:
        clave = (_fecha_iso_merger(f.get("fecha")), _cent(f.get("monto")))
        if disponibles[clave] > 0:
            disponibles[clave] -= 1
            n += 1
    return n


def _dup(tipo: str, ext: ExtractoBancario, coincidencias: int, nuevos: int, anteriores: int = 0) -> dict:
    return {"tipo": tipo, "extracto_id": ext.id, "nombre": ext.nombre_archivo, "banco": ext.banco,
            "coincidencias": coincidencias, "nuevos": nuevos, "anteriores": max(anteriores, 0),
            "archivado": ext.archivado_at is not None}


def _candidatos_por_fecha(db: Session, org_id: int, filas_parser: list[dict]) -> list[ExtractoBancario]:
    """Extractos de la org (activos o archivados) cuyos movimientos se pisan en
    fechas con las del PDF: el mismo mes puede haberse cargado hace mucho (o estar
    archivado por un cierre de período) y no estar entre los más recientes."""
    fechas = [f["fecha"] for f in filas_parser if isinstance(f.get("fecha"), date)]
    if not fechas:
        return []
    desde, hasta = min(fechas), max(fechas)
    ids = [eid for (eid,) in (
        db.query(MovimientoBanco.extracto_id)
        .join(ExtractoBancario, ExtractoBancario.id == MovimientoBanco.extracto_id)
        .filter(ExtractoBancario.organizacion_id == org_id, ExtractoBancario.deleted_at.is_(None),
                MovimientoBanco.fecha.isnot(None))
        .group_by(MovimientoBanco.extracto_id)
        .having(func.min(MovimientoBanco.fecha) <= hasta, func.max(MovimientoBanco.fecha) >= desde)
        .order_by(MovimientoBanco.extracto_id.desc())
        .limit(MAX_EXTRACTOS_POR_FECHA)
        .all()
    )]
    if not ids:
        return []
    return db.query(ExtractoBancario).filter(ExtractoBancario.id.in_(ids)).all()


def buscar_duplicado(db: Session, org_id: int, filas_parser: list[dict], *, sha: Optional[str] = None,
                     excluir_borrador_id: Optional[int] = None, banco: Optional[str] = None) -> Optional[dict]:
    """¿Ya hay un extracto activo de la org con este PDF o estos movimientos?

    - `mismo_archivo`: otro borrador confirmado con el mismo sha256 y su extracto activo.
    - `mismos_movimientos`: misma huella que un extracto (como el Excel) con las mismas
      fechas e importes, o todas las filas coinciden en fecha e importe con un extracto
      de la misma cantidad de movimientos.
    - `solapado`: el extracto con más filas en común en fecha e importe (mismo banco
      primero) entre los que se pisan en fechas con el PDF (activos o archivados) y los
      más recientes; `nuevos` = lo que agregaría "agregar solo los nuevos" y `anteriores`
      = filas del PDF que no están y el merge no agregaría (más viejas que el extracto).
    Comparar por fecha evita tomar otro mes con los mismos importes como "ya cargado"."""
    n = len(filas_parser)
    if sha:
        q = (db.query(ExtractoBancario)
             .join(BorradorExtractoPdf, BorradorExtractoPdf.extracto_id == ExtractoBancario.id)
             .filter(BorradorExtractoPdf.organizacion_id == org_id,
                     BorradorExtractoPdf.contenido_sha256 == sha,
                     BorradorExtractoPdf.estado == "confirmado",
                     ExtractoBancario.organizacion_id == org_id,
                     ExtractoBancario.deleted_at.is_(None)))
        if excluir_borrador_id:
            q = q.filter(BorradorExtractoPdf.id != excluir_borrador_id)
        ext = q.order_by(BorradorExtractoPdf.id.desc()).first()
        if ext:
            return _dup("mismo_archivo", ext, n, 0)
    if not n:
        return None

    ext = (db.query(ExtractoBancario)
           .filter(ExtractoBancario.organizacion_id == org_id,
                   ExtractoBancario.fingerprint == huella(filas_parser),
                   ExtractoBancario.deleted_at.is_(None))
           .order_by(ExtractoBancario.id.desc()).first())
    if ext:
        # La huella solo mira cantidad + suma: se confirma por fecha e importe para no
        # tomar como "ya cargado" otro mes con los mismos importes (y perder ese mes).
        if coincidencias_por_fecha(_filas_de_extracto(db, [ext.id])[ext.id], filas_parser) * 5 >= n * 4:
            return _dup("mismos_movimientos", ext, n, 0)

    recientes = (db.query(ExtractoBancario)
                 .filter(ExtractoBancario.organizacion_id == org_id,
                         ExtractoBancario.deleted_at.is_(None),
                         ExtractoBancario.archivado_at.is_(None))
                 .order_by(ExtractoBancario.fecha_creacion.desc(), ExtractoBancario.id.desc())
                 .limit(MAX_EXTRACTOS_SOLAPADO).all())
    vistos: set[int] = set()
    candidatos: list[ExtractoBancario] = []
    for e in _candidatos_por_fecha(db, org_id, filas_parser) + recientes:
        if e.id not in vistos:
            vistos.add(e.id)
            candidatos.append(e)
    if not candidatos:
        return None
    candidatos.sort(key=lambda e: 0 if (banco and e.banco == banco) else 1)  # estable: mismo banco primero
    por_extracto = _filas_de_extracto(db, [e.id for e in candidatos])

    mejor: Optional[tuple[ExtractoBancario, int, int, int]] = None
    for e in candidatos:
        por_fecha = coincidencias_por_fecha(por_extracto[e.id], filas_parser)
        if not por_fecha:
            continue
        coincidencias, nuevos = simular_merge(por_extracto[e.id], filas_parser)
        if mejor is None or por_fecha > mejor[1]:
            mejor = (e, por_fecha, coincidencias, nuevos)
    if mejor is None or mejor[1] < min(2, n):
        return None
    e, por_fecha, coincidencias, nuevos = mejor
    if por_fecha == n and len(por_extracto[e.id]) == n:
        return _dup("mismos_movimientos", e, n, 0)
    return _dup("solapado", e, coincidencias, nuevos, n - coincidencias - nuevos)


# ── Borradores: lectura, colgados, salida ────────────────────────────

def revisar_colgados(db: Session, org_id: int, borrador_id: Optional[int] = None) -> None:
    """Un borrador `procesando` > 10 min se da por interrumpido (`error`); uno
    `confirmando` > 10 min vuelve a `listo` (la confirmación es reintentable)."""
    limite = _utcnow() - timedelta(minutes=MINUTOS_COLGADO)
    marca = func.coalesce(BorradorExtractoPdf.actualizado_at, BorradorExtractoPdf.creado_at)
    base = db.query(BorradorExtractoPdf).filter(BorradorExtractoPdf.organizacion_id == org_id, marca < limite)
    if borrador_id is not None:
        base = base.filter(BorradorExtractoPdf.id == borrador_id)
    n = base.filter(BorradorExtractoPdf.estado == "procesando").update(
        {"estado": "error", "error": MSG_COLGADO, "actualizado_at": _utcnow()}, synchronize_session=False)
    n += base.filter(BorradorExtractoPdf.estado == "confirmando").update(
        {"estado": "listo", "actualizado_at": _utcnow()}, synchronize_session=False)
    if n:
        db.commit()


def obtener_borrador(db: Session, org_id: int, borrador_id: int) -> BorradorExtractoPdf:
    revisar_colgados(db, org_id, borrador_id)
    b = db.query(BorradorExtractoPdf).filter(
        BorradorExtractoPdf.id == borrador_id,
        BorradorExtractoPdf.organizacion_id == org_id,
    ).first()
    if not b:
        raise ExtractoPdfServicioError("Borrador no encontrado", 404)
    return b


def borrador_out(db: Session, b: BorradorExtractoPdf) -> dict:
    datos = b.datos or {}
    duplicado = None
    if b.estado == "listo":
        duplicado = buscar_duplicado(
            db, b.organizacion_id, a_filas_parser(_filas_guardadas(b), datos.get("orden") or "asc"),
            sha=b.contenido_sha256, excluir_borrador_id=b.id, banco=b.banco,
        )
    return {
        "id": b.id,
        "estado": b.estado,
        "nombre_archivo": b.nombre_archivo,
        "creado_at": b.creado_at,
        "metodo": b.metodo,
        "banco": b.banco,
        "banco_clave": b.banco_clave,
        "periodo_desde": b.periodo_desde,
        "periodo_hasta": b.periodo_hasta,
        "saldo_inicial": dinero_str(b.saldo_inicial),
        "saldo_final": dinero_str(b.saldo_final),
        "orden": datos.get("orden") or "asc",
        "paginas": int(datos.get("paginas") or 0),
        "escaneado": bool(datos.get("escaneado")),
        "movimientos": datos.get("movimientos") or [],
        "cuadre": serializar_cuadre(datos.get("cuadre")),
        "alertas": b.alertas or [],
        "duplicado": duplicado,
        "extracto_id": b.extracto_id,
        "ia_disponible": bool(ia_configurada()),
        "ia_usada": bool(datos.get("ia_usada")),
        "puede_aprender": bool(datos.get("aprendizaje")),
        "error": b.error,
    }


def borrador_resumen(b: BorradorExtractoPdf) -> dict:
    datos = b.datos or {}
    return {
        "id": b.id, "estado": b.estado, "nombre_archivo": b.nombre_archivo, "creado_at": b.creado_at,
        "metodo": b.metodo, "banco": b.banco, "periodo_desde": b.periodo_desde,
        "periodo_hasta": b.periodo_hasta, "cantidad": len(datos.get("movimientos") or []),
        "cierra": bool((datos.get("cuadre") or {}).get("cierra")), "extracto_id": b.extracto_id,
        "error": b.error,
    }


def listar_borradores(db: Session, org_id: int, estado: Optional[str] = None, limite: int = 50) -> list[BorradorExtractoPdf]:
    if estado and estado not in ESTADOS_BORRADOR_PDF:
        raise ExtractoPdfServicioError("Estado inválido", 422)
    revisar_colgados(db, org_id)
    q = db.query(BorradorExtractoPdf).filter(BorradorExtractoPdf.organizacion_id == org_id)
    q = q.filter(BorradorExtractoPdf.estado == estado) if estado else \
        q.filter(BorradorExtractoPdf.estado.in_(ESTADOS_PENDIENTES_PDF))
    return q.order_by(BorradorExtractoPdf.creado_at.desc(), BorradorExtractoPdf.id.desc()).limit(limite).all()


# ── Importar ─────────────────────────────────────────────────────────

def validar_archivo(nombre_archivo: Optional[str], contenido: bytes, max_bytes: int) -> str:
    """Valida nombre, tamaño y firma `%PDF`. Devuelve el nombre limpio."""
    nombre = os.path.basename((nombre_archivo or "").replace("\\", "/")).strip()
    if not nombre.lower().endswith(".pdf"):
        raise ExtractoPdfServicioError("Solo se aceptan archivos PDF.", 400)
    if len(contenido) > max_bytes:
        raise ExtractoPdfServicioError(f"El archivo supera el límite de {max_bytes // (1024 * 1024)} MB.", 413)
    if not contenido:
        raise ExtractoPdfServicioError("El archivo está vacío.", 400)
    # La firma puede venir precedida de basura (la especificación PDF tolera hasta 1 KB).
    if b"%PDF-" not in contenido[:1024]:
        raise ExtractoPdfServicioError("El archivo no es un PDF válido.", 400)
    return nombre[:255]


def _moldes_para_lector(db: Session, org_id: int) -> list[dict]:
    moldes = (db.query(MoldeExtractoPdf)
              .filter(MoldeExtractoPdf.organizacion_id == org_id)
              .order_by(MoldeExtractoPdf.confirmaciones.desc(), MoldeExtractoPdf.id.desc())
              .limit(MAX_MOLDES_LECTOR).all())
    return [{"id": m.id, "banco_clave": m.banco_clave, "firma": m.firma, "layout": m.layout or {}} for m in moldes]


def _leer(db: Session, org_id: int, contenido: bytes, *, usar_ia: bool, forzar_ia: bool, hoy: date) -> dict:
    moldes = _moldes_para_lector(db, org_id)
    # Cerrar la transacción antes de leer: pdfminer o la IA pueden tardar y no hay que
    # retener una conexión del pool (ni un snapshot abierto) mientras tanto.
    db.commit()
    try:
        return _lector()(contenido, moldes=moldes, usar_ia=usar_ia, forzar_ia=forzar_ia, hoy=hoy)
    except ExtractoPdfServicioError:
        raise
    except Exception as ex:
        traducido = _error_de_lectura(ex)
        if traducido:
            raise traducido from ex
        logger.exception("Lectura determinista de PDF falló: %s", ex)
        raise ExtractoPdfServicioError(MSG_ERROR_LECTURA, 400) from ex


def _decidir_estado(res: dict, *, forzar_ia: bool) -> str:
    if forzar_ia:
        return "procesando"
    cierra = bool((res.get("cuadre") or {}).get("cierra"))
    if res.get("movimientos") and cierra:
        return "listo"
    return "procesando" if ia_configurada() else "listo"


def importar_pdf(db: Session, *, org_id: int, usuario_id: int, nombre_archivo: str, contenido: bytes,
                 forzar_ia: bool = False, banco_usuario: Optional[str] = None,
                 hoy: Optional[date] = None) -> tuple[BorradorExtractoPdf, Optional[dict]]:
    """Crea (o reutiliza) el borrador de un PDF. Devuelve `(borrador, trabajo)`, donde
    `trabajo` son los kwargs de `procesar_en_fondo` si hay que releer con IA (o None).

    El archivo ya viene validado (`validar_archivo`). No se guarda el PDF: solo su sha256."""
    hoy = hoy or hoy_art()
    if forzar_ia and not ia_configurada():
        raise ExtractoPdfServicioError("La lectura con IA no está configurada (falta GEMINI_API_KEY).", 503)
    sha = hashlib.sha256(contenido).hexdigest()

    # 1) Ya importado: el mismo PDF confirmado y su extracto sigue activo.
    confirmado = (db.query(BorradorExtractoPdf)
                  .join(ExtractoBancario, ExtractoBancario.id == BorradorExtractoPdf.extracto_id)
                  .filter(BorradorExtractoPdf.organizacion_id == org_id,
                          BorradorExtractoPdf.contenido_sha256 == sha,
                          BorradorExtractoPdf.estado == "confirmado",
                          ExtractoBancario.organizacion_id == org_id,
                          ExtractoBancario.deleted_at.is_(None))
                  .order_by(BorradorExtractoPdf.id.desc()).first())
    if confirmado:
        return confirmado, None

    # 2) Ya hay un borrador pendiente de este PDF: se reutiliza (no se crea otra fila).
    revisar_colgados(db, org_id)
    b = (db.query(BorradorExtractoPdf)
         .filter(BorradorExtractoPdf.organizacion_id == org_id,
                 BorradorExtractoPdf.contenido_sha256 == sha,
                 BorradorExtractoPdf.estado.in_(ESTADOS_PENDIENTES_PDF))
         .order_by(BorradorExtractoPdf.id.desc()).first())
    if b is not None:
        if b.estado == "procesando" or (b.estado == "listo" and not forzar_ia):
            return b, None
        banco_usuario = banco_usuario or (b.datos or {}).get("banco_usuario")

    if b is not None and forzar_ia:
        # Releer con IA un borrador ya leído: no hace falta la lectura determinista de nuevo.
        b.estado = "procesando"
        b.error = None
        b.actualizado_at = _utcnow()
        reutilizado = True
    else:
        res = _leer(db, org_id, contenido, usar_ia=False, forzar_ia=False, hoy=hoy)
        valores = valores_de_lectura(db, org_id, res, banco_usuario=banco_usuario)
        reutilizado = b is not None
        if b is None:
            b = BorradorExtractoPdf(organizacion_id=org_id, creado_por=usuario_id,
                                    nombre_archivo=nombre_archivo, contenido_sha256=sha,
                                    tamano_bytes=len(contenido))
            db.add(b)
        _aplicar(b, valores)
        b.estado = _decidir_estado(res, forzar_ia=forzar_ia)
        b.actualizado_at = _utcnow()
    db.commit()
    db.refresh(b)

    registrar_log(db, usuario_id, "borradores_extracto_pdf", b.id, "IMPORTAR", {
        "nombre_archivo": b.nombre_archivo, "estado": b.estado, "metodo": b.metodo,
        "movimientos": len((b.datos or {}).get("movimientos") or []),
        "reutilizado": reutilizado, "forzar_ia": forzar_ia,
    })
    trabajo = None
    if b.estado == "procesando":
        trabajo = {"borrador_id": b.id, "contenido": contenido, "forzar_ia": forzar_ia,
                   "banco_usuario": banco_usuario, "hoy": hoy}
    return b, trabajo


def procesar_en_fondo(session_factory: Callable[[], Session], *, borrador_id: int, contenido: bytes,
                      forzar_ia: bool = False, banco_usuario: Optional[str] = None,
                      hoy: Optional[date] = None) -> None:
    """Relee el PDF con IA (tarea en segundo plano, sesión propia). Nunca lanza: ante
    cualquier falla el borrador queda en `error` con un mensaje para la persona.
    Si mientras tanto lo descartaron, no lo pisa (UPDATE condicionado a `procesando`)."""
    db = session_factory()
    try:
        b = db.query(BorradorExtractoPdf).filter(BorradorExtractoPdf.id == borrador_id).first()
        if not b or b.estado != "procesando":
            return
        org_id = b.organizacion_id
        try:
            res = _leer(db, org_id, contenido, usar_ia=True, forzar_ia=forzar_ia, hoy=hoy or hoy_art())
            valores = valores_de_lectura(db, org_id, res, banco_usuario=banco_usuario)
            valores.update({"estado": "listo", "actualizado_at": _utcnow()})
        except ExtractoPdfServicioError as ex:
            valores = {"estado": "error", "error": ex.mensaje, "actualizado_at": _utcnow()}
        except Exception as ex:
            logger.exception("Lectura con IA del borrador %s falló: %s", borrador_id, ex)
            valores = {"estado": "error", "error": MSG_ERROR_LECTURA, "actualizado_at": _utcnow()}
        db.query(BorradorExtractoPdf).filter(
            BorradorExtractoPdf.id == borrador_id,
            BorradorExtractoPdf.estado == "procesando",
        ).update(valores, synchronize_session=False)
        db.commit()
    except Exception as ex:
        logger.exception("No se pudo guardar la lectura del borrador %s: %s", borrador_id, ex)
        try:
            db.rollback()
            db.query(BorradorExtractoPdf).filter(
                BorradorExtractoPdf.id == borrador_id,
                BorradorExtractoPdf.estado == "procesando",
            ).update({"estado": "error", "error": MSG_ERROR_LECTURA, "actualizado_at": _utcnow()},
                     synchronize_session=False)
            db.commit()
        except Exception:
            db.rollback()
    finally:
        db.close()


# ── Descartar ────────────────────────────────────────────────────────

def descartar_borrador(db: Session, b: BorradorExtractoPdf, usuario_id: int) -> None:
    if b.estado == "descartado":
        return
    if b.estado == "confirmado":
        raise ExtractoPdfServicioError("Este PDF ya se guardó como extracto: si hay que sacarlo, borrá el extracto.", 409)
    if b.estado == "confirmando":
        raise ExtractoPdfServicioError("Se está guardando este extracto: esperá unos segundos.", 409)
    n = db.query(BorradorExtractoPdf).filter(
        BorradorExtractoPdf.id == b.id,
        BorradorExtractoPdf.estado.in_(ESTADOS_PENDIENTES_PDF),
    ).update({"estado": "descartado", "actualizado_at": _utcnow()}, synchronize_session=False)
    db.commit()
    if not n:
        db.refresh(b)
        if b.estado != "descartado":
            raise ExtractoPdfServicioError("El borrador cambió mientras tanto: actualizá la página.", 409)
        return
    registrar_log(db, usuario_id, "borradores_extracto_pdf", b.id, "DESCARTAR", {"nombre_archivo": b.nombre_archivo})


# ── Confirmar ────────────────────────────────────────────────────────

def _valor(obj: Any, campo: str) -> Any:
    return obj.get(campo) if isinstance(obj, dict) else getattr(obj, campo, None)


def _vacio(raw: Any) -> bool:
    return raw is None or (isinstance(raw, str) and not raw.strip())


def validar_filas(movimientos: list, hoy: date) -> list[dict]:
    """Filas confirmadas → `{fecha, descripcion, monto, saldo}` con Decimal. 422 con la fila."""
    if not movimientos:
        raise ExtractoPdfServicioError("No hay movimientos para guardar.", 422)
    if len(movimientos) > MAX_MOVIMIENTOS:
        raise ExtractoPdfServicioError(f"Son demasiados movimientos (máximo {MAX_MOVIMIENTOS}).", 422)
    tope_txt = formato_ar(TOPE_MOVIMIENTO - CENT)
    filas = []
    for i, m in enumerate(movimientos, start=1):
        fecha = a_fecha(_valor(m, "fecha"))
        if not fecha or not (1990 <= fecha.year <= hoy.year + 1):
            raise ExtractoPdfServicioError(f"Fila {i}: la fecha falta o no es válida.", 422)
        monto = a_dinero(_valor(m, "monto"))
        if monto is None:
            raise ExtractoPdfServicioError(f"Fila {i}: el importe falta o no es válido.", 422)
        if monto == 0:
            raise ExtractoPdfServicioError(f"Fila {i}: el importe no puede ser cero.", 422)
        if abs(monto) >= TOPE_MOVIMIENTO:
            raise ExtractoPdfServicioError(f"Fila {i}: el importe es demasiado grande (máximo $ {tope_txt}).", 422)
        saldo_raw = _valor(m, "saldo")
        saldo = None
        if not _vacio(saldo_raw):
            saldo = a_dinero(saldo_raw)
            if saldo is None:
                raise ExtractoPdfServicioError(f"Fila {i}: el saldo no es válido.", 422)
            if abs(saldo) >= TOPE_MOVIMIENTO:
                raise ExtractoPdfServicioError(f"Fila {i}: el saldo es demasiado grande (máximo $ {tope_txt}).", 422)
        descripcion = str(_valor(m, "descripcion") or "").strip()[:MAX_DESCRIPCION]
        filas.append({"fecha": fecha, "descripcion": descripcion, "monto": monto, "saldo": saldo})
    return filas


def _saldo_cabecera(raw: Any, etiqueta: str) -> Optional[Decimal]:
    if _vacio(raw):
        return None
    d = a_dinero(raw)
    if d is None:
        raise ExtractoPdfServicioError(f"El {etiqueta} no es válido.", 422)
    if abs(d) >= TOPE_SALDO_BORRADOR:
        raise ExtractoPdfServicioError(f"El {etiqueta} es demasiado grande.", 422)
    return d


def _cambios(originales: list[dict], confirmadas: list[dict]) -> int:
    """Filas corregidas: las que no coinciden en (fecha, monto) contando agregadas y borradas.
    Se compara como multiconjunto (borrar una fila del medio cuenta 1, no "corre" el resto)."""
    a = Counter((a_fecha(o.get("fecha")), a_dinero(o.get("monto"))) for o in originales)
    b = Counter((c["fecha"], c["monto"]) for c in confirmadas)
    iguales = sum((a & b).values())
    return max(len(originales), len(confirmadas)) - iguales


def _aprender(db: Session, b: BorradorExtractoPdf, filas: list[dict], cierra: bool, usuario_id: int) -> bool:
    """Guarda/refuerza el formato aprendido si la lectura fue buena. Devuelve si aprendió."""
    datos = b.datos or {}
    originales = datos.get("movimientos") or []
    if not cierra or not originales:
        return False
    if Decimal(_cambios(originales, filas)) > Decimal(len(originales)) * UMBRAL_CAMBIOS_APRENDIZAJE:
        return False
    ahora = _utcnow()
    if b.metodo == "molde":
        molde = db.query(MoldeExtractoPdf).filter(
            MoldeExtractoPdf.id == b.molde_id, MoldeExtractoPdf.organizacion_id == b.organizacion_id,
        ).first() if b.molde_id else None
        if not molde:
            return False
        molde.confirmaciones = (molde.confirmaciones or 0) + 1
        molde.ultimo_uso_at = ahora
        return True
    apr = datos.get("aprendizaje")
    if not isinstance(apr, dict) or not apr.get("firma") or not isinstance(apr.get("layout"), dict):
        return False
    firma = str(apr["firma"])
    if len(firma) > 64:
        logger.warning("Firma de formato demasiado larga (%s caracteres): no se aprende", len(firma))
        return False
    origen = b.metodo if b.metodo in ORIGENES_MOLDE else None
    clave = str(apr.get("banco_clave") or b.banco_clave or "")[:40] or None
    molde = db.query(MoldeExtractoPdf).filter(
        MoldeExtractoPdf.organizacion_id == b.organizacion_id, MoldeExtractoPdf.firma == firma,
    ).first()
    if molde:
        # El formato guardado no alcanzó para este PDF y este sí: se reemplaza.
        molde.layout = _json_safe(apr["layout"])
        molde.banco_clave = clave
        molde.origen = origen or molde.origen
        molde.confirmaciones = (molde.confirmaciones or 0) + 1
        molde.ultimo_uso_at = ahora
    else:
        db.add(MoldeExtractoPdf(
            organizacion_id=b.organizacion_id, banco_clave=clave, firma=firma,
            layout=_json_safe(apr["layout"]), origen=origen, confirmaciones=1,
            ultimo_uso_at=ahora, creado_por=usuario_id,
        ))
    return True


def _guardar_confirmacion(db: Session, b: BorradorExtractoPdf, resultado: dict) -> None:
    datos = dict(b.datos or {})
    datos["confirmacion"] = dict(resultado)
    b.datos = datos  # reasignar: la columna JSON no detecta mutaciones in situ


def _volver_a(db: Session, borrador_id: int, estado: str) -> None:
    try:
        db.rollback()
        db.query(BorradorExtractoPdf).filter(
            BorradorExtractoPdf.id == borrador_id, BorradorExtractoPdf.estado == "confirmando",
        ).update({"estado": estado, "actualizado_at": _utcnow()}, synchronize_session=False)
        db.commit()
    except Exception:  # pragma: no cover
        logger.exception("No se pudo liberar el borrador %s", borrador_id)
        db.rollback()


def confirmar_borrador(db: Session, b: BorradorExtractoPdf, body: Any, usuario_id: int,
                       hoy: Optional[date] = None) -> dict:
    """Confirma el borrador (ver docstring del módulo). Devuelve `ConfirmarExtractoPdfOut`."""
    hoy = hoy or hoy_art()
    if b.estado == "confirmado":
        activo = b.extracto_id and db.query(ExtractoBancario.id).filter(
            ExtractoBancario.id == b.extracto_id, ExtractoBancario.deleted_at.is_(None),
        ).first()
        if not activo:
            raise ExtractoPdfServicioError(
                "El extracto de este PDF se borró: volvé a subir el PDF para importarlo de nuevo.", 409)
        previo = dict((b.datos or {}).get("confirmacion") or {})
        previo.update({"extracto_id": b.extracto_id, "ya_existia": True})
        previo.setdefault("destino", "nuevo")
        previo.setdefault("mensaje", "Este PDF ya estaba guardado.")
        return previo
    if b.estado == "confirmando":
        raise ExtractoPdfServicioError("Ya se está guardando este extracto: esperá unos segundos.", 409)
    if b.estado == "procesando":
        raise ExtractoPdfServicioError("Todavía se está leyendo el PDF: esperá a que termine.", 409)
    if b.estado not in ("listo", "error"):
        raise ExtractoPdfServicioError("Este PDF se descartó: volvé a subirlo para importarlo.", 409)

    destino = (_valor(body, "destino") or "nuevo").strip().lower()
    if destino not in ("nuevo", "existente"):
        raise ExtractoPdfServicioError("Destino inválido: elegí extracto nuevo o uno existente.", 422)
    filas = validar_filas(list(_valor(body, "movimientos") or []), hoy)
    saldo_inicial = _saldo_cabecera(_valor(body, "saldo_inicial"), "saldo inicial")
    saldo_final = _saldo_cabecera(_valor(body, "saldo_final"), "saldo final")
    orden = (b.datos or {}).get("orden") or "asc"
    cuadre = _validar_saldos([dict(f, dudosa=False, motivos=[]) for f in filas], orden=orden,
                             saldo_inicial=saldo_inicial, saldo_final=saldo_final)
    cierra = bool(cuadre.get("cierra"))
    if not cierra and not _valor(body, "confirmar_sin_cuadre"):
        diferencia = a_dinero(cuadre.get("diferencia"))
        if diferencia is None:
            raise ExtractoPdfServicioError(
                "No se pudo comprobar el saldo (falta el saldo inicial o el final). "
                "Revisá los movimientos o confirmá igual.", 422)
        raise ExtractoPdfServicioError(
            f"El saldo no cierra: hay una diferencia de $ {formato_ar(abs(diferencia))}. "
            "Revisá los movimientos o confirmá igual.", 422)

    destino_ext = None
    if destino == "existente":
        extracto_id = _valor(body, "extracto_id")
        if not extracto_id:
            raise ExtractoPdfServicioError("Elegí a qué extracto agregar los movimientos.", 422)
        destino_ext = db.query(ExtractoBancario).filter(
            ExtractoBancario.id == extracto_id,
            ExtractoBancario.organizacion_id == b.organizacion_id,
            ExtractoBancario.deleted_at.is_(None),
        ).first()
        if not destino_ext:
            raise ExtractoPdfServicioError("Extracto no encontrado", 404)
        if destino_ext.archivado_at is not None:
            raise ExtractoPdfServicioError(
                "El extracto está archivado (período cerrado): desarchivalo o guardá el PDF como extracto nuevo.", 409)

    banco_body = (_valor(body, "banco") or "").strip()[:120]
    banco_final = resolver_banco(banco_body or b.banco or BANCO_DEFAULT, b.banco_clave or "generico")[:120]
    nombre = ((_valor(body, "nombre") or "").strip() or b.nombre_archivo)[:255]
    filas_parser = a_filas_parser(filas, orden)

    # Transición atómica: solo un request puede pasar de listo/error a confirmando.
    estado_previo = b.estado
    borrador_id = b.id
    tomado = db.query(BorradorExtractoPdf).filter(
        BorradorExtractoPdf.id == borrador_id,
        BorradorExtractoPdf.estado == estado_previo,
    ).update({"estado": "confirmando", "actualizado_at": _utcnow()}, synchronize_session=False)
    db.commit()
    if tomado != 1:
        db.refresh(b)
        if b.estado == "confirmado":
            return confirmar_borrador(db, b, body, usuario_id, hoy)
        raise ExtractoPdfServicioError("Ya se está guardando este extracto: esperá unos segundos.", 409)

    try:
        db.refresh(b)
        metodo = b.metodo
        if destino == "nuevo":
            resultado = _confirmar_nuevo(db, b, filas_parser, nombre=nombre, banco=banco_final,
                                         usuario_id=usuario_id, metodo=metodo)
        else:
            resultado = _confirmar_existente(db, b, destino_ext, filas_parser, usuario_id=usuario_id)
    except IntegrityError as ex:
        logger.warning("Confirmación del borrador %s chocó con otro extracto: %s", borrador_id, ex)
        _volver_a(db, borrador_id, estado_previo)
        raise ExtractoPdfServicioError(
            "Ese extracto se acaba de guardar desde otro lado. Actualizá la página y revisá.", 409) from ex
    except ExtractoPdfServicioError:
        _volver_a(db, borrador_id, estado_previo)
        raise
    except Exception:
        logger.exception("Confirmación del borrador %s falló", borrador_id)
        _volver_a(db, borrador_id, estado_previo)
        raise

    # Aprendizaje (aparte: si falla, el extracto ya quedó guardado).
    try:
        if _aprender(db, b, filas, cierra, usuario_id):
            resultado["molde_aprendido"] = True
            _guardar_confirmacion(db, b, resultado)
            db.commit()
    except Exception as ex:
        logger.warning("No se pudo guardar el formato aprendido del borrador %s: %s", borrador_id, ex)
        db.rollback()
        resultado["molde_aprendido"] = False
    return resultado


def _confirmar_nuevo(db: Session, b: BorradorExtractoPdf, filas_parser: list[dict], *, nombre: str,
                     banco: str, usuario_id: int, metodo: Optional[str]) -> dict:
    n = len(filas_parser)
    dup = buscar_duplicado(db, b.organizacion_id, filas_parser, sha=b.contenido_sha256,
                           excluir_borrador_id=b.id, banco=banco)
    if dup and dup["tipo"] in ("mismo_archivo", "mismos_movimientos"):
        ext = db.query(ExtractoBancario).filter(ExtractoBancario.id == dup["extracto_id"]).first()
        resultado = {
            "extracto_id": ext.id, "destino": "nuevo", "ya_existia": True, "agregados": 0,
            "duplicados": n, "no_agregados": 0, "molde_aprendido": False, "contabilidad_ok": True,
            "mensaje": f"Ese extracto ya estaba cargado («{ext.nombre_archivo}»): no se duplicó nada.",
        }
        accion, cambios = "VINCULAR_PDF", {"borrador_id": b.id, "nombre_archivo": b.nombre_archivo,
                                           "origen": "pdf", "metodo": metodo, "tipo": dup["tipo"]}
    else:
        ext = crear_extracto_con_movimientos(
            db, movs=filas_parser, nombre_archivo=nombre, banco=banco, huella=_huella_libre(db, b.organizacion_id, filas_parser),
            org_id=b.organizacion_id, usuario_id=usuario_id, commit=False,
        )
        resultado = {
            "extracto_id": ext.id, "destino": "nuevo", "ya_existia": False, "agregados": n,
            "duplicados": 0, "no_agregados": 0, "molde_aprendido": False, "contabilidad_ok": True,
            "mensaje": f"Extracto guardado: {n} movimientos.",
        }
        # Igual que el upload de Excel: el extracto base no genera asiento propio.
        accion, cambios = "INSERT", {"nombre_archivo": nombre, "movimientos": n, "origen": "pdf",
                                     "metodo": metodo, "borrador_id": b.id}
    b.estado = "confirmado"
    b.extracto_id = ext.id
    b.confirmado_por = usuario_id
    b.confirmado_at = _utcnow()
    _guardar_confirmacion(db, b, resultado)
    registrar_log(db, usuario_id, "extractos_bancarios", ext.id, accion, cambios, autocommit=False)
    db.commit()
    return resultado


def _max_lote(db: Session, extracto_id: int) -> int:
    return int(db.query(func.max(MovimientoBanco.um_lote))
               .filter(MovimientoBanco.extracto_id == extracto_id).scalar() or 0)


def _plural_mov(n: int) -> str:
    return "1 movimiento" if n == 1 else f"{n} movimientos"


def _confirmar_existente(db: Session, b: BorradorExtractoPdf, ext: ExtractoBancario,
                         filas_parser: list[dict], *, usuario_id: int) -> dict:
    """Agrega al extracto solo los movimientos nuevos, con el merge de "Últimos
    movimientos". El merge commitea solo: para no dejar movimientos sin asiento si
    algo falla después, antes de mergear se anota en el borrador el último lote del
    extracto; un reintento genera los asientos que falten de los lotes posteriores
    (el asiento de UM es idempotente) y cuenta como agregados los de ese intento."""
    borrador_id, extracto_id, nombre_ext = b.id, ext.id, ext.nombre_archivo
    datos = dict(b.datos or {})
    pendiente = datos.get("merge_pendiente")
    if not (isinstance(pendiente, dict) and pendiente.get("extracto_id") == extracto_id):
        pendiente = {"extracto_id": extracto_id, "lote_previo": _max_lote(db, extracto_id)}
        datos["merge_pendiente"] = pendiente
        b.datos = datos
        db.commit()
    lote_previo = int(pendiente.get("lote_previo") or 0)

    coincidencias, _ = simular_merge(_filas_de_extracto(db, [extracto_id])[extracto_id], filas_parser)
    # Mismo merge que "Últimos movimientos": dedup + solo lo más nuevo, source='um' + um_lote.
    stats = mergear_movimientos(db, extracto_id, filas_parser)  # commitea
    agregados = int(stats.get("agregados") or 0)

    # Asientos de los lotes de este borrador (también los de un intento anterior cortado).
    lotes = [lote for (lote,) in db.query(MovimientoBanco.um_lote).filter(
        MovimientoBanco.extracto_id == extracto_id, MovimientoBanco.um_lote > lote_previo,
    ).distinct().all() if lote]
    agregados_antes = 0
    if not agregados and lotes:
        agregados_antes = db.query(func.count(MovimientoBanco.id)).filter(
            MovimientoBanco.extracto_id == extracto_id, MovimientoBanco.um_lote > lote_previo,
        ).scalar() or 0
    contabilidad_ok = True
    for lote in sorted(lotes):
        ext = db.query(ExtractoBancario).filter(ExtractoBancario.id == extracto_id).first()
        if not registrar_asiento_um(db, extracto=ext, nuevo_lote=lote, usuario_id=usuario_id):
            db.rollback()
            contabilidad_ok = False
    total_agregados = agregados or int(agregados_antes)
    # En un reintento, `coincidencias` ya cuenta lo que agregó el intento anterior.
    no_agregados = max(len(filas_parser) - coincidencias - agregados, 0)

    if total_agregados:
        mensaje = f"Se agregaron {_plural_mov(total_agregados)} nuevos a «{nombre_ext}»."
    elif no_agregados:
        mensaje = f"No se agregó ningún movimiento a «{nombre_ext}»."
    else:
        mensaje = f"No había movimientos nuevos: «{nombre_ext}» ya los tenía todos."
    if no_agregados:
        mensaje += (
            f" {_plural_mov(no_agregados)} del PDF {'es anterior' if no_agregados == 1 else 'son anteriores'}"
            f" al último movimiento del extracto y no {'está' if no_agregados == 1 else 'están'} en él: no se"
            " agregaron. Si faltan, guardá el PDF como extracto nuevo."
        )
    if not contabilidad_ok:
        mensaje += " No se pudo generar el asiento contable de los movimientos agregados: revisalo en Contabilidad."
    resultado = {
        "extracto_id": extracto_id, "destino": "existente", "ya_existia": False,
        "agregados": total_agregados, "duplicados": coincidencias, "no_agregados": no_agregados,
        "molde_aprendido": False, "contabilidad_ok": contabilidad_ok, "mensaje": mensaje,
    }
    b = db.query(BorradorExtractoPdf).filter(BorradorExtractoPdf.id == borrador_id).first()
    b.estado = "confirmado"
    b.extracto_id = extracto_id
    b.confirmado_por = usuario_id
    b.confirmado_at = _utcnow()
    datos = dict(b.datos or {})
    datos.pop("merge_pendiente", None)
    b.datos = datos
    _guardar_confirmacion(db, b, resultado)
    db.commit()
    # La auditoría va aparte: los movimientos y su asiento ya quedaron guardados y un
    # fallo acá no puede dejar el borrador a medio confirmar.
    try:
        registrar_log(db, usuario_id, "extractos_bancarios", extracto_id, "APPEND_PDF",
                      _json_safe({"archivo": b.nombre_archivo, "borrador_id": borrador_id, "origen": "pdf",
                                  "metodo": b.metodo, "no_agregados": no_agregados, **stats}))
    except Exception:
        logger.exception("No se pudo registrar la auditoría del PDF %s agregado al extracto %s",
                         borrador_id, extracto_id)
        db.rollback()
    return resultado


# ── Moldes ───────────────────────────────────────────────────────────

def molde_out(m: MoldeExtractoPdf) -> dict:
    return {"id": m.id, "banco": nombre_banco(m.banco_clave) or "Otro banco", "banco_clave": m.banco_clave,
            "origen": m.origen, "confirmaciones": m.confirmaciones or 0, "creado_at": m.creado_at,
            "ultimo_uso_at": m.ultimo_uso_at}


def listar_moldes(db: Session, org_id: int) -> list[MoldeExtractoPdf]:
    return (db.query(MoldeExtractoPdf).filter(MoldeExtractoPdf.organizacion_id == org_id)
            .order_by(MoldeExtractoPdf.ultimo_uso_at.desc(), MoldeExtractoPdf.id.desc()).all())


def borrar_molde(db: Session, org_id: int, molde_id: int, usuario_id: int) -> None:
    m = db.query(MoldeExtractoPdf).filter(
        MoldeExtractoPdf.id == molde_id, MoldeExtractoPdf.organizacion_id == org_id,
    ).first()
    if not m:
        raise ExtractoPdfServicioError("Formato no encontrado", 404)
    cambios = {"banco_clave": m.banco_clave, "origen": m.origen, "confirmaciones": m.confirmaciones}
    # ON DELETE SET NULL también a mano (SQLite de los tests no aplica FKs).
    db.query(BorradorExtractoPdf).filter(
        BorradorExtractoPdf.organizacion_id == org_id, BorradorExtractoPdf.molde_id == molde_id,
    ).update({"molde_id": None}, synchronize_session=False)
    db.delete(m)
    registrar_log(db, usuario_id, "moldes_extracto_pdf", molde_id, "DELETE", cambios, autocommit=False)
    db.commit()
