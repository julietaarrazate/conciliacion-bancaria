"""Router de "Comprobantes por revisar" (facturas de compra por mail + lectura con IA).

Endpoints (prefix /comprobantes-compra):
  GET  /buzon                      — dirección de mail de la org (o cómo activarla)
  POST /buzon/activar?regenerar=   — crea la dirección / genera una nueva
  POST /subir                      — sube hasta 10 PDF/fotos (se leen con IA en segundo plano)
  GET  ""                          — bandeja (sin el archivo), filtro por estado
  GET  /{id}                       — detalle con el archivo para verlo al lado
  POST /{id}/reprocesar            — vuelve a leerlo con IA
  POST /{id}/confirmar             — crea el comprobante en IVA (+ Pago opcional)
  POST /{id}/descartar
  POST /webhook/resend             — Resend Inbound (email.received), sin auth, firma Svix

Permisos (3 capas, ver SECURITY_MODEL):
  ver bandeja / buzón        → view_accounting
  subir / reprocesar / descartar → upload_files
  confirmar                  → manage_finance (igual que importar "Mis Comprobantes")
  activar / regenerar buzón  → admin_accounting
"""

from __future__ import annotations

import json
import logging
from datetime import date
from typing import Optional

from fastapi import (
    APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, Request, UploadFile,
)
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal, get_db
from app.middleware.auth import can_switch_org, require_permission
from app.models.comprobante_compra import BorradorComprobante, BuzonComprobantes, ESTADOS_BORRADOR
from app.models.user import User
from app.services import comprobantes_compra_service as svc
from app.services.auditoria import registrar_log
from app.services.storage import upload_comprobante

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/comprobantes-compra", tags=["comprobantes-compra"])

# Sesión para el procesamiento en segundo plano (los tests la reemplazan).
_session_factory = SessionLocal


def _org_id(current_user: User, org_id: Optional[int]) -> int:
    if can_switch_org(current_user, org_id) and org_id:
        return org_id
    return current_user.organizacion_id or 1


def _borrador_con_acceso(db: Session, current_user: User, borrador_id: int, org_id: Optional[int]) -> BorradorComprobante:
    oid = _org_id(current_user, org_id)
    b = db.query(BorradorComprobante).filter(
        BorradorComprobante.id == borrador_id,
        BorradorComprobante.organizacion_id == oid,
    ).first()
    if not b:
        raise HTTPException(404, "Comprobante no encontrado")
    return b


def _borrador_dict(b: BorradorComprobante, con_archivo: bool = False) -> dict:
    return {
        "id": b.id,
        "organizacion_id": b.organizacion_id,
        "origen": b.origen,
        "estado": b.estado,
        "remitente": b.remitente,
        "asunto": b.asunto,
        "archivo_nombre": b.archivo_nombre,
        "archivo_mime": b.archivo_mime,
        "archivo": b.archivo if con_archivo else None,
        "datos": b.datos,
        "alertas": b.alertas or [],
        "error": b.error,
        "comprobante_iva_id": b.comprobante_iva_id,
        "egreso_id": b.egreso_id,
        "confirmado_at": b.confirmado_at,
        "created_at": b.created_at,
    }


def _http(ex: svc.ComprobanteCompraError) -> HTTPException:
    return HTTPException(ex.status, str(ex))


# ── Procesamiento en segundo plano ─────────────────────────────────

def _procesar_en_fondo(borrador_ids: list[int], contenidos: Optional[dict[int, tuple[str, bytes]]] = None) -> None:
    """Lee con IA cada borrador. Para mails, primero baja el adjunto de Resend."""
    db = _session_factory()
    try:
        settings = get_settings()
        for bid in borrador_ids:
            b = db.query(BorradorComprobante).filter(BorradorComprobante.id == bid).first()
            if not b or b.estado != "procesando":
                continue
            mime, contenido = (contenidos or {}).get(bid, (None, None))
            if contenido is None and b.origen == "email" and not b.archivo:
                try:
                    if not settings.resend_api_key:
                        raise svc.ComprobanteCompraError("Falta RESEND_API_KEY para bajar el adjunto.")
                    contenido = svc.descargar_adjunto_resend(settings.resend_api_key, b.email_id, b.adjunto_id)
                    mime = b.archivo_mime
                    b.archivo = upload_comprobante(svc.a_data_url(mime, contenido), prefix=f"compras/{b.organizacion_id}")
                    db.commit()
                except Exception as ex:
                    logger.warning("No se pudo bajar el adjunto del borrador %s: %s", bid, ex)
                    b.estado = "error"
                    b.error = str(ex) if isinstance(ex, svc.ComprobanteCompraError) else \
                        "No se pudo descargar el adjunto del mail."
                    db.commit()
                    continue
            svc.procesar_borrador(db, b, contenido=contenido, mime=mime)
    finally:
        db.close()


# ── Buzón ──────────────────────────────────────────────────────────

