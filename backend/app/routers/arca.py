"""Router del módulo ARCA (ex-AFIP) — facturación electrónica, integración propia WSFEv1/WSAA.

Endpoints (prefix /arca):
  GET  /arca/config                  — config opt-in de la org (sin certificado/clave en la respuesta)
  PUT  /arca/config                  — upsert config (cuit, ambiente, punto_venta, activo)
  POST /arca/certificado             — sube/reemplaza certificado+clave (PEM) — se cifran al guardar
  DELETE /arca/certificado           — borra el certificado+clave cargados (no el resto de la config)
  GET  /arca/comprobantes            — lista comprobantes de la org, paginado
  POST /arca/comprobantes            — crea un comprobante en borrador
  POST /arca/comprobantes/{id}/emitir — pide el CAE a ARCA (WSAA login + WSFEv1 FECAESolicitar);
                                        reintentable sin duplicar (ver "Emisión segura")
  GET  /arca/comprobantes/{id}       — detalle

Permisos en 3 capas (mismo patrón que IVA/IIBB/Sueldos):
  config (GET/PUT), certificado (POST/DELETE) → admin_accounting
  comprobantes (GET listar/detalle)            → view_accounting
  comprobantes (POST crear/emitir)             → manage_finance

Nunca se devuelve `certificado_enc`/`clave_privada_enc`/tokens cifrados en ninguna respuesta JSON.
"""

from __future__ import annotations

import hashlib
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
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
    consultar_comprobante,
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
        "fecha_serv_desde": c.fecha_serv_desde,
        "fecha_serv_hasta": c.fecha_serv_hasta,
        "fecha_vto_pago": c.fecha_vto_pago,
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
    # Obligatorios ante ARCA si concepto es 2 (servicios) o 3 (ambos)
    fecha_serv_desde: Optional[date] = None
    fecha_serv_hasta: Optional[date] = None
    fecha_vto_pago: Optional[date] = None


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

    if body.concepto in (2, 3) and not (body.fecha_serv_desde and body.fecha_serv_hasta and body.fecha_vto_pago):
        raise HTTPException(
            422,
            "Concepto servicios/ambos requiere fecha_serv_desde, fecha_serv_hasta y fecha_vto_pago",
        )

    c = ComprobanteArca(
        organizacion_id=oid,
        cliente_id=body.cliente_id,
        tipo_comprobante=body.tipo_comprobante,
        punto_venta=cfg.punto_venta,
        concepto=body.concepto,
        doc_tipo=body.doc_tipo,
        doc_nro=body.doc_nro,
        fecha_emision=hoy_art(),
        fecha_serv_desde=body.fecha_serv_desde,
        fecha_serv_hasta=body.fecha_serv_hasta,
        fecha_vto_pago=body.fecha_vto_pago,
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


# ── Emisión segura (sin duplicar comprobantes) ───────────────────
#
# ARCA no acepta una clave de idempotencia: si la respuesta de FECAESolicitar se
# pierde (timeout, corte de red, reinicio de Render), ARCA pudo haber autorizado
# el comprobante igual. Reintentar pidiendo "último + 1" emitiría una SEGUNDA
# factura real. Para evitarlo:
#   1. El número se reserva en la fila (estado "emitiendo") ANTES de llamar a
#      FECAESolicitar, con commit — sobrevive a un reinicio del proceso.
#   2. Si la llamada falla técnicamente, el número queda reservado (estado
#      "error"). Al reintentar, primero se consulta ese número en ARCA
#      (FECompConsultar): si ya existe y coincide, se recupera el CAE sin emitir
#      de nuevo; si existe pero es otro comprobante, se frena (conflicto); si no
#      existe, se libera y se emite normalmente.
#   3. Las emisiones del mismo punto de venta + tipo se serializan con un
#      advisory lock de Postgres, para que dos pedidos simultáneos no tomen el
#      mismo número.


def _clave_lock(oid: int, punto_venta: int, tipo_comprobante: int) -> int:
    """Clave bigint estable (entre procesos) para el advisory lock de emisión."""
    digest = hashlib.sha1(f"arca:{oid}:{punto_venta}:{tipo_comprobante}".encode()).digest()
    return int.from_bytes(digest[:8], "big", signed=True)


@contextmanager
def _lock_emision(db: Session, oid: int, punto_venta: int, tipo_comprobante: int):
    """Serializa emisiones por (org, punto de venta, tipo).

    En Postgres usa un advisory lock de sesión sobre una conexión aparte (la
    sesión del request hace commits intermedios y puede soltar su conexión).
    En otros motores (SQLite de tests) es un no-op.
    """
    bind = db.get_bind()
    engine = getattr(bind, "engine", bind)
    if engine.dialect.name != "postgresql":
        yield
        return
    clave = _clave_lock(oid, punto_venta, tipo_comprobante)
    with engine.connect() as conn:
        conn.execute(text("SELECT pg_advisory_lock(:k)"), {"k": clave})
        conn.commit()
        try:
            yield
        finally:
            conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": clave})
            conn.commit()


def _coincide_con_arca(c: ComprobanteArca, remoto: dict) -> bool:
    """¿El comprobante que ARCA tiene en ese número es este mismo?"""
    if remoto.get("resultado") not in (None, "A") or not remoto.get("cae"):
        return False
    total_remoto = remoto.get("importe_total")
    if total_remoto is None or Decimal(str(total_remoto)).quantize(Decimal("0.01")) != Decimal(str(c.importe_total)).quantize(Decimal("0.01")):
        return False
    try:
        return int(remoto.get("doc_nro") or 0) == int(c.doc_nro or 0)
    except ValueError:
        return False


def _parse_fecha_arca(valor: Optional[str]) -> Optional[date]:
    if not valor:
        return None
    try:
        return datetime.strptime(valor, "%Y%m%d").date()
    except ValueError:
        return None


def _registrar_emitido(
    db: Session, c: ComprobanteArca, oid: int, current_user: User,
    cae: str, cae_vencimiento: Optional[str], recuperado: bool,
) -> dict:
    """Marca el comprobante como emitido, genera el asiento y audita."""
    c.cae = cae
    c.cae_vencimiento = _parse_fecha_arca(cae_vencimiento)
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
        "comprobante_id": c.id, "cae": c.cae, "numero": c.numero, "recuperado": recuperado,
    })
    db.refresh(c)
    return _comprobante_dict(c)


