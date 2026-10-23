"""Procesos masivos: un cálculo para varias organizaciones y Mis Comprobantes de
varias organizaciones juntos (ver services/procesos_masivos.py)."""
import re
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import require_permission
from app.models.organizacion import Organizacion
from app.models.user import User
from app.services import procesos_masivos as svc
from app.services.acceso_orgs import orgs_accesibles
from app.services.auditoria import registrar_log
from app.services.limites import leer_planilla
from app.services.comparar_mis_comprobantes import comparar, importar_filas
from app.services.mis_comprobantes_parser import parsear_mis_comprobantes

router = APIRouter(prefix="/procesos-masivos", tags=["procesos-masivos"])

MAX_ARCHIVOS = 50


@router.get("/acciones")
def listar_acciones(current_user: User = Depends(require_permission("view_accounting"))):
    return [{"accion": k, "nombre": n, "periodo": t} for k, (n, t) in svc.ACCIONES.items()]


class CalcularIn(BaseModel):
    accion: str
    periodo: str
    org_ids: Optional[List[int]] = None   # None = todas las accesibles


@router.post("/calcular")
def calcular(
    body: CalcularIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage_finance")),
):
    """Corre la acción para cada org accesible (o las pedidas que sean accesibles)."""
    try:
        svc.validar(body.accion, body.periodo)
    except svc.ProcesoInvalido as ex:
        raise HTTPException(422, str(ex))
    org_ids = orgs_accesibles(db, current_user, body.org_ids)
    resultados = svc.correr(db, body.accion, body.periodo, org_ids, current_user.id)
    return {"accion": body.accion, "periodo": body.periodo, "resultados": resultados}


# ── Mis Comprobantes de varias organizaciones ──────────────────────────────────────

def _validar_mc(direccion: str, periodo: str, files: List[UploadFile]) -> None:
    if direccion not in ("emitido", "recibido"):
        raise HTTPException(422, "direccion debe ser 'emitido' o 'recibido'")
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", periodo or ""):
        raise HTTPException(422, "El período debe ser AAAA-MM")
    if not files or len(files) > MAX_ARCHIVOS:
        raise HTTPException(422, f"Subí entre 1 y {MAX_ARCHIVOS} archivos")


async def _leer(db: Session, user: User, direccion: str, files: List[UploadFile]):
    """Por archivo: (nombre, org_id|None, nombre_org, filas|None, error|None, cuit)."""
    accesibles = orgs_accesibles(db, user)
    out = []
    for f in files:
        contenido = await leer_planilla(f)
        cuit = svc.cuit_del_titulo(contenido)
        org_id, error = svc.asignar_org(db, cuit, accesibles)
        filas = None
        if org_id is not None:
            try:
                filas = parsear_mis_comprobantes(contenido, direccion)
            except ValueError as ex:
                org_id, error = None, str(ex)
        org = db.get(Organizacion, org_id) if org_id else None
        out.append((f.filename, org_id, org.nombre if org else None, filas, error, cuit))
    return out


@router.post("/mis-comprobantes/comparar")
async def comparar_varios(
    direccion: str = Query(...),
    periodo: str = Query(...),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage_finance")),
):
    """Asigna cada Excel a su org por el CUIT del título y compara con lo cargado. No importa nada."""
    _validar_mc(direccion, periodo, files)
    archivos = []
    for nombre, org_id, org_nombre, filas, error, cuit in await _leer(db, current_user, direccion, files):
        item = {"archivo": nombre, "cuit": cuit, "organizacion_id": org_id, "nombre": org_nombre,
                "error": error, "faltantes": 0, "iva_faltante": 0.0, "ya_cargados": 0,
                "importes_distintos": 0, "solo_en_cuadra": 0, "fuera_de_periodo": 0}
        if filas is not None:
            r = comparar(db, org_id, direccion, periodo, filas)
            item.update(faltantes=len(r["faltantes"]), iva_faltante=float(r["iva_faltante"]),
                        ya_cargados=len(r["ya_cargados"]),
                        importes_distintos=sum(1 for x in r["ya_cargados"] if x["importe_distinto"]),
                        solo_en_cuadra=len(r["solo_en_cuadra"]), fuera_de_periodo=r["fuera_de_periodo"])
        archivos.append(item)
    return {"direccion": direccion, "periodo": periodo, "archivos": archivos}


@router.post("/mis-comprobantes/importar")
async def importar_varios(
    direccion: str = Query(...),
    periodo: str = Query(...),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage_finance")),
):
    """Importa lo que falta de cada Excel en su org. Cada org queda en su propio lote
    (se deshace con DELETE /iva/comprobantes/lote/{lote}?org_id=)."""
    _validar_mc(direccion, periodo, files)
    archivos = []
    for nombre, org_id, org_nombre, filas, error, cuit in await _leer(db, current_user, direccion, files):
        item = {"archivo": nombre, "cuit": cuit, "organizacion_id": org_id, "nombre": org_nombre,
                "error": error, "importados": 0, "duplicados": 0, "lote": None}
        if filas is not None:
            r = importar_filas(db, org_id, direccion, periodo, filas, nombre)
            item.update(importados=r["importados"], duplicados=r["duplicados"], lote=r["lote"])
            registrar_log(db, current_user.id, "comprobantes_iva", 0, "IMPORTAR_MASIVO",
                          {"organizacion_id": org_id, "direccion": direccion, **r},
                          organizacion_id=org_id)
            db.commit()
        archivos.append(item)
    return {"direccion": direccion, "periodo": periodo, "archivos": archivos}
