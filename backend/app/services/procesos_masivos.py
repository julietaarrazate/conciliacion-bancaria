"""Procesos masivos: correr un cálculo para varias organizaciones a la vez y
asignar Excels de "Mis Comprobantes" a su org por el CUIT del título.

Reusa los servicios de cada módulo (no duplica cálculos). Reglas:
- Una org sin el módulo activo queda `omitido` (con el motivo).
- Lo presentado/revisado no se toca: `ya_presentado`. Los `guardar_o_actualizar_*`
  ya lo devuelven intacto; la liquidación de IVA lanza error y se traduce acá.
- Cada org se commitea sola: un error en una (`error`) no corta al resto.
- Liquidación de IVA: el cálculo pone en 0 retenciones/percepciones que no se le
  pasan (hoy se cargan a mano), así que se conservan las ya cargadas. Los saldos
  anteriores se heredan del mes previo si existe su liquidación; si no, se
  conservan los cargados.
"""
import io
import logging
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

import openpyxl
from sqlalchemy.orm import Session

from app.models.iibb import IIBBConfig
from app.models.iva_liquidacion import LiquidacionIva
from app.models.monotributo import MonotributoConfig
from app.models.organizacion import Organizacion
from app.models.sueldos import ConfigSueldos
from app.services import iibb_service, iva_liquidacion_service, iva_service, monotributo_service, sueldos_service
from app.services.auditoria import registrar_log

logger = logging.getLogger(__name__)

# clave → (nombre visible, tipo de período)
ACCIONES: Dict[str, Tuple[str, str]] = {
    "iva_liquidacion": ("Liquidación de IVA", "mensual"),
    "iva_proyeccion": ("Proyección de IVA", "mensual"),
    "iibb_proyeccion": ("Proyección de Ingresos Brutos", "mensual"),
    "monotributo_control": ("Control semestral de Monotributo", "semestral"),
    "sueldos_liquidacion": ("Liquidación de sueldos", "mensual"),
}
_RE_PERIODO = {"mensual": r"\d{4}-(0[1-9]|1[0-2])", "semestral": r"\d{4}-S[12]"}

_ERRORES_MODULO = (
    iva_service.IvaServiceError, iibb_service.IIBBServiceError,
    monotributo_service.MonotributoServiceError, sueldos_service.SueldosServiceError,
    iva_liquidacion_service.IvaLiquidacionError,
)


class ProcesoInvalido(ValueError):
    pass


def validar(accion: str, periodo: str) -> None:
    if accion not in ACCIONES:
        raise ProcesoInvalido(f"Acción desconocida: {accion}")
    tipo = ACCIONES[accion][1]
    if not re.fullmatch(_RE_PERIODO[tipo], periodo or ""):
        raise ProcesoInvalido("El período debe ser AAAA-MM" if tipo == "mensual"
                              else "El período debe ser AAAA-S1 o AAAA-S2")


def motivo_no_aplica(db: Session, org_id: int, accion: str) -> Optional[str]:
    """None si la acción corre para la org; si no, el motivo (para `omitido`)."""
    if accion.startswith("iva_"):
        from app.services.vencimientos import obligaciones_org
        return None if "iva" in obligaciones_org(db, org_id) else "No usa el módulo de IVA"
    modelo, texto = {
        "iibb_proyeccion": (IIBBConfig, "Ingresos Brutos no está activo"),
        "monotributo_control": (MonotributoConfig, "Monotributo no está activo"),
        "sueldos_liquidacion": (ConfigSueldos, "Sueldos no está activo"),
    }[accion]
    activo = db.query(modelo.activo).filter(modelo.organizacion_id == org_id).scalar()
    return None if activo else texto


def _iva_liquidacion(db: Session, org_id: int, periodo: str) -> Tuple[str, Any]:
    existente = db.query(LiquidacionIva).filter_by(organizacion_id=org_id, periodo=periodo).first()
    if existente is not None and existente.estado == "presentada":
        return "ya_presentado", existente
    kwargs: Dict[str, Any] = {}
    if existente is not None:
        kwargs = {"retenciones": existente.retenciones, "percepciones": existente.percepciones}
        prev = db.query(LiquidacionIva.id).filter_by(
            organizacion_id=org_id, periodo=iva_liquidacion_service._periodo_anterior(periodo)).first()
        if prev is None:
            kwargs.update(saldo_tecnico_anterior=existente.saldo_tecnico_anterior,
                          saldo_libre_anterior=existente.saldo_libre_anterior)
    liq = iva_liquidacion_service.calcular_liquidacion(db, org_id, periodo, **kwargs)
    return "calculado", liq


