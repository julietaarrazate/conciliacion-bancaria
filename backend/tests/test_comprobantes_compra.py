"""Tests de "Comprobantes por revisar" (facturas de compra por mail + lectura con IA).

Cubre:
  - funciones puras: montos en formato argentino, CUIT, normalización de lo que
    devuelve la IA, controles automáticos, firma Svix del webhook, filtro de adjuntos.
  - subida → lectura con IA (mockeada) → bandeja → confirmar → ComprobanteIva.
  - confirmar con pago → Egreso; nota de crédito no genera pago.
  - sin duplicados: confirmar dos veces / ya cargado en IVA / import posterior
    de "Mis Comprobantes" cuenta la factura como duplicada.
  - webhook de Resend: firma, destinatario, idempotencia, mail sin adjunto.
  - permisos y aislamiento multi-tenant.
No toca la red ni Gemini.
"""
import base64
import hashlib
import hmac
import io
import json
import time
from datetime import date
from decimal import Decimal

import openpyxl
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.database import Base, get_db
from app.main import app
from app.models.comprobante_compra import BorradorComprobante, BuzonComprobantes
from app.models.egreso import Egreso
from app.models.iva_liquidacion import ComprobanteIva
from app.models.organizacion import Organizacion
from app.models.user import User
from app.routers import comprobantes_compra as router_mod
from app.services import comprobantes_compra_service as svc
from app.services.auth import create_access_token, get_password_hash

CUIT_PROV = "30690783521"   # CUIT real con dígito verificador válido

RESPUESTA_IA = {
    "tipo_codigo": 1, "punto_venta": "0010", "numero": "00000999",
    "fecha": "2026-09-15", "cuit_emisor": "30-69078352-1",
    "razon_social": "INTERBANKING SA", "cae": "76123456789012",
    "alicuotas": [{"alicuota": "21%", "neto": "20.000,00", "iva": 4200}],
    "neto_no_gravado": None, "exento": None,
    "percepciones_iva": 600, "percepciones_iibb": "500.00",
    "otros_tributos": None, "total": 25300,
}

PDF = b"%PDF-1.4 factura de prueba"


# ── Fixtures ───────────────────────────────────────────────────────

@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    for oid, nombre in [(1, "Org1"), (2, "Org2")]:
        session.add(Organizacion(id=oid, nombre=nombre))
    session.commit()
    usuarios = [
        ("admin@cc.test", 1, "admin"),
        ("admin2@cc.test", 2, "admin"),
        ("revisor@cc.test", 1, "revisor"),
    ]
    for email, oid, rol in usuarios:
        session.add(User(email=email, full_name=email, hashed_password=get_password_hash("pw"),
                         organizacion_id=oid, is_active=True, role=rol, is_superadmin=False))
    session.commit()
    yield session
    session.close()


@pytest.fixture
def client(db, monkeypatch):
    def _override_db():
        yield db
    app.dependency_overrides[get_db] = _override_db
    # El procesamiento en segundo plano usa una sesión propia sobre la misma DB.
    monkeypatch.setattr(router_mod, "_session_factory", sessionmaker(bind=db.get_bind()))
    monkeypatch.setattr(svc, "ocr_factura", lambda mime, contenido: dict(RESPUESTA_IA))
    c = TestClient(app, raise_server_exceptions=True)
    yield c
    app.dependency_overrides.pop(get_db, None)


def _auth(db, email):
    u = db.query(User).filter(User.email == email).first()
    tok = create_access_token({"sub": u.email, "user_id": u.id, "role": u.role})
    return {"Authorization": f"Bearer {tok}"}


def _subir(client, headers, nombre="factura.pdf", contenido=PDF, mime="application/pdf"):
    return client.post("/comprobantes-compra/subir", headers=headers,
                       files=[("files", (nombre, contenido, mime))])


def _borrador_listo(client, db, email="admin@cc.test"):
    r = _subir(client, _auth(db, email))
    assert r.status_code == 200, r.text
    bid = r.json()["borradores"][0]["id"]
    db.expire_all()
    return bid


