"""Grilla de vencimientos impositivos por organización.

Fuentes de cada dato:
- **Fecha**: `CalendarioVencimiento` (general, cargado mes a mes desde la web de
  ARCA por el superadmin) según la terminación del CUIT de la org. Monotributo,
  si no está cargado, vence el día 20 del mes o el día hábil siguiente si cae
  sábado/domingo (no conoce feriados: un feriado se corrige cargando la fecha).
  ARCA no publica un calendario anual descargable y cambia fechas por RG, así
  que **no se inventan fechas**: sin calendario cargado la celda dice
  "sin_calendario".
- **CUIT**: el de la org (`comprobantes_compra_service.cuit_organizacion`).
- **Qué obligaciones tiene**: `configuracion["obligaciones"]` si está, o lo que
  digan los módulos activos (Monotributo → monotributo; si no es monotributista
  y usa IVA → iva; IIBB en Convenio Multilateral → iibb_cm; Sueldos → f931).
- **Presentado**: lo que registran los módulos (IVA liquidación/proyección,
  IIBB, F931) o una marca manual (`VencimientoMarcado`).

Mes de la grilla = mes en que VENCE. IVA, IIBB CM y F931 de un período vencen el
mes siguiente; la cuota de Monotributo vence en el mismo mes.
"""
from datetime import date, timedelta
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy.orm import Session

from app.models.contabilidad import PlanCuenta
from app.models.iibb import IIBBConfig, ProyeccionIIBB
from app.models.iva_liquidacion import LiquidacionIva
from app.models.monotributo import MonotributoConfig
from app.models.organizacion import Organizacion
from app.models.proyeccion_iva import ProyeccionIva
from app.models.sueldos import ConfigSueldos, LiquidacionSueldoPeriodo
from app.models.vencimientos import IMPUESTOS, CalendarioVencimiento, VencimientoMarcado

# Impuestos cuyo período vence el mes siguiente (el resto, el mismo mes).
_VENCE_MES_SIGUIENTE = {"iva", "iibb_cm", "f931"}
DIA_MONOTRIBUTO = 20


def _mes_anterior(mes: str) -> str:
    y, m = int(mes[:4]), int(mes[5:7])
    y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    return f"{y:04d}-{m:02d}"


def periodo_fiscal(impuesto: str, mes_vencimiento: str) -> str:
    """Período fiscal de `impuesto` que vence en `mes_vencimiento` ('YYYY-MM')."""
    return _mes_anterior(mes_vencimiento) if impuesto in _VENCE_MES_SIGUIENTE else mes_vencimiento


def dia_habil(d: date) -> date:
    """Sábado/domingo → lunes siguiente. No conoce feriados."""
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def _terminacion(cuit: Optional[str]) -> Optional[int]:
    digitos = "".join(c for c in str(cuit or "") if c.isdigit())
    return int(digitos[-1]) if len(digitos) == 11 else None


def fecha_vencimiento(db: Session, impuesto: str, periodo: str, cuit: Optional[str]) -> Optional[date]:
    """Fecha de vencimiento de `impuesto` para `periodo` y ese CUIT, o None."""
    term = _terminacion(cuit)
    if term is None:
        return None
    fila = db.query(CalendarioVencimiento.fecha).filter(
        CalendarioVencimiento.impuesto == impuesto,
        CalendarioVencimiento.periodo == periodo,
        CalendarioVencimiento.terminacion_desde <= term,
        CalendarioVencimiento.terminacion_hasta >= term,
    ).first()
    if fila:
        return fila[0]
    if impuesto == "monotributo":
        return dia_habil(date(int(periodo[:4]), int(periodo[5:7]), DIA_MONOTRIBUTO))
    return None


def _cuit_org(db: Session, org_id: int) -> Optional[str]:
    from app.services.comprobantes_compra_service import cuit_organizacion
    return cuit_organizacion(db, org_id)


