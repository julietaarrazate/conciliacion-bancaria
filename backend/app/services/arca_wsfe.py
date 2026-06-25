"""WSFEv1 — Web Service de Facturación Electrónica de ARCA (ex-AFIP).

Con el token+sign que entrega WSAA (ver `arca_wsaa.py`) se consulta el último
número de comprobante autorizado para un punto de venta + tipo, y se solicita
el CAE (Código de Autorización Electrónico) del comprobante siguiente.

Solo dos operaciones del WS se usan acá (las únicas que Cuadra necesita hoy):
  - FECompUltimoAutorizado: último número ya autorizado (para saber qué número sigue).
  - FECAESolicitar: pide el CAE de un comprobante nuevo.

Sin librería SOAP pesada (no hay zeep/suds en el proyecto) — se construyen los
envelopes a mano con XML simple, igual estilo liviano que el resto de Cuadra
(excel_parser, motor_contable no usan frameworks externos tampoco).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional
from xml.etree import ElementTree as ET

import requests

logger = logging.getLogger(__name__)

_WSFE_URL = {
    "homologacion": "https://wswhomo.afip.gov.ar/wsfev1/service.asmx",
    "produccion": "https://servicios1.afip.gov.ar/wsfev1/service.asmx",
}

_NS_FEV1 = "http://ar.gov.afip.dif.FEV1/"


class ArcaWsfeError(Exception):
    """Error técnico llamando a WSFEv1 (red, HTTP, parseo)."""


class ArcaWsfeRechazo(Exception):
    """ARCA procesó la solicitud pero la rechazó (Resultado=R) — viene con el detalle de errores."""

    def __init__(self, mensaje: str, errores: list[str]):
        super().__init__(mensaje)
        self.errores = errores


@dataclass
class ItemIva:
    alic_id: int       # código AFIP de alícuota: 3=0%, 4=10.5%, 5=21%, 6=27%
    base_imp: Decimal
    importe: Decimal


@dataclass
class DatosComprobante:
    cuit: str
    punto_venta: int
    tipo_comprobante: int
    numero: int                 # CbteDesde == CbteHasta (un comprobante por solicitud)
    concepto: int                # 1=productos, 2=servicios, 3=ambos
    doc_tipo: int
    doc_nro: str
    fecha_emision: str           # YYYYMMDD
    importe_neto: Decimal
    importe_iva: Decimal
    importe_total: Decimal
    fecha_serv_desde: Optional[str] = None  # YYYYMMDD — obligatorio si concepto es 2 o 3
    fecha_serv_hasta: Optional[str] = None  # YYYYMMDD — obligatorio si concepto es 2 o 3
    fecha_vto_pago: Optional[str] = None    # YYYYMMDD — obligatorio si concepto es 2 o 3
    ivas: list[ItemIva] = field(default_factory=list)


def _local(tag: str) -> str:
    """Nombre del tag sin namespace ('{ns}Foo' -> 'Foo')."""
    return tag.rsplit("}", 1)[-1]


def _find_local(root: ET.Element, name: str) -> Optional[ET.Element]:
    for el in root.iter():
        if _local(el.tag) == name:
            return el
    return None


def _findall_local(root: ET.Element, name: str) -> list[ET.Element]:
    return [el for el in root.iter() if _local(el.tag) == name]


def _soap_call(ambiente: str, soap_action: str, body_xml: str) -> ET.Element:
    url = _WSFE_URL.get(ambiente, _WSFE_URL["homologacion"])
    envelope = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" '
        f'xmlns:ar="{_NS_FEV1}">'
        f"<soap:Body>{body_xml}</soap:Body></soap:Envelope>"
    )
    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": f"{_NS_FEV1}{soap_action}",
    }
    try:
        resp = requests.post(url, data=envelope.encode("utf-8"), headers=headers, timeout=30)
    except requests.RequestException as ex:
        raise ArcaWsfeError(f"No se pudo conectar a WSFEv1 ({ambiente}): {ex}")

    if resp.status_code != 200:
        raise ArcaWsfeError(f"WSFEv1 respondió HTTP {resp.status_code}: {resp.text[:500]}")

    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError as ex:
        raise ArcaWsfeError(f"Respuesta de WSFEv1 no es XML válido: {ex}")

    fault = _find_local(root, "faultstring")
    if fault is not None and fault.text:
        raise ArcaWsfeError(f"WSFEv1 rechazó la llamada: {fault.text}")

    return root


def consultar_ultimo_autorizado(token: str, sign: str, cuit: str, ambiente: str, punto_venta: int, tipo_comprobante: int) -> int:
    """Devuelve el último número de comprobante autorizado para ese punto de venta + tipo (0 si no hay ninguno)."""
    body = (
        "<ar:FECompUltimoAutorizado>"
        "<ar:Auth>"
        f"<ar:Token>{token}</ar:Token><ar:Sign>{sign}</ar:Sign><ar:Cuit>{cuit}</ar:Cuit>"
        "</ar:Auth>"
        f"<ar:PtoVta>{punto_venta}</ar:PtoVta>"
        f"<ar:CbteTipo>{tipo_comprobante}</ar:CbteTipo>"
        "</ar:FECompUltimoAutorizado>"
    )
    root = _soap_call(ambiente, "FECompUltimoAutorizado", body)
    err = _find_local(root, "Err")
    if err is not None:
        codigo = _find_local(err, "Code")
        msg = _find_local(err, "Msg")
        raise ArcaWsfeError(f"WSFEv1 error {codigo.text if codigo is not None else '?'}: {msg.text if msg is not None else ''}")
    nro = _find_local(root, "CbteNro")
    return int(nro.text) if nro is not None and nro.text else 0


def solicitar_cae(token: str, sign: str, ambiente: str, datos: DatosComprobante) -> dict:
    """Solicita el CAE de un comprobante. Devuelve {cae, cae_vencimiento} o lanza ArcaWsfeRechazo/ArcaWsfeError."""
    ivas_xml = ""
    if datos.ivas:
        items = "".join(
            "<ar:AlicIva>"
            f"<ar:Id>{i.alic_id}</ar:Id>"
            f"<ar:BaseImp>{i.base_imp:.2f}</ar:BaseImp>"
            f"<ar:Importe>{i.importe:.2f}</ar:Importe>"
            "</ar:AlicIva>"
            for i in datos.ivas
        )
        ivas_xml = f"<ar:Iva>{items}</ar:Iva>"

    # ARCA exige FchServDesde/FchServHasta/FchVtoPago cuando Concepto es 2 (servicios) o 3 (ambos);
    # deben omitirse para Concepto 1 (productos) — incluirlos ahí también es rechazado por WSFEv1.
    fechas_serv_xml = ""
    if datos.concepto in (2, 3):
        if not (datos.fecha_serv_desde and datos.fecha_serv_hasta and datos.fecha_vto_pago):
            raise ArcaWsfeError(
                "Concepto servicios/ambos requiere fecha_serv_desde, fecha_serv_hasta y fecha_vto_pago"
            )
        fechas_serv_xml = (
            f"<ar:FchServDesde>{datos.fecha_serv_desde}</ar:FchServDesde>"
            f"<ar:FchServHasta>{datos.fecha_serv_hasta}</ar:FchServHasta>"
            f"<ar:FchVtoPago>{datos.fecha_vto_pago}</ar:FchVtoPago>"
        )

    det = (
        "<ar:FECAEDetRequest>"
        f"<ar:Concepto>{datos.concepto}</ar:Concepto>"
        f"<ar:DocTipo>{datos.doc_tipo}</ar:DocTipo>"
        f"<ar:DocNro>{datos.doc_nro or 0}</ar:DocNro>"
        f"<ar:CbteDesde>{datos.numero}</ar:CbteDesde>"
        f"<ar:CbteHasta>{datos.numero}</ar:CbteHasta>"
        f"<ar:CbteFch>{datos.fecha_emision}</ar:CbteFch>"
        f"<ar:ImpTotal>{datos.importe_total:.2f}</ar:ImpTotal>"
        "<ar:ImpTotConc>0.00</ar:ImpTotConc>"
        f"<ar:ImpNeto>{datos.importe_neto:.2f}</ar:ImpNeto>"
        "<ar:ImpOpEx>0.00</ar:ImpOpEx>"
        f"<ar:ImpIVA>{datos.importe_iva:.2f}</ar:ImpIVA>"
        "<ar:ImpTrib>0.00</ar:ImpTrib>"
        f"{fechas_serv_xml}"
        "<ar:MonId>PES</ar:MonId><ar:MonCotiz>1</ar:MonCotiz>"
        f"{ivas_xml}"
        "</ar:FECAEDetRequest>"
    )
    body = (
        "<ar:FECAESolicitar>"
        "<ar:Auth>"
        f"<ar:Token>{token}</ar:Token><ar:Sign>{sign}</ar:Sign><ar:Cuit>{datos.cuit}</ar:Cuit>"
        "</ar:Auth>"
        "<ar:FeCAEReq>"
        f"<ar:FeCabReq><ar:CantReg>1</ar:CantReg><ar:PtoVta>{datos.punto_venta}</ar:PtoVta>"
        f"<ar:CbteTipo>{datos.tipo_comprobante}</ar:CbteTipo></ar:FeCabReq>"
        f"<ar:FeDetReq>{det}</ar:FeDetReq>"
        "</ar:FeCAEReq>"
        "</ar:FECAESolicitar>"
    )
    root = _soap_call(ambiente, "FECAESolicitar", body)

    # El detalle por comprobante (FECAEDetResponse) es la fuente de verdad — la cabecera
    # (FeCabResp) puede decir "A" parcial con un solo comprobante rechazado adentro.
    detalle_el = _find_local(root, "FECAEDetResponse") or root
    resultado_el = _find_local(detalle_el, "Resultado")
    resultado = resultado_el.text if resultado_el is not None else None

    errores = []
    for err in _findall_local(root, "Err"):
        codigo = _find_local(err, "Code")
        msg = _find_local(err, "Msg")
        errores.append(f"{codigo.text if codigo is not None else '?'}: {msg.text if msg is not None else ''}")
    observaciones = []
    for obs in _findall_local(detalle_el, "Obs"):
        codigo = _find_local(obs, "Code")
        msg = _find_local(obs, "Msg")
        observaciones.append(f"{codigo.text if codigo is not None else '?'}: {msg.text if msg is not None else ''}")

    if resultado != "A":
        detalle = errores or observaciones or ["ARCA no autorizó el comprobante (sin detalle)."]
        raise ArcaWsfeRechazo(f"Comprobante rechazado por ARCA (Resultado={resultado})", detalle)

    cae_el = _find_local(detalle_el, "CAE")
    vto_el = _find_local(detalle_el, "CAEFchVto")
    if cae_el is None or not cae_el.text:
        raise ArcaWsfeError("ARCA autorizó el comprobante pero no devolvió CAE — respuesta inesperada.")

    return {
        "cae": cae_el.text,
        "cae_vencimiento": vto_el.text if vto_el is not None else None,
        "observaciones": observaciones,
    }
