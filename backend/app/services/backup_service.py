"""Servicio de backup completo en JSON.

Exporta todos los datos de una organización a un dict serializable.
El JSON resultante contiene TODO lo necesario para reconstruir el estado:
extractos, planillas, cheques, pagos, gastos, caja, contabilidad, auditoría.

Uso típico:
    data = export_org_backup(db, org_id=1)
    json.dump(data, open("backup.json", "w"), default=str, indent=2)

Importante: las contraseñas (hashed_password) NUNCA se exportan.
Las fotos en base64 (cheques, OPs) SÍ se exportan — son parte del registro.
"""

import logging
from datetime import datetime, date
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.organizacion import Organizacion
from app.models.user import User
from app.models.cliente import Cliente
from app.models.extracto import ExtractoBancario
from app.models.planilla import Planilla
from app.models.auditoria import AuditoriaLog
from app.models.patron_aprendido import PatronAprendido
from app.models.liquidacion import Liquidacion, CierrePeriodo
from app.models.cheque import Cheque
from app.models.egreso import Egreso, CategoriaEgreso
from app.models.caja import ArqueoDiario
from app.models.contabilidad import PlanCuenta, ReglaContable, Asiento


logger = logging.getLogger(__name__)

BACKUP_VERSION = "1.0"


def _row_to_dict(obj: Any, exclude: Optional[List[str]] = None) -> Dict[str, Any]:
    """Convierte una fila SQLAlchemy a dict serializable a JSON."""
    exclude = exclude or []
    result = {}
    for col in obj.__table__.columns:
        if col.name in exclude:
            continue
        value = getattr(obj, col.name)
        if isinstance(value, (datetime, date)):
            result[col.name] = value.isoformat()
        else:
            result[col.name] = value
    return result


