"""WSAA — Web Service de Autenticación y Autorización de ARCA.

Cada organización tiene su propio certificado X.509 + clave privada (emitidos
por ARCA para su CUIT). Para llamar a WSFEv1 primero hay que loguearse contra
WSAA: se construye un "Ticket de Requerimiento de Acceso" (TRA, XML simple),
se firma como CMS/PKCS#7 (detached, DER) con el certificado+clave del org, y se
envía en una llamada SOAP `loginCms`. ARCA devuelve un token+sign válidos por
~12hs que se usan en cada llamada a WSFEv1.

El token/sign se cachean cifrados en `ArcaConfig` (mismo patrón que el propio
certificado — ver `arca_crypto.py`) para no loguear en cada factura.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from xml.etree import ElementTree as ET

import requests
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.serialization import pkcs7
from sqlalchemy.orm import Session

from app.models.arca import ArcaConfig
from app.services.arca_crypto import desencriptar, encriptar
from app.services.tz import now_art

logger = logging.getLogger(__name__)

_WSAA_URL = {
    "homologacion": "https://wsaahomo.afip.gov.ar/ws/services/LoginCms",
    "produccion": "https://wsaa.afip.gov.ar/ws/services/LoginCms",
}

_SERVICE = "wsfe"
_MARGEN_RENOVACION = timedelta(minutes=10)  # renovar el token un poco antes de que venza


class ArcaWsaaError(Exception):
    """Error de negocio del login WSAA (certificado inválido, ARCA rechazó el TRA, etc.)."""


def _build_tra() -> bytes:
    """Construye el XML del Ticket de Requerimiento de Acceso (TRA)."""
    ahora = now_art()
    generation = ahora - timedelta(minutes=5)   # margen por desfasaje de reloj
    expiration = ahora + timedelta(minutes=10)
    unique_id = str(int(ahora.timestamp()))
    tra = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<loginTicketRequest version=\"1.0\">"
        "<header>"
        f"<uniqueId>{unique_id}</uniqueId>"
        f"<generationTime>{generation.isoformat()}</generationTime>"
        f"<expirationTime>{expiration.isoformat()}</expirationTime>"
        "</header>"
        f"<service>{_SERVICE}</service>"
        "</loginTicketRequest>"
    )
    return tra.encode("utf-8")


def _firmar_cms(tra_xml: bytes, certificado_pem: str, clave_privada_pem: str) -> bytes:
    """Firma el TRA como CMS/PKCS#7 (DER, con certificado embebido) — lo que ARCA exige en loginCms."""
    try:
        cert = x509.load_pem_x509_certificate(certificado_pem.encode())
        clave = serialization.load_pem_private_key(clave_privada_pem.encode(), password=None)
    except Exception as ex:
        raise ArcaWsaaError(f"Certificado o clave privada inválidos: {ex}")

    try:
        firmado = (
            pkcs7.PKCS7SignatureBuilder()
            .set_data(tra_xml)
            .add_signer(cert, clave, hashes.SHA256())
            .sign(serialization.Encoding.DER, [pkcs7.PKCS7Options.Binary])
        )
    except Exception as ex:
        raise ArcaWsaaError(f"No se pudo firmar el TRA (CMS): {ex}")
    return firmado


def _llamar_login_cms(cms_der: bytes, ambiente: str) -> str:
    """POST SOAP a WSAA con el CMS en base64. Devuelve el XML de loginTicketResponse (string)."""
    import base64

    cms_b64 = base64.b64encode(cms_der).decode()
    envelope = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" '
        'xmlns:wsaa="http://wsaa.view.sua.dvadac.desein.afip.gov">'
        "<soapenv:Header/><soapenv:Body><wsaa:loginCms>"
        f"<wsaa:in0>{cms_b64}</wsaa:in0>"
        "</wsaa:loginCms></soapenv:Body></soapenv:Envelope>"
    )
    url = _WSAA_URL.get(ambiente, _WSAA_URL["homologacion"])
    headers = {"Content-Type": "text/xml; charset=utf-8", "SOAPAction": ""}
    try:
        resp = requests.post(url, data=envelope.encode("utf-8"), headers=headers, timeout=30)
    except requests.RequestException as ex:
        raise ArcaWsaaError(f"No se pudo conectar a WSAA ({ambiente}): {ex}")

    if resp.status_code != 200:
        raise ArcaWsaaError(f"WSAA respondió HTTP {resp.status_code}: {resp.text[:500]}")

    if "<faultstring>" in resp.text:
        try:
            fault = ET.fromstring(resp.text).find(".//faultstring").text
        except Exception:
            fault = resp.text[:500]
        raise ArcaWsaaError(f"WSAA rechazó el login: {fault}")

    return resp.text


def _parsear_login_ticket_response(soap_xml: str) -> tuple[str, str, str]:
    """Extrae (token, sign, expirationTime) del XML anidado dentro del Envelope SOAP."""
    try:
        root = ET.fromstring(soap_xml)
        # loginCmsReturn trae el loginTicketResponse XML escapado como texto
        ns_body = next(c for c in root if c.tag.endswith("Body"))
        inner_xml = None
        for el in ns_body.iter():
            if el.tag.endswith("loginCmsReturn") and el.text:
                inner_xml = el.text
                break
        if not inner_xml:
            raise ValueError("No se encontró loginCmsReturn en la respuesta")
        ticket = ET.fromstring(inner_xml)
        token = ticket.find(".//token").text
        sign = ticket.find(".//sign").text
        expira = ticket.find(".//header/expirationTime").text
        return token, sign, expira
    except Exception as ex:
        raise ArcaWsaaError(f"No se pudo parsear la respuesta de WSAA: {ex}")


def obtener_token_sign(db: Session, config: ArcaConfig) -> tuple[str, str]:
    """Devuelve (token, sign) vigentes para esta org — usa el cache si no venció, sino re-loguea."""
    if not config.certificado_enc or not config.clave_privada_enc:
        raise ArcaWsaaError("La organización no tiene certificado ARCA cargado.")

    ahora = now_art()
    if (
        config.ultimo_token_enc
        and config.ultimo_sign_enc
        and config.token_expira
        and config.token_expira.replace(tzinfo=ahora.tzinfo) - ahora > _MARGEN_RENOVACION
    ):
        return desencriptar(config.ultimo_token_enc), desencriptar(config.ultimo_sign_enc)

    certificado = desencriptar(config.certificado_enc)
    clave = desencriptar(config.clave_privada_enc)

    tra = _build_tra()
    cms = _firmar_cms(tra, certificado, clave)
    respuesta = _llamar_login_cms(cms, config.ambiente)
    token, sign, expira_str = _parsear_login_ticket_response(respuesta)

    try:
        from datetime import datetime
        expira_dt = datetime.fromisoformat(expira_str)
    except Exception:
        expira_dt = ahora + timedelta(hours=11)

    config.ultimo_token_enc = encriptar(token)
    config.ultimo_sign_enc = encriptar(sign)
    config.token_expira = expira_dt.replace(tzinfo=None)
    db.add(config)
    db.commit()

    return token, sign