# ── Funciones puras ────────────────────────────────────────────────

@pytest.mark.parametrize("raw,esperado", [
    (25300, Decimal("25300.00")),
    ("20.000,00", Decimal("20000.00")),
    ("1.005.282", Decimal("1005282.00")),
    ("1005282.5", Decimal("1005282.50")),
    ("$ 4.200,50", Decimal("4200.50")),
    (None, None), ("", None), ("abc", None),
])
def test_parse_decimal_formato_argentino(raw, esperado):
    assert svc.parse_decimal(raw) == esperado


def test_cuit_valido():
    assert svc.cuit_valido(CUIT_PROV)
    assert not svc.cuit_valido("30690783522")     # dígito verificador mal
    assert not svc.cuit_valido("3069078352")      # 10 dígitos
    assert not svc.cuit_valido(None)


def test_normalizar_datos_de_la_ia():
    d = svc.normalizar_datos(RESPUESTA_IA)
    assert d["tipo_codigo"] == 1
    assert d["punto_venta"] == 10 and d["numero"] == 999
    assert d["cuit_emisor"] == CUIT_PROV
    assert d["alicuotas"] == {"21%": {"neto": "20000.00", "iva": "4200.00"}}
    assert d["percepciones_iibb"] == "500.00"
    assert d["total"] == "25300.00"
    assert svc.validar_datos(d, hoy=date(2026, 10, 4)) == []


def test_normalizar_tipo_por_letra_y_clase():
    assert svc.normalizar_datos({"letra": "B", "clase": "nota de crédito"})["tipo_codigo"] == 8
    assert svc.normalizar_datos({"letra": "c"})["tipo_codigo"] == 11
    assert svc.normalizar_datos({"tipo_codigo": 999})["tipo_codigo"] is None


def test_normalizar_alicuotas_en_formato_canonico_y_numerico():
    d = svc.normalizar_datos({"alicuotas": {"10.5%": {"neto": "1000", "iva": "105"}}})
    assert d["alicuotas"] == {"10.5%": {"neto": "1000.00", "iva": "105.00"}}
    d = svc.normalizar_datos({"alicuotas": [{"alicuota": 21, "neto": 100, "iva": 21}]})
    assert "21%" in d["alicuotas"]


def test_normalizar_respuesta_lista_o_vacia():
    assert svc.normalizar_datos([RESPUESTA_IA])["numero"] == 999
    assert svc.normalizar_datos(None)["total"] is None


def test_validar_detecta_problemas():
    hoy = date(2026, 10, 4)
    d = svc.normalizar_datos({**RESPUESTA_IA, "total": 30000})
    assert any("no cierra" in a for a in svc.validar_datos(d, hoy))

    d = svc.normalizar_datos({**RESPUESTA_IA, "alicuotas": [{"alicuota": "21%", "neto": 20000, "iva": 3000}],
                              "total": 24100})
    assert any("IVA 21%" in a for a in svc.validar_datos(d, hoy))

    d = svc.normalizar_datos({**RESPUESTA_IA, "tipo_codigo": 11})
    assert any("comprobante C" in a for a in svc.validar_datos(d, hoy))

    d = svc.normalizar_datos({**RESPUESTA_IA, "cuit_emisor": "30690783522"})
    assert any("CUIT" in a for a in svc.validar_datos(d, hoy))

    d = svc.normalizar_datos({"total": 100})
    assert any(a.startswith("Falta completar") for a in svc.validar_datos(d, hoy))

    d = svc.normalizar_datos({**RESPUESTA_IA, "fecha": "2026-12-01"})
    assert any("posterior a hoy" in a for a in svc.validar_datos(d, hoy))


def _firmar(secret_b64: str, msg_id: str, ts: str, body: bytes) -> str:
    firma = hmac.new(base64.b64decode(secret_b64), f"{msg_id}.{ts}.".encode() + body,
                     hashlib.sha256).digest()
    return "v1," + base64.b64encode(firma).decode()