@router.post("/comprobantes/{comprobante_id}/emitir")
def emitir_comprobante(
    comprobante_id: int,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage_finance")),
):
    """Pide el CAE a ARCA sin riesgo de duplicar (ver "Emisión segura" arriba)."""
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

    # Si ya hay un número reservado, se verifica sobre ESE punto de venta.
    punto_venta = c.punto_venta if c.numero is not None else cfg.punto_venta

    with _lock_emision(db, oid, punto_venta, c.tipo_comprobante):
        # Otro pedido pudo haberlo emitido mientras esperábamos el lock.
        db.refresh(c)
        if c.estado == "emitido":
            raise HTTPException(409, "El comprobante ya fue emitido (tiene CAE) — es inmutable")

        try:
            token, sign = obtener_token_sign(db, cfg)
        except ArcaWsaaError as ex:
            c.estado = "error"
            c.error_detalle = f"WSAA: {ex}"
            db.commit()
            raise HTTPException(502, f"No se pudo autenticar contra ARCA: {ex}")

        # 1. Número reservado de un intento anterior: verificar antes de emitir otro.
        if c.numero is not None:
            try:
                remoto = consultar_comprobante(
                    token, sign, cfg.cuit, cfg.ambiente, c.punto_venta, c.tipo_comprobante, c.numero,
                )
            except ArcaWsfeError as ex:
                c.estado = "error"
                c.error_detalle = (
                    f"No se pudo verificar en ARCA el número {c.numero} reservado: {ex}. "
                    "Reintentá más tarde — no se emite otro número hasta verificarlo."
                )
                db.commit()
                raise HTTPException(502, c.error_detalle)
            if remoto is not None:
                if _coincide_con_arca(c, remoto):
                    return _registrar_emitido(
                        db, c, oid, current_user, remoto["cae"], remoto.get("cae_vencimiento"),
                        recuperado=True,
                    )
                c.estado = "error"
                c.error_detalle = (
                    f"Conflicto: ARCA tiene otro comprobante autorizado con el número {c.numero} "
                    f"(total {remoto.get('importe_total')}). No se emitió nada. Revisalo antes de seguir."
                )
                db.commit()
                raise HTTPException(409, c.error_detalle)
            # ARCA no lo tiene: el número no se consumió, se libera.
            c.numero = None
            db.commit()

        # 2. Reservar el número siguiente.
        try:
            ultimo = consultar_ultimo_autorizado(
                token, sign, cfg.cuit, cfg.ambiente, cfg.punto_venta, c.tipo_comprobante,
            )
        except ArcaWsfeError as ex:
            c.estado = "error"
            c.error_detalle = str(ex)
            db.commit()
            raise HTTPException(502, f"Error técnico llamando a WSFEv1: {ex}")
        numero = ultimo + 1

        otro = (
            db.query(ComprobanteArca)
            .filter(
                ComprobanteArca.organizacion_id == oid,
                ComprobanteArca.punto_venta == cfg.punto_venta,
                ComprobanteArca.tipo_comprobante == c.tipo_comprobante,
                ComprobanteArca.numero == numero,
                ComprobanteArca.id != c.id,
            )
            .first()
        )
        if otro is not None:
            raise HTTPException(
                409,
                f"El comprobante #{otro.id} tiene reservado el número {numero} y está pendiente "
                "de verificar. Reintentá ese primero.",
            )

        c.punto_venta = cfg.punto_venta
        c.numero = numero
        c.estado = "emitiendo"
        c.error_detalle = None
        db.commit()

        # 3. Pedir el CAE.
        ivas = []
        if c.importe_iva and c.importe_iva > 0:
            ivas.append(ItemIva(alic_id=5, base_imp=c.importe_neto, importe=c.importe_iva))

        datos = DatosComprobante(
            cuit=cfg.cuit,
            punto_venta=c.punto_venta,
            tipo_comprobante=c.tipo_comprobante,
            numero=numero,
            concepto=c.concepto,
            doc_tipo=c.doc_tipo,
            doc_nro=c.doc_nro or "0",
            fecha_emision=c.fecha_emision.strftime("%Y%m%d"),
            importe_neto=c.importe_neto,
            importe_iva=c.importe_iva,
            importe_total=c.importe_total,
            fecha_serv_desde=c.fecha_serv_desde.strftime("%Y%m%d") if c.fecha_serv_desde else None,
            fecha_serv_hasta=c.fecha_serv_hasta.strftime("%Y%m%d") if c.fecha_serv_hasta else None,
            fecha_vto_pago=c.fecha_vto_pago.strftime("%Y%m%d") if c.fecha_vto_pago else None,
            ivas=ivas,
        )
        try:
            resultado = solicitar_cae(token, sign, cfg.ambiente, datos)
        except ArcaWsfeRechazo as ex:
            # ARCA respondió y rechazó: el número no se consumió.
            c.numero = None
            c.estado = "rechazado"
            c.error_detalle = "; ".join(ex.errores)
            db.commit()
            raise HTTPException(422, f"ARCA rechazó el comprobante: {'; '.join(ex.errores)}")
        except ArcaWsfeError as ex:
            # Resultado incierto: ARCA pudo haberlo autorizado. El número queda
            # reservado y el próximo intento lo verifica antes de emitir.
            c.estado = "error"
            c.error_detalle = (
                f"Error técnico llamando a WSFEv1: {ex}. El número {numero} queda reservado: "
                "al reintentar, Cuadra verifica en ARCA antes de emitir otro."
            )
            db.commit()
            raise HTTPException(502, f"Error técnico llamando a WSFEv1: {ex}")

        return _registrar_emitido(
            db, c, oid, current_user, resultado["cae"], resultado.get("cae_vencimiento"),
            recuperado=False,
        )