def _buzon_dict(buzon: Optional[BuzonComprobantes]) -> dict:
    dominio = get_settings().inbound_email_domain.strip()
    configurado = bool(dominio and get_settings().resend_inbound_secret)
    return {
        "configurado": configurado,
        "activo": bool(buzon and buzon.activo),
        "direccion": svc.direccion_buzon(buzon.token, dominio) if (buzon and buzon.activo and configurado) else None,
    }


@router.get("/buzon")
def get_buzon(
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("view_accounting")),
):
    oid = _org_id(current_user, org_id)
    buzon = db.query(BuzonComprobantes).filter(BuzonComprobantes.organizacion_id == oid).first()
    return _buzon_dict(buzon)


@router.post("/buzon/activar")
def activar_buzon(
    regenerar: bool = Query(False),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin_accounting")),
):
    oid = _org_id(current_user, org_id)
    buzon = svc.activar_buzon(db, oid, regenerar=regenerar)
    registrar_log(db, current_user.id, "buzon_comprobantes", buzon.id,
                  "REGENERAR" if regenerar else "ACTIVAR", {"organizacion_id": oid})
    db.commit()
    return _buzon_dict(buzon)


# ── Subida manual ──────────────────────────────────────────────────

@router.post("/subir")
async def subir_comprobantes(
    background: BackgroundTasks,
    files: list[UploadFile] = File(...),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("upload_files")),
):
    oid = _org_id(current_user, org_id)
    if not files:
        raise HTTPException(400, "No llegó ningún archivo")
    if len(files) > svc.MAX_ARCHIVOS_POR_SUBIDA:
        raise HTTPException(400, f"Podés subir hasta {svc.MAX_ARCHIVOS_POR_SUBIDA} archivos a la vez")

    leidos = []
    for f in files:
        mime = svc.mime_normalizado(f.content_type, f.filename)
        if not mime:
            raise HTTPException(400, f"{f.filename}: solo se aceptan PDF, JPG, PNG o WebP")
        contenido = await f.read()
        if not contenido:
            raise HTTPException(400, f"{f.filename}: el archivo está vacío")
        if len(contenido) > svc.MAX_ARCHIVO_BYTES:
            raise HTTPException(400, f"{f.filename}: supera los 5 MB")
        leidos.append((f.filename, mime, contenido))

    creados = []
    contenidos: dict[int, tuple[str, bytes]] = {}
    for nombre, mime, contenido in leidos:
        b = BorradorComprobante(
            organizacion_id=oid, origen="subida", estado="procesando",
            archivo_nombre=(nombre or "comprobante")[:255], archivo_mime=mime,
            archivo=upload_comprobante(svc.a_data_url(mime, contenido), prefix=f"compras/{oid}"),
            creado_por=current_user.id,
        )
        db.add(b)
        db.flush()
        creados.append(b)
        contenidos[b.id] = (mime, contenido)
    db.commit()

    registrar_log(db, current_user.id, "borradores_comprobante", 0, "SUBIR",
                  {"cantidad": len(creados), "ids": [b.id for b in creados]})
    db.commit()
    background.add_task(_procesar_en_fondo, [b.id for b in creados], contenidos)
    return {"borradores": [_borrador_dict(b) for b in creados]}


# ── Bandeja ────────────────────────────────────────────────────────

@router.get("")
def listar_borradores(
    estado: Optional[str] = Query(None, description="Estado o 'pendientes' (procesando+listo+error+sin_adjunto)"),
    limit: int = Query(100, ge=1, le=500),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("view_accounting")),
):
    oid = _org_id(current_user, org_id)
    q = db.query(BorradorComprobante).filter(BorradorComprobante.organizacion_id == oid)
    if estado == "pendientes":
        q = q.filter(BorradorComprobante.estado.in_(["procesando", "listo", "error", "sin_adjunto"]))
    elif estado:
        if estado not in ESTADOS_BORRADOR:
            raise HTTPException(422, "Estado inválido")
        q = q.filter(BorradorComprobante.estado == estado)
    items = q.order_by(BorradorComprobante.created_at.desc(), BorradorComprobante.id.desc()).limit(limit).all()

    conteo = {e: 0 for e in ESTADOS_BORRADOR}
    for (e,) in db.query(BorradorComprobante.estado).filter(BorradorComprobante.organizacion_id == oid).all():
        conteo[e] = conteo.get(e, 0) + 1
    return {"items": [_borrador_dict(b) for b in items], "conteo": conteo}


@router.get("/{borrador_id}")
def detalle_borrador(
    borrador_id: int,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("view_accounting")),
):
    return _borrador_dict(_borrador_con_acceso(db, current_user, borrador_id, org_id), con_archivo=True)