SECRET_B64 = base64.b64encode(b"clave-de-prueba-del-webhook").decode()
SECRET = "whsec_" + SECRET_B64


def test_verificar_firma_svix():
    body = b'{"type":"email.received"}'
    ts = str(int(time.time()))
    headers = {"svix-id": "msg_1", "svix-timestamp": ts,
               "svix-signature": "v1,otrafirma " + _firmar(SECRET_B64, "msg_1", ts, body)}
    assert svc.verificar_firma_svix(SECRET, headers, body)
    assert not svc.verificar_firma_svix(SECRET, headers, body + b" ")
    assert not svc.verificar_firma_svix("", headers, body)
    viejo = {**headers, "svix-timestamp": str(int(ts) - 3600)}
    assert not svc.verificar_firma_svix(SECRET, viejo, body)


def test_adjuntos_utiles_filtra_logos_y_otros_formatos():
    adj = [
        {"id": "a1", "filename": "factura.pdf", "content_type": "application/pdf"},
        {"id": "a2", "filename": "logo.png", "content_type": "image/png",
         "content_disposition": "inline", "content_id": "img001"},
        {"id": "a3", "filename": "planilla.xlsx", "content_type": "application/vnd.ms-excel"},
        {"id": "a4", "filename": "foto.JPG", "content_type": "application/octet-stream"},
    ]
    assert [a["id"] for a in svc.adjuntos_utiles(adj)] == ["a1", "a4"]


# ── Subida, bandeja y confirmación ─────────────────────────────────

def test_subir_lee_con_ia_y_queda_listo(client, db):
    bid = _borrador_listo(client, db)
    r = client.get("/comprobantes-compra?estado=pendientes", headers=_auth(db, "admin@cc.test"))
    assert r.status_code == 200
    item = r.json()["items"][0]
    assert item["id"] == bid and item["estado"] == "listo"
    assert item["archivo"] is None                         # la bandeja no trae el archivo
    assert item["datos"]["razon_social"] == "INTERBANKING SA"
    assert item["alertas"] == []
    det = client.get(f"/comprobantes-compra/{bid}", headers=_auth(db, "admin@cc.test")).json()
    assert det["archivo"].startswith("data:application/pdf;base64,")


def test_subir_rechaza_formato_y_tamano(client, db):
    h = _auth(db, "admin@cc.test")
    assert _subir(client, h, "x.xlsx", b"abc", "application/vnd.ms-excel").status_code == 400
    grande = b"0" * (svc.MAX_ARCHIVO_BYTES + 1)
    assert _subir(client, h, "x.pdf", grande).status_code == 400
    muchos = [("files", (f"f{i}.pdf", PDF, "application/pdf")) for i in range(11)]
    assert client.post("/comprobantes-compra/subir", headers=h, files=muchos).status_code == 400


def test_ia_falla_queda_en_error_y_se_puede_reintentar(client, db, monkeypatch):
    def _falla(mime, contenido):
        raise ValueError("gemini caído")
    monkeypatch.setattr(svc, "ocr_factura", _falla)
    bid = _borrador_listo(client, db)
    b = db.get(BorradorComprobante, bid)
    assert b.estado == "error" and "No se pudo leer" in b.error

    monkeypatch.setattr(svc, "ocr_factura", lambda m, c: dict(RESPUESTA_IA))
    r = client.post(f"/comprobantes-compra/{bid}/reprocesar", headers=_auth(db, "admin@cc.test"))
    assert r.status_code == 200
    db.expire_all()
    assert db.get(BorradorComprobante, bid).estado == "listo"


