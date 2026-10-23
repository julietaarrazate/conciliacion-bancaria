"""Router del importador de extractos bancarios en PDF.

Prefix `/extractos-pdf` (no `/extractos/pdf`: lo capturaría `/extractos/{extracto_id}`).

  POST   /importar                      — sube el PDF y lo lee (borrador para revisar)
  GET    /borradores                    — pendientes (procesando / listo / error) o ?estado=
  GET    /borradores/{id}               — detalle para la pantalla de revisión (polling)
  POST   /borradores/{id}/confirmar     — guarda como extracto nuevo o agrega a uno existente
  POST   /borradores/{id}/descartar
  GET    /moldes                        — formatos aprendidos de la org
  DELETE /moldes/{id}                   — olvida un formato aprendido

Permisos (3 capas, ver SECURITY_MODEL): importar / confirmar / descartar → `upload_files`;
leer → cualquier usuario de la org; borrar un formato aprendido → `delete_records`.
Multi-tenant: todo filtra por la org resuelta (`?org_id=` si puede cambiar de org);
un borrador o formato de otra org da 404.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, Request, UploadFile
from slowapi import Limiter
from app.services.limites import ip_cliente
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal, get_db
from app.middleware.auth import can_switch_org, get_current_user, require_permission
from app.models.user import User
from app.schemas.extracto_pdf import (
    BorradoresExtractoPdfOut, BorradorExtractoOut, ConfirmarExtractoPdfIn, ConfirmarExtractoPdfOut,
    MoldesExtractoPdfOut, OkOut,
)
from app.services import extracto_pdf_service as svc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/extractos-pdf", tags=["extractos-pdf"])
limiter = Limiter(key_func=ip_cliente)

# Sesión del procesamiento en segundo plano (los tests la reemplazan).
_session_factory = SessionLocal


def _org_id(current_user: User, org_id: Optional[int]) -> int:
    return org_id if (org_id and can_switch_org(current_user, org_id)) else (current_user.organizacion_id or 1)


def _http(ex: svc.ExtractoPdfServicioError) -> HTTPException:
    # Detalle siempre string: el interceptor de axios del frontend convierte objetos en JSON crudo.
    return HTTPException(ex.status, ex.mensaje)


def _procesar_en_fondo(**kwargs) -> None:
    # `_session_factory` se resuelve al ejecutar (monkeypatcheable en tests).
    svc.procesar_en_fondo(_session_factory, **kwargs)


@router.post("/importar", response_model=BorradorExtractoOut)
@limiter.limit("10/minute")
def importar(
    request: Request,
    background: BackgroundTasks,
    file: UploadFile = File(...),
    org_id: Optional[int] = Query(None),
    forzar_ia: bool = Query(False),
    banco: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("upload_files")),
):
    """Lee el PDF y deja un borrador para revisar (no guarda el extracto todavía).

    `def` sincrónico: la lectura (pdfminer) corre en el threadpool, no bloquea el event loop."""
    oid = _org_id(current_user, org_id)
    max_bytes = get_settings().max_file_size
    contenido = file.file.read(max_bytes + 1)
    try:
        nombre = svc.validar_archivo(file.filename, contenido, max_bytes)
        borrador, trabajo = svc.importar_pdf(
            db, org_id=oid, usuario_id=current_user.id, nombre_archivo=nombre, contenido=contenido,
            forzar_ia=forzar_ia, banco_usuario=banco,
        )
        salida = svc.borrador_out(db, borrador)
    except svc.ExtractoPdfServicioError as ex:
        raise _http(ex)
    if trabajo:
        background.add_task(_procesar_en_fondo, **trabajo)
    return salida


@router.get("/borradores", response_model=BorradoresExtractoPdfOut)
def listar_borradores(
    estado: Optional[str] = Query(None),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        items = svc.listar_borradores(db, _org_id(current_user, org_id), estado)
    except svc.ExtractoPdfServicioError as ex:
        raise _http(ex)
    return {"items": [svc.borrador_resumen(b) for b in items]}


@router.get("/borradores/{borrador_id}", response_model=BorradorExtractoOut)
def detalle_borrador(
    borrador_id: int,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        b = svc.obtener_borrador(db, _org_id(current_user, org_id), borrador_id)
        return svc.borrador_out(db, b)
    except svc.ExtractoPdfServicioError as ex:
        raise _http(ex)


@router.post("/borradores/{borrador_id}/confirmar", response_model=ConfirmarExtractoPdfOut)
def confirmar_borrador(
    borrador_id: int,
    body: ConfirmarExtractoPdfIn,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("upload_files")),
):
    try:
        b = svc.obtener_borrador(db, _org_id(current_user, org_id), borrador_id)
        return svc.confirmar_borrador(db, b, body, current_user.id)
    except svc.ExtractoPdfServicioError as ex:
        raise _http(ex)


@router.post("/borradores/{borrador_id}/descartar", response_model=OkOut)
def descartar_borrador(
    borrador_id: int,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("upload_files")),
):
    try:
        b = svc.obtener_borrador(db, _org_id(current_user, org_id), borrador_id)
        svc.descartar_borrador(db, b, current_user.id)
    except svc.ExtractoPdfServicioError as ex:
        raise _http(ex)
    return {"ok": True}


@router.get("/moldes", response_model=MoldesExtractoPdfOut)
def listar_moldes(
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return {"items": [svc.molde_out(m) for m in svc.listar_moldes(db, _org_id(current_user, org_id))]}


@router.delete("/moldes/{molde_id}", response_model=OkOut)
def borrar_molde(
    molde_id: int,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("delete_records")),
):
    try:
        svc.borrar_molde(db, _org_id(current_user, org_id), molde_id, current_user.id)
    except svc.ExtractoPdfServicioError as ex:
        raise _http(ex)
    return {"ok": True}
