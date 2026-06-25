"""Modelos del módulo ARCA (ex-AFIP) — facturación electrónica, integración propia WSFEv1/WSAA.

Cuadra implementa su propio cliente de los web services de ARCA (no un wrapper
pagado de terceros): WSAA para autenticarse (token+sign con ~12h de validez,
firmado con el certificado X.509 + clave privada de cada organización) y WSFEv1
para solicitar el CAE (Código de Autorización Electrónico) de cada comprobante.

Opt-in por organización (mismo patrón que IVA/Monotributo/IIBB/Sueldos):
`ArcaConfig.activo=False` hasta que el admin carga su certificado y lo activa.

Seguridad: `certificado_pem`/`clave_privada_pem` se guardan SIEMPRE cifrados
(ver `app/services/arca_crypto.py`, Fernet con ARCA_ENCRYPTION_KEY de Render) —
nunca en claro en la DB, nunca en logs, nunca en el repo. Es el material más
sensible que maneja el sistema: con la clave privada de un CUIT se puede facturar
en su nombre ante ARCA.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Boolean, Date, DateTime, ForeignKey, Text,
    Numeric, UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class ArcaConfig(Base):
    """Configuración ARCA de una organización — 1 por org. Opt-in."""

    __tablename__ = "arca_config"

    id                    = Column(Integer, primary_key=True, index=True)
    organizacion_id       = Column(Integer, ForeignKey("organizaciones.id"), nullable=False, unique=True, index=True)

    cuit                  = Column(String(11), nullable=True)   # CUIT bajo el que se factura (sin guiones)
    ambiente              = Column(String(20), nullable=False, default="homologacion")  # homologacion | produccion
    punto_venta           = Column(Integer, nullable=False, default=1)
    activo                = Column(Boolean, nullable=False, default=False)

    # Certificado + clave privada del CUIT, SIEMPRE cifrados (ver arca_crypto.py)
    certificado_enc       = Column(Text, nullable=True)
    clave_privada_enc     = Column(Text, nullable=True)
    certificado_subido_en = Column(DateTime, nullable=True)

    # Cache del token/sign de WSAA (válido ~12h) — evita re-loguear en cada factura.
    # Cifrados igual que el certificado: el token de WSAA habilita a facturar.
    ultimo_token_enc      = Column(Text, nullable=True)
    ultimo_sign_enc       = Column(Text, nullable=True)
    token_expira          = Column(DateTime, nullable=True)

    created_at            = Column(DateTime, default=datetime.utcnow)
    updated_at            = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organizacion = relationship("Organizacion", foreign_keys=[organizacion_id])


class ComprobanteArca(Base):
    """Un comprobante (factura) emitido — o intentado — ante ARCA vía WSFEv1.

    `estado`: borrador → emitido (CAE obtenido) | rechazado (ARCA devolvió error) | error (falla técnica).
    Una vez `emitido` (tiene CAE), el comprobante es INMUTABLE — mismo patrón que
    ProyeccionIva/IIBB al marcar presentada: es un documento fiscal real, no se edita.
    """

    __tablename__ = "comprobantes_arca"

    id                  = Column(Integer, primary_key=True, index=True)
    organizacion_id     = Column(Integer, ForeignKey("organizaciones.id"), nullable=False, index=True)
    cliente_id          = Column(Integer, ForeignKey("clientes.id"), nullable=True, index=True)

    tipo_comprobante    = Column(Integer, nullable=False)         # códigos AFIP: 1=Factura A, 6=B, 11=C...
    punto_venta         = Column(Integer, nullable=False)
    numero              = Column(Integer, nullable=True)          # asignado por ARCA al emitir
    concepto            = Column(Integer, nullable=False, default=1)  # 1=productos, 2=servicios, 3=ambos
    doc_tipo            = Column(Integer, nullable=False, default=99)  # 80=CUIT, 96=DNI, 99=consumidor final
    doc_nro             = Column(String(11), nullable=True)

    fecha_emision       = Column(Date, nullable=False)
    # Obligatorios ante ARCA cuando concepto es 2 (servicios) o 3 (ambos) — ver WSFEv1 FECAEDetRequest
    fecha_serv_desde    = Column(Date, nullable=True)
    fecha_serv_hasta    = Column(Date, nullable=True)
    fecha_vto_pago      = Column(Date, nullable=True)
    importe_neto        = Column(Numeric(12, 2), nullable=False, default=0)
    importe_iva         = Column(Numeric(12, 2), nullable=False, default=0)
    importe_total       = Column(Numeric(12, 2), nullable=False, default=0)

    cae                 = Column(String(20), nullable=True)
    cae_vencimiento     = Column(Date, nullable=True)
    estado              = Column(String(20), nullable=False, default="borrador")
    error_detalle       = Column(Text, nullable=True)

    referencia_planilla_id = Column(Integer, ForeignKey("planillas.id"), nullable=True)
    asiento_id          = Column(Integer, ForeignKey("asientos.id"), nullable=True)
    usuario_id          = Column(Integer, ForeignKey("users.id"), nullable=True)

    created_at          = Column(DateTime, default=datetime.utcnow)
    updated_at           = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organizacion = relationship("Organizacion", foreign_keys=[organizacion_id])
    cliente      = relationship("Cliente", foreign_keys=[cliente_id])

    __table_args__ = (
        UniqueConstraint(
            "organizacion_id", "punto_venta", "tipo_comprobante", "numero",
            name="uq_comprobante_arca_org_pv_tipo_numero",
        ),
    )