def test_confirmar_crea_comprobante_en_iva(client, db):
    bid = _borrador_listo(client, db)
    r = client.post(f"/comprobantes-compra/{bid}/confirmar", headers=_auth(db, "admin@cc.test"), json={})
    assert r.status_code == 200, r.text
    assert r.json()["egreso_id"] is None
    comp = db.query(ComprobanteIva).one()
    assert comp.direccion == "recibido" and comp.periodo == "2026-09"
    assert comp.tipo_codigo == 1 and comp.punto_venta == 10 and comp.numero == 999
    assert comp.cuit_contraparte == CUIT_PROV
    assert comp.total_iva == Decimal("4200.00")
    assert comp.neto_gravado_total == Decimal("20000.00")
    assert comp.imp_total == Decimal("25300.00")
    assert comp.detalle_alicuotas["21%"]["iva"] == 4200.0
    db.expire_all()
    assert db.get(BorradorComprobante, bid).estado == "confirmado"

    # Confirmar de nuevo no duplica.
    r = client.post(f"/comprobantes-compra/{bid}/confirmar", headers=_auth(db, "admin@cc.test"), json={})
    assert r.status_code == 409
    assert db.query(ComprobanteIva).count() == 1


def test_confirmar_con_datos_corregidos_y_periodo(client, db):
    bid = _borrador_listo(client, db)
    corregidos = {**RESPUESTA_IA, "numero": 1000}
    r = client.post(f"/comprobantes-compra/{bid}/confirmar", headers=_auth(db, "admin@cc.test"),
                    json={"datos": corregidos, "periodo": "2026-10"})
    assert r.status_code == 200, r.text
    comp = db.query(ComprobanteIva).one()
    assert comp.numero == 1000 and comp.periodo == "2026-10"


def test_confirmar_sin_datos_obligatorios_422(client, db):
    bid = _borrador_listo(client, db)
    r = client.post(f"/comprobantes-compra/{bid}/confirmar", headers=_auth(db, "admin@cc.test"),
                    json={"datos": {**RESPUESTA_IA, "cuit_emisor": None}})
    assert r.status_code == 422
    assert db.query(ComprobanteIva).count() == 0


def test_dos_borradores_misma_factura_no_duplican_iva(client, db):
    b1 = _borrador_listo(client, db)
    b2 = _borrador_listo(client, db)
    h = _auth(db, "admin@cc.test")
    assert client.post(f"/comprobantes-compra/{b1}/confirmar", headers=h, json={}).status_code == 200
    det = client.get(f"/comprobantes-compra/{b2}", headers=h).json()
    assert det["estado"] == "listo"
    r = client.post(f"/comprobantes-compra/{b2}/confirmar", headers=h, json={})
    assert r.status_code == 409
    assert db.query(ComprobanteIva).count() == 1


def test_lectura_avisa_si_ya_esta_en_iva(client, db):
    b1 = _borrador_listo(client, db)
    client.post(f"/comprobantes-compra/{b1}/confirmar", headers=_auth(db, "admin@cc.test"), json={})
    b2 = _borrador_listo(client, db)
    assert "Este comprobante ya está cargado en IVA." in db.get(BorradorComprobante, b2).alertas