@router.post("/{borrador_id}/reprocesar")
def reprocesar_borrador(
    borrador_id: int,
    background: BackgroundTasks,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("upload_files")),
):
    b = _borrador_con_acceso(db, current_user, borrador_id, org_id)
    if b.estado not in ("listo", "error"):
        raise HTTPException(409, "Solo se pueden volver a leer los comprobantes pendientes")
    b.estado = "procesando"
    b.error = None
    db.commit()
    background.add_task(_procesar_en_fondo, [b.id])
    return _borrador_dict(b)


class ConfirmarIn(BaseModel):
    datos: Optional[dict] = None
    periodo: Optional[str] = None
    registrar_pago: bool = False
    fecha_pago: Optional[date] = None


@router.post("/{borrador_id}/confirmar")
def confirmar(
    borrador_id: int,
    body: ConfirmarIn,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage_finance")),
):
    b = _borrador_con_acceso(db, current_user, borrador_id, org_id)
    try:
        resultado = svc.confirmar_borrador(
            db, b, body.datos, current_user.id,
            periodo=body.periodo, registrar_pago=body.registrar_pago, fecha_pago=body.fecha_pago,
        )
    except svc.ComprobanteCompraError as ex:
        raise _http(ex)
    registrar_log(db, current_user.id, "borradores_comprobante", b.id, "CONFIRMAR", {
        "comprobante_iva_id": resultado["comprobante_iva_id"],
        "egreso_id": resultado["egreso_id"],
        "periodo": resultado["periodo"],
        "total": (b.datos or {}).get("total"),
    })
    db.commit()
    return {"ok": True, **resultado, "borrador": _borrador_dict(b)}


@router.post("/{borrador_id}/descartar")
def descartar(
    borrador_id: int,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("upload_files")),
):
    b = _borrador_con_acceso(db, current_user, borrador_id, org_id)
    if b.estado == "confirmado":
        raise HTTPException(409, "Ya está confirmado: si hay que sacarlo, borralo desde IVA")
    b.estado = "descartado"
    db.commit()
    registrar_log(db, current_user.id, "borradores_comprobante", b.id, "DESCARTAR", {})
    db.commit()
    return _borrador_dict(b)


# ── Webhook de Resend Inbound ──────────────────────────────────────

@router.post("/webhook/resend")
async def webhook_resend(
    request: Request,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Recibe `email.received`. Responde 200 rápido y procesa en segundo plano.

    Seguridad: firma Svix obligatoria (RESEND_INBOUND_SECRET). Un destinatario
    que no corresponde a ningún buzón activo se ignora con 200 (no se revela si
    existe o no)."""
    settings = get_settings()
    if not settings.resend_inbound_secret:
        raise HTTPException(503, "Recepción de comprobantes por mail no configurada")
    body = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}
    if not svc.verificar_firma_svix(settings.resend_inbound_secret, headers, body):
        raise HTTPException(401, "Firma inválida")

    try:
        evento = json.loads(body)
    except ValueError:
        raise HTTPException(400, "JSON inválido")
    if evento.get("type") != "email.received":
        return {"ok": True, "ignorado": "tipo"}

    data = evento.get("data") or {}
    email_id = str(data.get("email_id") or "")[:64]
    if not email_id:
        return {"ok": True, "ignorado": "sin_email_id"}
    destinatarios = [*(data.get("to") or []), *(data.get("cc") or []), *(data.get("received_for") or [])]
    oid = svc.buscar_org_por_destinatarios(db, destinatarios, settings.inbound_email_domain.strip())
    if oid is None:
        return {"ok": True, "ignorado": "destinatario"}

    # Idempotencia: Resend reintenta si no respondemos a tiempo.
    if db.query(BorradorComprobante.id).filter(
        BorradorComprobante.organizacion_id == oid,
        BorradorComprobante.email_id == email_id,
    ).first():
        return {"ok": True, "duplicado": True}

    remitente = str(data.get("from") or "")[:255] or None
    asunto = str(data.get("subject") or "")[:500] or None
    adjuntos = svc.adjuntos_utiles(data.get("attachments") or [])

    if not adjuntos:
        # Sin PDF/foto: queda visible igual (p. ej. el código de confirmación del reenvío de Gmail).
        db.add(BorradorComprobante(
            organizacion_id=oid, origen="email", estado="sin_adjunto",
            email_id=email_id, remitente=remitente, asunto=asunto,
        ))
        db.commit()
        return {"ok": True, "borradores": 0}

    ids = []
    for a in adjuntos:
        b = BorradorComprobante(
            organizacion_id=oid, origen="email", estado="procesando",
            email_id=email_id, adjunto_id=str(a.get("id") or "")[:64] or None,
            remitente=remitente, asunto=asunto,
            archivo_nombre=str(a.get("filename") or "adjunto")[:255], archivo_mime=a["mime"],
        )
        db.add(b)
        db.flush()
        ids.append(b.id)
    db.commit()
    background.add_task(_procesar_en_fondo, ids)
    return {"ok": True, "borradores": len(ids)}