def obligaciones_org(db: Session, org_id: int) -> List[str]:
    """Obligaciones de la org, en el orden de IMPUESTOS-ish: iva/monotributo, iibb_cm, f931."""
    org = db.get(Organizacion, org_id)
    explicitas = (org.configuracion or {}).get("obligaciones") if org else None
    if isinstance(explicitas, list):
        return [i for i in IMPUESTOS if i in explicitas]

    out: List[str] = []
    mono = db.query(MonotributoConfig.activo).filter(MonotributoConfig.organizacion_id == org_id).scalar()
    if mono:
        out.append("monotributo")
    else:
        usa_iva = (
            db.query(PlanCuenta.id).filter(PlanCuenta.organizacion_id == org_id,
                                           PlanCuenta.tasa_iva.isnot(None)).first()
            or db.query(LiquidacionIva.id).filter(LiquidacionIva.organizacion_id == org_id).first()
        )
        if usa_iva:
            out.append("iva")
    iibb = db.query(IIBBConfig).filter(IIBBConfig.organizacion_id == org_id).first()
    if iibb and iibb.activo and iibb.modo == "convenio_multilateral":
        out.append("iibb_cm")
    if db.query(ConfigSueldos.activo).filter(ConfigSueldos.organizacion_id == org_id).scalar():
        out.append("f931")
    return out


def presentado_por_modulo(db: Session, org_id: int, impuesto: str, periodo: str) -> bool:
    if impuesto == "iva":
        return bool(
            db.query(LiquidacionIva.id).filter_by(organizacion_id=org_id, periodo=periodo,
                                                   estado="presentada").first()
            or db.query(ProyeccionIva.id).filter_by(organizacion_id=org_id, periodo=periodo,
                                                     estado="presentado").first()
        )
    if impuesto == "iibb_cm":
        return db.query(ProyeccionIIBB.id).filter_by(organizacion_id=org_id, periodo=periodo,
                                                      estado="presentado").first() is not None
    if impuesto == "f931":
        return db.query(LiquidacionSueldoPeriodo.id).filter_by(organizacion_id=org_id, periodo=periodo,
                                                                estado="presentado").first() is not None
    return False   # la cuota de Monotributo no la registra ningún módulo


def _marcado(db: Session, org_id: int, impuesto: str, periodo: str) -> bool:
    return db.query(VencimientoMarcado.id).filter_by(organizacion_id=org_id, impuesto=impuesto,
                                                     periodo=periodo).first() is not None


def celda(db: Session, org_id: int, cuit: Optional[str], impuesto: str, mes: str,
          hoy: date, dias_aviso: int = 3) -> Dict[str, Any]:
    periodo = periodo_fiscal(impuesto, mes)
    fecha = fecha_vencimiento(db, impuesto, periodo, cuit)
    motivo = None if fecha else ("sin_cuit" if _terminacion(cuit) is None else "sin_calendario")
    presentado_por = ("modulo" if presentado_por_modulo(db, org_id, impuesto, periodo)
                      else "manual" if _marcado(db, org_id, impuesto, periodo) else None)
    if presentado_por:
        estado = "presentado"
    elif fecha and fecha < hoy:
        estado = "vencido"
    elif fecha and (fecha - hoy).days <= dias_aviso:
        estado = "proximo"
    else:
        estado = "pendiente"
    return {"impuesto": impuesto, "nombre": IMPUESTOS[impuesto], "periodo": periodo, "fecha": fecha,
            "motivo": motivo, "estado": estado, "presentado_por": presentado_por}


def grilla(db: Session, org_ids: Iterable[int], mes: str, hoy: date) -> List[Dict[str, Any]]:
    filas = []
    for org_id in org_ids:
        org = db.get(Organizacion, org_id)
        if not org:
            continue
        cuit = _cuit_org(db, org_id)
        filas.append({
            "organizacion_id": org_id,
            "nombre": org.nombre,
            "cuit": cuit,
            "obligaciones": [celda(db, org_id, cuit, imp, mes, hoy) for imp in obligaciones_org(db, org_id)],
        })
    return filas