def _ejecutar(db: Session, accion: str, org_id: int, periodo: str) -> Tuple[str, Dict[str, Any], str, int]:
    """(resultado, resumen, tabla de auditoría, id) para una org."""
    if accion == "iva_liquidacion":
        resultado, liq = _iva_liquidacion(db, org_id, periodo)
        return resultado, {"saldo_a_pagar": float(liq.saldo_a_pagar or 0)}, "liquidaciones_iva", liq.id
    if accion == "iva_proyeccion":
        p = iva_service.guardar_o_actualizar_proyeccion(db, org_id, periodo)
        return ("ya_presentado" if p.estado == "presentado" else "calculado",
                {"saldo": float(p.saldo or 0)}, "iva_proyeccion", p.id)
    if accion == "iibb_proyeccion":
        p = iibb_service.guardar_o_actualizar_proyeccion(db, org_id, periodo)
        return ("ya_presentado" if p.estado == "presentado" else "calculado",
                {"impuesto_total": float(p.impuesto_total or 0)}, "iibb_proyeccion", p.id)
    if accion == "monotributo_control":
        c = monotributo_service.guardar_o_actualizar_control(db, org_id, periodo)
        return ("ya_presentado" if c.estado == "revisado" else "calculado",
                {"categoria_sugerida": c.categoria_sugerida, "excede": bool(c.excede)},
                "monotributo_control", c.id)
    liq = sueldos_service.guardar_o_actualizar_liquidacion(db, org_id, periodo)
    return ("ya_presentado" if liq.estado == "presentado" else "calculado",
            {"total_bruto": float(liq.total_bruto or 0)}, "sueldos_liquidacion", liq.id)


def correr(db: Session, accion: str, periodo: str, org_ids: Iterable[int],
           usuario_id: Optional[int]) -> List[Dict[str, Any]]:
    """Corre `accion` para cada org. Nunca lanza por una org: la marca `error`."""
    validar(accion, periodo)
    resultados = []
    for org_id in org_ids:
        org = db.get(Organizacion, org_id)
        if not org:
            continue
        fila: Dict[str, Any] = {"organizacion_id": org_id, "nombre": org.nombre,
                                "resultado": "omitido", "detalle": None, "resumen": None}
        motivo = motivo_no_aplica(db, org_id, accion)
        if motivo:
            fila["detalle"] = motivo
            resultados.append(fila)
            continue
        try:
            resultado, resumen, tabla, ref_id = _ejecutar(db, accion, org_id, periodo)
            fila.update(resultado=resultado, resumen=resumen,
                        detalle="Ya estaba presentado: no se recalculó" if resultado == "ya_presentado" else None)
            if resultado == "calculado":
                registrar_log(db, usuario_id, tabla, ref_id, "CALCULAR_MASIVO",
                              {"periodo": periodo, "accion": accion, **resumen})
            db.commit()
        except _ERRORES_MODULO as ex:
            db.rollback()
            fila.update(resultado="error", detalle=str(ex))
        except Exception as ex:   # noqa: BLE001 — una org rota no corta el lote
            db.rollback()
            logger.exception("Proceso masivo %s org %s falló: %s", accion, org_id, ex)
            fila.update(resultado="error", detalle="Error inesperado al calcular esta organización.")
        resultados.append(fila)
    return resultados


# ── Mis Comprobantes de varios clientes ──────────────────────────────────────

_RE_CUIT = re.compile(r"\b(\d{2})-?(\d{8})-?(\d)\b")


def cuit_del_titulo(contenido: bytes) -> Optional[str]:
    """CUIT del título del Excel de ARCA ("Mis Comprobantes Recibidos - CUIT 30-...")."""
    try:
        wb = openpyxl.load_workbook(io.BytesIO(contenido), read_only=True, data_only=True)
        fila1 = next(wb.active.iter_rows(values_only=True), ())
        wb.close()
    except Exception:   # noqa: BLE001 — archivo ilegible: lo informa el parser
        return None
    titulo = " ".join(str(c) for c in fila1 if c is not None)
    m = _RE_CUIT.search(titulo)
    return "".join(m.groups()) if m else None


def asignar_org(db: Session, cuit: Optional[str], org_ids: Iterable[int]) -> Tuple[Optional[int], Optional[str]]:
    """(org_id, None) si exactamente una org accesible tiene ese CUIT; si no, (None, motivo)."""
    if not cuit:
        return None, "El título del archivo no tiene el CUIT (¿es el Excel de Mis Comprobantes de ARCA?)."
    from app.services.comprobantes_compra_service import cuit_organizacion
    coinciden = [oid for oid in org_ids if cuit_organizacion(db, oid) == cuit]
    if not coinciden:
        return None, (f"No hay una organización con el CUIT {cuit}. Cargalo en Comprobantes por revisar "
                      "→ CUIT de la empresa.")
    if len(coinciden) > 1:
        return None, f"Hay más de una organización con el CUIT {cuit}: subilo desde IVA de la que corresponda."
    return coinciden[0], None
