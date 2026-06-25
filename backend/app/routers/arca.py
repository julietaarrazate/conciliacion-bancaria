"""Router del módulo ARCA (ex-AFIP) — facturación electrónica, integración propia WSFEv1/WSAA.

Endpoints (prefix /arca):
  GET  /arca/config                  — config opt-in de la org (sin certificado/clave en la respuesta)
  PUT  /arca/config                  — upsert config (cuit, ambiente, punto_venta, activo)
  POST /arca/certificado             — sube/reemplaza certificado+clave (PEM) — se cifran al guardar
  DELETE /arca/certificado           — borra el certificado+clave cargados (no el resto de la config)
  GET  /arca/comprobantes            — lista comprobantes de la org, paginado
  POST /arca/comprobantes            — crea un comprobante en borrador
  POST /arca/comprobantes/{id}/emitir — pide el CAE a ARCA (WSAA login + WSFEv1 FECAESolicitar)
  GET  /arca/comprobantes/{id}       — detalle

Permisos en 3 capas (mismo patrón que IVA/IIBB/Sueldos):
  config (GET/PUT), certificado (POST/DELETE) → admin_accounting
  comprobantes (GET listar/detalle)            → view_accounting
  comprobantes (POST crear/emitir)             → manage_finance

Nunca se devuelve `certificado_enc`/`clave_privada_enc`/tokens cifrados en ninguna respuesta JSON.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import require_permission, can_switch_org
from app.models.arca import ArcaConfig, ComprobanteArca
from app.models.cliente import Cliente
from app.models.user import User
from app.services import motor_contable
from app.services.arca_crypto import encriptar, ArcaCryptoError
from app.services.arca_wsaa import obtener_token_sign, ArcaWsaaError
from app.services.arca_wsfe import (
    consultar_ultimo_autorizado,
    solicitar_cae,
    DatosComprobante,
    ItemIva,
    ArcaWsfeError,
    ArcaWsfeRechazo,
)
from app.services.auditoria import registrar_log
from app.services.tz import hoy_art

router = APIRouter(prefix="/arca", tags=["arca"])


# ── Helpers ───────────────────────────────────────────────────────

def _org_id(current_user: User, org_id: Optional[int]) -> int:
    if can_switch_org(current_user, org_id) and org_id:
        return org_id
    return current_user.organizacion_id or 1


def _config_dict(c: Optional[ArcaConfig]) -> dict:
    if c is None:
        return {
            "activo": False, "cuit": None, "ambiente": "homologacion",
            "punto_venta": 1, "tiene_certificado": False,
        }
    return {
        "activo": c.activo,
        "cuit": c.cuit,
        "ambiente": c.ambiente,
        "punto_venta": c.punto_venta,
        "tiene_certificado": bool(c.certificado_enc and c.clave_privada_enc),
        "certificado_subido_en": c.certificado_subido_en,
    }


def _comprobante_dict(c: ComprobanteArca) -> dict:
    return {
        "id": c.id,
        "cliente_id": c.cliente_id,
        "cliente_nombre": c.cliente.nombre if c.cliente else None,
        "tipo_comprobante": c.tipo_comprobante,
        "punto_venta": c.punto_venta,
        "numero": c.numero,
        "concepto": c.concepto,
        "doc_tipo": c.doc_tipo,
        "doc_nro": c.doc_nro,
        "fecha_emision": c.fecha_emision,
        "importe_neto": c.importe_neto,
        "importe_iva": c.importe_iva,
        "importe_total": c.importe_total,
        "cae": c.cae,
        "cae_vencimiento": c.cae_vencimiento,
        "estado": c.estado,
        "error_detalle": c.error_detalle,
        "created_at": c.created_at,
    }


# ── Schemas ───────────────────────────────────────────────────────

class ConfigIn(BaseModel):
    activo: bool = False
    cuit: Optional[str] = None
    ambiente: str = "homologacion"
    punto_venta: int = 1


class CertificadoIn(BaseModel):
    certificado_pem: str
    clave_privada_pem: str


class ComprobanteIn(BaseModel):
    cliente_id: Optional[int] = None
    tipo_comprobante: int
    concepto: int = 1
    doc_tipo: int = 99
    doc_nro: Optional[str] = None
    importe_neto: float = 0.0
    importe_iva: float = 0.0
    importe_total: float
    alic_iva: Optional[int] = None  # código AFIP de alícuota (3,4,5,6) si hay IVA


# ── Config ────────────────────────────────────────────────────────

@router.get("/config")
def get_config(
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin_accounting")),
):
    oid = _org_id(current_user, org_id)
    cfg = db.query(ArcaConfig).filter(ArcaConfig.organizacion_id == oid).first()
    return _config_dict(cfg)


@router.put("/config")
def put_config(
    body: ConfigIn,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin_accounting")),
):
    oid = _org_id(current_user, org_id)
    if body.ambiente not in ("homologacion", "produccion"):
        raise HTTPException(422, "ambiente debe ser 'homologacion' o 'produccion'")
    if body.punto_venta < 1:
        raise HTTPException(422, "punto_venta debe ser >= 1")
    if body.cuit and (not body.cuit.isdigit() or len(body.cuit) != 11):
        raise HTTPException(422, "cuit debe tener 11 dígitos sin guiones")

    cfg = db.query(ArcaConfig).filter(ArcaConfig.organizacion_id == oid).first()
    if cfg is None:
        cfg = ArcaConfig(organizacion_id=oid)
        db.add(cfg)

    if body.activo and not (cfg.certificado_enc and cfg.clave_privada_enc):
        raise HTTPException(422, "No se puede activar ARCA sin haber cargado un certificado primero")

    cfg.activo = body.activo
    cfg.cuit = body.cuit
    cfg.ambiente = body.ambiente
    cfg.punto_venta = body.punto_venta

    registrar_log(db, current_user.id, "arca_config", oid, "UPDATE", {
        "activo": body.activo, "ambiente": body.ambiente, "punto_venta": body.punto_venta,
    })
    db.commit()
    db.refresh(cfg)
    return _config_dict(cfg)


@router.post("/certificado")
def subir_certificado(
    body: CertificadoIn,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin_accounting")),
):
    """Sube/reemplaza el certificado+clave privada de la org. Se cifran antes de guardar."""
    oid = _org_id(current_user, org_id)
    if not body.certificado_pem.strip() or not body.clave_privada_pem.strip():
        raise HTTPException(422, "certificado_pem y clave_privada_pem son obligatorios")

    cfg = db.query(ArcaConfig).filter(ArcaConfig.organizacion_id == oid).first()
    if cfg is None:
        cfg = ArcaConfig(organizacion_id=oid)
        db.add(cfg)

    try:
        cfg.certificado_enc = encriptar(body.certificado_pem)
        cfg.clave_privada_enc = encriptar(body.clave_privada_pem)
    except ArcaCryptoError as ex:
        raise HTTPException(503, str(ex))

    cfg.certificado_subido_en = hoy_art()
    # Invalida el token cacheado — el próximo llamado a WSFEv1 re-loguea con el certificado nuevo.
    cfg.ultimo_token_enc = None
    cfg.ultimo_sign_enc = None
    cfg.token_expira = None

    registrar_log(db, current_user.id, "arca_certificado", oid, "UPDATE", {"accion": "subido"})
    db.commit()
    return _config_dict(cfg)


@router.delete("/certificado")
def borrar_certificado(
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin_accounting")),
):
    oid = _org_id(current_user, org_id)
    cfg = db.query(ArcaConfig).filter(ArcaConfig.organizacion_id == oid).first()
    if cfg is None:
        raise HTTPException(404, "La organización no tiene configuración ARCA")

    cfg.certificado_enc = None
    cfg.clave_privada_enc = None
    cfg.ultimo_token_enc = None
    cfg.ultimo_sign_enc = None
    cfg.token_expira = None
    cfg.activo = False

    registrar_log(db, current_user.id, "arca_certificado", oid, "DELETE", {})
    db.commit()
    return _config_dict(cfg)


# ── Comprobantes ──────────────────────────────────────────────────

@router.get("/comprobantes")
def listar_comprobantes(
    org_id: Optional[int] = Query(None),
    estado: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("view_accounting")),
):
    oid = _org_id(current_user, org_id)
    q = db.query(ComprobanteArca).filter(ComprobanteArca.organizacion_id == oid)
    if estado:
        q = q.filter(ComprobanteArca.estado == estado)
    total = q.count()
    items = q.order_by(ComprobanteArca.id.desc()).offset(offset).limit(limit).all()
    return {"items": [_comprobante_dict(c) for c in items], "total": total}


@router.get("/comprobantes/{comprobante_id}")
def get_comprobante(
    comprobante_id: int,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("view_accounting")),
):
    oid = _org_id(current_user, org_id)
    c = (
        db.query(ComprobanteArca)
        .filter(ComprobanteArca.id == comprobante_id, ComprobanteArca.organizacion_id == oid)
        .first()
    )
    if c is None:
        raise HTTPException(404, "Comprobante no encontrado")
    return _comprobante_dict(c)


@router.post("/comprobantes")
def crear_comprobante(
    body: ComprobanteIn,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage_finance")),
):
    """Crea un comprobante en borrador (sin CAE) — emitirlo es un paso aparte."""
    oid = _org_id(current_user, org_id)
    cfg = db.query(ArcaConfig).filter(ArcaConfig.organizacion_id == oid).first()
    if cfg is None or not cfg.activo:
        raise HTTPException(422, "El módulo ARCA no está activo para esta organización")

    if body.cliente_id is not None:
        cliente = (
            db.query(Cliente)
            .filter(Cliente.id == body.cliente_id, Cliente.organizacion_id == oid)
            .first()
        )
        if cliente is None:
            raise HTTPException(404, "Cliente no encontrado")

    if body.importe_total <= 0:
        raise HTTPException(422, "importe_total debe ser mayor a 0")

    c = ComprobanteArca(
        organizacion_id=oid,
        cliente_id=body.cliente_id,
        tipo_comprobante=body.tipo_comprobante,
        punto_venta=cfg.punto_venta,
        concepto=body.concepto,
        doc_tipo=body.doc_tipo,
        doc_nro=body.doc_nro,
        fecha_emision=hoy_art(),
        importe_neto=Decimal(str(body.importe_neto)),
        importe_iva=Decimal(str(body.importe_iva)),
        importe_total=Decimal(str(body.importe_total)),
        estado="borrador",
    )
    db.add(c)
    registrar_log(db, current_user.id, "arca_comprobante", oid, "CREATE", {
        "tipo_comprobante": body.tipo_comprobante, "importe_total": body.importe_total,
    })
    db.commit()
    db.refresh(c)
    return _comprobante_dict(c)


@router.post("/comprobantes/{comprobante_id}/emitir")
def emitir_comprobante(
    comprobante_id: int,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage_finance")),
):
    """Pide el CAE a ARCA: login WSAA (cacheado ~12h) + FECompUltimoAutorizado + FECAESolicitar."""
    oid = _org_id(current_user, org_id)
    c = (
        db.query(ComprobanteArca)
        .filter(ComprobanteArca.id == comprobante_id, ComprobanteArca.organizacion_id == oid)
        .first()
    )
    if c is None:
        raise HTTPException(404, "Comprobante no encontrado")
    if c.estado == "emitido":
        raise HTTPException(409, "El comprobante ya fue emitido (tiene CAE) — es inmutable")

    cfg = db.query(ArcaConfig).filter(ArcaConfig.organizacion_id == oid).first()
    if cfg is None or not cfg.activo:
        raise HTTPException(422, "El módulo ARCA no está activo para esta organización")
    if not cfg.cuit:
        raise HTTPException(422, "Falta configurar el CUIT de la organización")

    try:
        token, sign = obtener_token_sign(db, cfg)
        ultimo = consultar_ultimo_autorizado(
            token, sign, cfg.cuit, cfg.ambiente, cfg.punto_venta, c.tipo_comprobante,
        )
        numero = ultimo + 1

        ivas = []
        if c.importe_iva and c.importe_iva > 0:
            ivas.append(ItemIva(alic_id=5, base_imp=c.importe_neto, importe=c.importe_iva))

        datos = DatosComprobante(
            cuit=cfg.cuit,
            punto_venta=cfg.punto_venta,
            tipo_comprobante=c.tipo_comprobante,
            numero=numero,
            concepto=c.concepto,
            doc_tipo=c.doc_tipo,
            doc_nro=c.doc_nro or "0",
            fecha_emision=c.fecha_emision.strftime("%Y%m%d"),
            importe_neto=c.importe_neto,
            importe_iva=c.importe_iva,
            importe_total=c.importe_total,
            ivas=ivas,
        )
        resultado = solicitar_cae(token, sign, cfg.ambiente, datos)
    except ArcaWsaaError as ex:
        c.estado = "error"
        c.error_detalle = f"WSAA: {ex}"
        db.commit()
        raise HTTPException(502, f"No se pudo autenticar contra ARCA: {ex}")
    except ArcaWsfeRechazo as ex:
        c.estado = "rechazado"
        c.error_detalle = "; ".join(ex.errores)
        db.commit()
        raise HTTPException(422, f"ARCA rechazó el comprobante: {'; '.join(ex.errores)}")
    except ArcaWsfeError as ex:
        c.estado = "error"
        c.error_detalle = str(ex)
        db.commit()
        raise HTTPException(502, f"Error técnico llamando a WSFEv1: {ex}")

    from datetime import datetime as _dt
    c.numero = numero
    c.cae = resultado["cae"]
    vto = resultado.get("cae_vencimiento")
    if vto:
        try:
            c.cae_vencimiento = _dt.strptime(vto, "%Y%m%d").date()
        except Exception:
            c.cae_vencimiento = None
    c.estado = "emitido"
    c.error_detalle = None
    db.commit()
    db.refresh(c)

    cliente_nombre = c.cliente.nombre if c.cliente else ""
    asiento_id = motor_contable.registrar_factura_arca(
        db, c.id, oid, current_user.id, c.cliente_id, cliente_nombre,
        c.importe_neto, c.importe_iva, c.importe_total, c.fecha_emision,
    )
    if asiento_id:
        c.asiento_id = asiento_id
        db.commit()

    registrar_log(db, current_user.id, "arca_comprobante", oid, "EMITIR", {
        "comprobante_id": c.id, "cae": c.cae, "numero": c.numero,
    })
    db.refresh(c)
    return _comprobante_dict(c)