def pendientes_proximos(db: Session, hoy: date, dias: int = 3) -> List[Dict[str, Any]]:
    """Obligaciones sin presentar que vencen entre hoy y hoy+`dias` (para el aviso diario)."""
    meses = sorted({f"{d.year:04d}-{d.month:02d}" for d in (hoy, hoy + timedelta(days=dias))})
    org_ids = [o.id for o in db.query(Organizacion.id).filter(Organizacion.activo.isnot(False))
               .order_by(Organizacion.id).all()]
    out = []
    for mes in meses:
        for fila in grilla(db, org_ids, mes, hoy):
            for c in fila["obligaciones"]:
                if c["estado"] == "proximo" and c["fecha"] >= hoy:
                    out.append({"organizacion_id": fila["organizacion_id"], "nombre": fila["nombre"], **c})
    return out


# ── Calendario ───────────────────────────────────────────────────────────────

class CalendarioInvalido(ValueError):
    pass


def validar_bloques(fechas: List[Dict[str, Any]]) -> None:
    """Los bloques tienen que cubrir las terminaciones 0..9 exactamente una vez."""
    cubiertas: List[int] = []
    for f in fechas:
        d, h = int(f["terminacion_desde"]), int(f["terminacion_hasta"])
        if not (0 <= d <= h <= 9):
            raise CalendarioInvalido(f"Bloque de terminación inválido: {d}-{h}")
        cubiertas.extend(range(d, h + 1))
    if sorted(cubiertas) != list(range(10)):
        raise CalendarioInvalido("Los bloques tienen que cubrir las terminaciones 0 a 9 sin repetirse")


def guardar_calendario(db: Session, impuesto: str, periodo: str, fechas: List[Dict[str, Any]],
                       fuente: Optional[str], usuario_id: Optional[int]) -> List[CalendarioVencimiento]:
    """Reemplaza el calendario de (impuesto, período) por los bloques dados."""
    if impuesto not in IMPUESTOS:
        raise CalendarioInvalido(f"Impuesto desconocido: {impuesto}")
    validar_bloques(fechas)
    db.query(CalendarioVencimiento).filter_by(impuesto=impuesto, periodo=periodo).delete()
    filas = [CalendarioVencimiento(impuesto=impuesto, periodo=periodo,
                                   terminacion_desde=int(f["terminacion_desde"]),
                                   terminacion_hasta=int(f["terminacion_hasta"]),
                                   fecha=f["fecha"], fuente=fuente, cargado_por=usuario_id)
             for f in fechas]
    db.add_all(filas)
    db.flush()
    return filas


# Fechas confirmadas al cargar el módulo (oct 2026). El resto se carga mes a mes
# desde https://www.argentina.gob.ar/arca/vencimientos — no se precargan fechas
# de terceros que no coinciden entre sí.
_ARCA = "argentina.gob.ar/arca/vencimientos (oct 2026)"
_SEMILLA = [
    ("iva", "2026-09", [(0, 1, 19), (2, 3, 20), (4, 5, 21), (6, 7, 22), (8, 9, 23)], _ARCA),
    ("f931", "2026-09", [(0, 3, 9), (4, 6, 13), (7, 9, 14)], _ARCA),
    ("iibb_cm", "2026-09", [(0, 2, 15), (3, 5, 16), (6, 7, 19), (8, 9, 20)],
     "COMARB RG CA 20/2025 (calendario 2026)"),
]


def sembrar_calendario_inicial(db: Session) -> None:
    """Carga las fechas confirmadas si ese (impuesto, período) todavía no tiene nada. Idempotente."""
    for impuesto, periodo, bloques, fuente in _SEMILLA:
        if db.query(CalendarioVencimiento.id).filter_by(impuesto=impuesto, periodo=periodo).first():
            continue
        y, m = int(periodo[:4]), int(periodo[5:7]) + 1
        y, m = (y + 1, 1) if m == 13 else (y, m)
        for d, h, dia in bloques:
            db.add(CalendarioVencimiento(impuesto=impuesto, periodo=periodo, terminacion_desde=d,
                                         terminacion_hasta=h, fecha=date(y, m, dia), fuente=fuente))
    db.commit()