def test_import_mis_comprobantes_posterior_cuenta_duplicado(client, db):
    bid = _borrador_listo(client, db)
    h = _auth(db, "admin@cc.test")
    client.post(f"/comprobantes-compra/{bid}/confirmar", headers=h, json={})

    headers = ["Fecha", "Tipo", "Punto de Venta", "Número Desde", "Número Hasta",
               "Cód. Autorización", "Tipo Doc. Emisor", "Nro. Doc. Emisor", "Denominación Emisor",
               "Tipo Doc. Receptor", "Nro. Doc. Receptor", "Tipo Cambio", "Moneda",
               "IVA 21%", "Neto Grav. IVA 21%", "Neto Gravado Total", "Total IVA", "Imp. Total"]
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Mis Comprobantes Recibidos"] + [None] * (len(headers) - 1))
    ws.append(headers)
    ws.append(["15/09/2026", "1 - Factura A", 10, 999, 999, 1, "CUIT", int(CUIT_PROV),
               "INTERBANKING SA", "CUIT", 30716892871, 1, "$", 4200, 20000, 20000, 4200, 25300])
    buf = io.BytesIO()
    wb.save(buf)
    r = client.post("/iva/comprobantes/importar?direccion=recibido&periodo=2026-09", headers=h,
                    files={"file": ("mc.xlsx", buf.getvalue(),
                                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert r.status_code == 200, r.text
    assert r.json()["importados"] == 0 and r.json()["duplicados"] == 1
    assert db.query(ComprobanteIva).count() == 1


def test_confirmar_con_pago_crea_egreso(client, db):
    bid = _borrador_listo(client, db)
    r = client.post(f"/comprobantes-compra/{bid}/confirmar", headers=_auth(db, "admin@cc.test"),
                    json={"registrar_pago": True, "fecha_pago": "2026-09-20"})
    assert r.status_code == 200, r.text
    eg = db.query(Egreso).one()
    assert r.json()["egreso_id"] == eg.id
    assert eg.tipo == "proveedor" and eg.forma_pago == "banco"
    assert eg.monto == Decimal("25300.00") and eg.fecha == date(2026, 9, 20)
    assert eg.beneficiario == "INTERBANKING SA"
    assert eg.foto_comprobante is None                 # un PDF no se muestra como foto en Pagos


def test_nota_de_credito_no_genera_pago(client, db, monkeypatch):
    monkeypatch.setattr(svc, "ocr_factura", lambda m, c: {**RESPUESTA_IA, "tipo_codigo": 3})
    bid = _borrador_listo(client, db)
    r = client.post(f"/comprobantes-compra/{bid}/confirmar", headers=_auth(db, "admin@cc.test"),
                    json={"registrar_pago": True})
    assert r.status_code == 200
    assert r.json()["egreso_id"] is None
    assert db.query(Egreso).count() == 0


def test_descartar(client, db):
    bid = _borrador_listo(client, db)
    h = _auth(db, "admin@cc.test")
    assert client.post(f"/comprobantes-compra/{bid}/descartar", headers=h).json()["estado"] == "descartado"
    assert client.post(f"/comprobantes-compra/{bid}/confirmar", headers=h, json={}).status_code == 409


# ── Permisos y multi-tenant ────────────────────────────────────────

def test_otra_org_no_ve_ni_confirma(client, db):
    bid = _borrador_listo(client, db)
    h2 = _auth(db, "admin2@cc.test")
    assert client.get(f"/comprobantes-compra/{bid}", headers=h2).status_code == 404
    assert client.post(f"/comprobantes-compra/{bid}/confirmar", headers=h2, json={}).status_code == 404
    assert client.get("/comprobantes-compra", headers=h2).json()["items"] == []


def test_revisor_no_sube_ni_confirma(client, db):
    bid = _borrador_listo(client, db)
    hr = _auth(db, "revisor@cc.test")
    assert client.get("/comprobantes-compra", headers=hr).status_code == 200
    assert _subir(client, hr).status_code == 403
    assert client.post(f"/comprobantes-compra/{bid}/confirmar", headers=hr, json={}).status_code == 403
    assert client.post("/comprobantes-compra/buzon/activar", headers=hr).status_code == 403


# ── Buzón y webhook ────────────────────────────────────────────────

DOMINIO = "cuadra-test.resend.app"


@pytest.fixture
def mail_config(monkeypatch):
    s = Settings(resend_inbound_secret=SECRET, inbound_email_domain=DOMINIO, resend_api_key="re_test")
    monkeypatch.setattr(router_mod, "get_settings", lambda: s)
    monkeypatch.setattr(svc, "descargar_adjunto_resend", lambda key, email_id, adj_id: PDF)
    return s


def _activar(client, db, email="admin@cc.test"):
    r = client.post("/comprobantes-compra/buzon/activar", headers=_auth(db, email))
    assert r.status_code == 200, r.text
    return r.json()["direccion"]


def _webhook(client, payload: dict, firmar=True):
    body = json.dumps(payload).encode()
    ts = str(int(time.time()))
    firma = _firmar(SECRET_B64, "msg_x", ts, body) if firmar else "v1,mala"
    return client.post("/comprobantes-compra/webhook/resend", content=body, headers={
        "svix-id": "msg_x", "svix-timestamp": ts, "svix-signature": firma,
        "content-type": "application/json",
    })


def _evento(direccion, email_id="em_1", adjuntos=None, subject="Factura 0010-00000999"):
    return {"type": "email.received", "data": {
        "email_id": email_id, "from": "facturacion@interbanking.com.ar",
        "to": ["contaduria@cliente.com"], "cc": [], "received_for": [direccion],
        "subject": subject,
        "attachments": adjuntos if adjuntos is not None else [
            {"id": "att_1", "filename": "FA-0010-999.pdf", "content_type": "application/pdf"},
        ],
    }}


def test_buzon_sin_configurar_no_muestra_direccion(client, db):
    h = _auth(db, "admin@cc.test")
    client.post("/comprobantes-compra/buzon/activar", headers=h)
    r = client.get("/comprobantes-compra/buzon", headers=h).json()
    assert r == {"configurado": False, "activo": True, "direccion": None}


def test_buzon_activar_y_regenerar(client, db, mail_config):
    d1 = _activar(client, db)
    assert d1.startswith("facturas-") and d1.endswith("@" + DOMINIO)
    assert client.get("/comprobantes-compra/buzon", headers=_auth(db, "admin@cc.test")).json()["direccion"] == d1
    r = client.post("/comprobantes-compra/buzon/activar?regenerar=true", headers=_auth(db, "admin@cc.test"))
    assert r.json()["direccion"] != d1
    assert db.query(BuzonComprobantes).count() == 1


def test_webhook_crea_borrador_y_lo_lee(client, db, mail_config):
    direccion = _activar(client, db)
    r = _webhook(client, _evento(direccion))
    assert r.status_code == 200 and r.json()["borradores"] == 1
    db.expire_all()
    b = db.query(BorradorComprobante).one()
    assert b.organizacion_id == 1 and b.origen == "email" and b.estado == "listo"
    assert b.remitente == "facturacion@interbanking.com.ar"
    assert b.archivo.startswith("data:application/pdf;base64,")
    assert b.datos["numero"] == 999

    # Resend reintenta el mismo evento → no duplica.
    assert _webhook(client, _evento(direccion)).json().get("duplicado") is True
    assert db.query(BorradorComprobante).count() == 1


def test_webhook_firma_invalida_401(client, db, mail_config):
    direccion = _activar(client, db)
    assert _webhook(client, _evento(direccion), firmar=False).status_code == 401
    assert db.query(BorradorComprobante).count() == 0


def test_webhook_sin_configurar_503(client, db):
    assert _webhook(client, _evento("facturas-xxxxxxxxxxxxxxxx@x.resend.app")).status_code == 503


def test_webhook_destinatario_desconocido_o_regenerado_se_ignora(client, db, mail_config):
    viejo = _activar(client, db)
    r = _webhook(client, _evento(f"facturas-noexiste1234567@{DOMINIO}"))
    assert r.json()["ignorado"] == "destinatario"
    client.post("/comprobantes-compra/buzon/activar?regenerar=true", headers=_auth(db, "admin@cc.test"))
    assert _webhook(client, _evento(viejo, email_id="em_2")).json()["ignorado"] == "destinatario"
    assert db.query(BorradorComprobante).count() == 0


def test_webhook_sin_adjunto_queda_visible(client, db, mail_config):
    direccion = _activar(client, db)
    asunto = "(#123456789) Confirmación de reenvío de Gmail"
    r = _webhook(client, _evento(direccion, adjuntos=[], subject=asunto))
    assert r.status_code == 200
    b = db.query(BorradorComprobante).one()
    assert b.estado == "sin_adjunto" and b.asunto == asunto


def test_webhook_va_a_la_org_del_buzon(client, db, mail_config):
    _activar(client, db)
    d2 = _activar(client, db, "admin2@cc.test")
    _webhook(client, _evento(d2))
    db.expire_all()
    assert db.query(BorradorComprobante).one().organizacion_id == 2