def export_org_backup(db: Session, org_id: int) -> Dict[str, Any]:
    """Devuelve un dict con TODOS los datos de la organización."""
    org = db.query(Organizacion).filter(Organizacion.id == org_id).first()
    if not org:
        raise ValueError(f"Organización {org_id} no encontrada")

    backup: Dict[str, Any] = {
        "backup_version": BACKUP_VERSION,
        "exportado_at": datetime.utcnow().isoformat(),
        "organizacion": _row_to_dict(org),
    }

    # Usuarios — SIN passwords ni datos sensibles
    backup["usuarios"] = [
        _row_to_dict(u, exclude=["hashed_password"])
        for u in db.query(User).filter(User.organizacion_id == org_id).all()
    ]

    backup["clientes"] = [
        _row_to_dict(c) for c in db.query(Cliente).filter(Cliente.organizacion_id == org_id).all()
    ]

    # Extractos + movimientos (anidados)
    extractos: List[Dict[str, Any]] = []
    for e in db.query(ExtractoBancario).filter(ExtractoBancario.organizacion_id == org_id).all():
        ext_dict = _row_to_dict(e)
        ext_dict["movimientos"] = [_row_to_dict(m) for m in e.movimientos]
        extractos.append(ext_dict)
    backup["extractos"] = extractos

    # Planillas + rows (anidados)
    planillas: List[Dict[str, Any]] = []
    for p in db.query(Planilla).filter(Planilla.organizacion_id == org_id).all():
        plan_dict = _row_to_dict(p)
        plan_dict["rows"] = [_row_to_dict(r) for r in p.rows]
        planillas.append(plan_dict)
    backup["planillas"] = planillas

    # Cheques (incluye foto_comprobante en base64)
    backup["cheques"] = [
        _row_to_dict(c) for c in db.query(Cheque).filter(Cheque.organizacion_id == org_id).all()
    ]

    # Egresos (módulo unificado: proveedores, gastos, pagos a clientes) + categorías
    backup["egresos"] = [
        _row_to_dict(e) for e in db.query(Egreso).filter(Egreso.organizacion_id == org_id).all()
    ]
    backup["categorias_egreso"] = [
        _row_to_dict(c) for c in db.query(CategoriaEgreso).filter(CategoriaEgreso.organizacion_id == org_id).all()
    ]

    # Caja: arqueos + egresos en efectivo anidados
    arqueos: List[Dict[str, Any]] = []
    for a in db.query(ArqueoDiario).filter(ArqueoDiario.organizacion_id == org_id).all():
        arq_dict = _row_to_dict(a)
        arq_dict["egresos_efectivo"] = [_row_to_dict(eg) for eg in a.egresos]
        arqueos.append(arq_dict)
    backup["arqueos_diarios"] = arqueos

    # Liquidaciones + detalles
    liquidaciones: List[Dict[str, Any]] = []
    for l in db.query(Liquidacion).filter(Liquidacion.organizacion_id == org_id).all():
        liq_dict = _row_to_dict(l)
        liq_dict["detalles"] = [_row_to_dict(d) for d in l.detalles]
        liquidaciones.append(liq_dict)
    backup["liquidaciones"] = liquidaciones

    backup["cierres_periodo"] = [
        _row_to_dict(c) for c in db.query(CierrePeriodo).filter(CierrePeriodo.organizacion_id == org_id).all()
    ]

    # Contabilidad: plan, reglas, asientos + detalles
    backup["plan_cuentas"] = [
        _row_to_dict(c) for c in db.query(PlanCuenta).filter(PlanCuenta.organizacion_id == org_id).all()
    ]
    backup["reglas_contables"] = [
        _row_to_dict(r) for r in db.query(ReglaContable).filter(ReglaContable.organizacion_id == org_id).all()
    ]
    asientos: List[Dict[str, Any]] = []
    for a in db.query(Asiento).filter(Asiento.organizacion_id == org_id).all():
        a_dict = _row_to_dict(a)
        a_dict["lineas"] = [_row_to_dict(l) for l in a.lineas]
        asientos.append(a_dict)
    backup["asientos"] = asientos

    # Aprendizaje IA
    backup["patrones_aprendidos"] = [
        _row_to_dict(p) for p in db.query(PatronAprendido).filter(PatronAprendido.organizacion_id == org_id).all()
    ]

    # Auditoría — limitar a último año para no inflar el backup
    auditoria = (
        db.query(AuditoriaLog)
        .join(User, AuditoriaLog.usuario_id == User.id)
        .filter(User.organizacion_id == org_id)
        .order_by(AuditoriaLog.timestamp.desc())
        .limit(50000)
        .all()
    )
    backup["auditoria"] = [_row_to_dict(a) for a in auditoria]

    # Resumen al final para verificación rápida
    backup["resumen"] = {
        "usuarios":              len(backup["usuarios"]),
        "clientes":              len(backup["clientes"]),
        "extractos":             len(backup["extractos"]),
        "movimientos_total":     sum(len(e["movimientos"]) for e in backup["extractos"]),
        "planillas":             len(backup["planillas"]),
        "filas_planilla_total":  sum(len(p["rows"]) for p in backup["planillas"]),
        "cheques":               len(backup["cheques"]),
        "egresos":               len(backup["egresos"]),
        "categorias_egreso":     len(backup["categorias_egreso"]),
        "arqueos_diarios":       len(backup["arqueos_diarios"]),
        "egresos_efectivo_total": sum(len(a["egresos_efectivo"]) for a in backup["arqueos_diarios"]),
        "liquidaciones":         len(backup["liquidaciones"]),
        "cierres_periodo":       len(backup["cierres_periodo"]),
        "plan_cuentas":          len(backup["plan_cuentas"]),
        "reglas_contables":      len(backup["reglas_contables"]),
        "asientos":              len(backup["asientos"]),
        "patrones_aprendidos":   len(backup["patrones_aprendidos"]),
        "auditoria_logs":        len(backup["auditoria"]),
    }

    logger.info("Backup org %s generado: %s", org_id, backup["resumen"])
    return backup
