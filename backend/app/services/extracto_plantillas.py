"""Plantillas de lectura de extractos Excel/CSV: buscar y guardar (por organización).

La lectura en sí está en `extracto_mapper` (puro). Acá solo la persistencia:
- `plantillas_de_org`: {firma: {"id", "mapeo", "banco_clave", "banco_confirmado"}}
  para pasarle al lector.
- `guardar_plantilla`: alta o actualización (upsert por org + firma) después de
  importar un extracto con un mapeo confirmado por la persona.
- `marcar_uso`: suma un uso cuando una plantilla se aplicó sola.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.extracto_plantilla import PlantillaExtractoExcel
from app.services.auditoria import registrar_log


def plantillas_de_org(db: Session, org_id: int) -> dict:
    filas = (
        db.query(PlantillaExtractoExcel)
        .filter(PlantillaExtractoExcel.organizacion_id == org_id)
        .all()
    )
    return {
        p.firma: {
            "id": p.id,
            "mapeo": p.mapeo or {},
            "banco_clave": p.banco_clave,
            # El banco lo eligió la persona (no lo adivinó el sistema): se guarda en
            # el JSON del mapeo para no agregar una columna.
            "banco_confirmado": bool((p.mapeo or {}).get("banco_confirmado")),
        }
        for p in filas
    }


def guardar_plantilla(
    db: Session,
    *,
    org_id: int,
    firma: Optional[str],
    banco_clave: Optional[str],
    mapeo: dict,
    encabezados: list,
    usuario_id: int,
    banco_confirmado: bool = False,
) -> Optional[PlantillaExtractoExcel]:
    """Guarda (o actualiza) la plantilla de este formato. Sin firma (archivo sin
    renglón de títulos) no hay con qué reconocerlo la próxima vez: no se guarda."""
    if not firma:
        return None
    # La fila del encabezado y la hoja se recalculan en cada archivo (pueden moverse).
    guardar = {k: v for k, v in mapeo.items() if k not in ("hoja", "fila_encabezado", "banco_confirmado")}
    p = (
        db.query(PlantillaExtractoExcel)
        .filter(PlantillaExtractoExcel.organizacion_id == org_id,
                PlantillaExtractoExcel.firma == firma)
        .first()
    )
    accion = "UPDATE"
    if p is None:
        accion = "INSERT"
        p = PlantillaExtractoExcel(organizacion_id=org_id, firma=firma, usos=0, creado_por=usuario_id)
        db.add(p)
    # Un banco ya confirmado por la persona no se pisa con uno adivinado.
    if banco_confirmado or not (p.mapeo or {}).get("banco_confirmado"):
        p.banco_clave = banco_clave
        if banco_confirmado:
            guardar["banco_confirmado"] = True
    else:
        guardar["banco_confirmado"] = True
    p.encabezados = encabezados
    p.mapeo = guardar
    p.usos = (p.usos or 0) + 1
    p.ultimo_uso_at = datetime.utcnow()
    db.commit()
    db.refresh(p)
    registrar_log(db, usuario_id, "plantillas_extracto_excel", p.id, accion,
                  {"banco": p.banco_clave, "banco_confirmado": bool(guardar.get("banco_confirmado")),
                   "columnas": guardar.get("columnas"), "signo": guardar.get("signo")},
                  organizacion_id=org_id)
    return p


def marcar_uso(db: Session, plantilla_id: Optional[int], org_id: int) -> None:
    if not plantilla_id:
        return
    p = (
        db.query(PlantillaExtractoExcel)
        .filter(PlantillaExtractoExcel.id == plantilla_id,
                PlantillaExtractoExcel.organizacion_id == org_id)
        .first()
    )
    if p is not None:
        p.usos = (p.usos or 0) + 1
        p.ultimo_uso_at = datetime.utcnow()
        db.commit()
