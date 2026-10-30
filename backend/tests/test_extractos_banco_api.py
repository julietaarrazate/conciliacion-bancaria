# ruff: noqa: F811  (fixtures `client`/`db` importados del módulo de preview)
"""API: reconocer el banco de un extracto Excel/CSV en el preview y el upload, y
recordar el banco que eligió la persona (por organización).

Archivos sintéticos; CBU ficticios con verificadores bien (`cbu_ficticio`).
"""

from __future__ import annotations

import json

from app.models.extracto import ExtractoBancario, MovimientoBanco
from app.models.extracto_plantilla import PlantillaExtractoExcel
from tests.extracto_sintetico import movimientos_cronologicos, xlsx_desde_filas, xlsx_estilo_macro
from tests.test_banco_identificacion import cbu_ficticio
from tests.test_extractos_preview_api import (  # noqa: F401 (fixtures)
    XLSX, _h, _sin_rate_limit, client, db,
)


def _preview(client, h, contenido, nombre="ext.xlsx", mapeo=None):
    data = {"mapeo": json.dumps(mapeo)} if mapeo is not None else {}
    return client.post("/extractos/preview", headers=h, files={"file": (nombre, contenido, XLSX)}, data=data)


def _upload(client, h, contenido, nombre="ext.xlsx", banco_clave=None, banco=None):
    data = {"banco_clave": banco_clave} if banco_clave else {}
    url = "/extractos/upload" + (f"?banco={banco}" if banco else "")
    return client.post(url, headers=h, files={"file": (nombre, contenido, XLSX)}, data=data)


def _extracto(membrete: list[list], encabezado=("Fecha", "Concepto", "Importe", "Saldo"),
              conceptos: list[str] | None = None) -> bytes:
    filas = [list(f) for f in membrete] + [list(encabezado)]
    for i, m in enumerate(movimientos_cronologicos(4)):
        titular = conceptos[i] if conceptos else m["titular"]
        filas.append([m["fecha"].strftime("%d/%m/%Y"), titular, float(m["monto"]), float(m["saldo"])])
    return xlsx_desde_filas(filas)


def _limpiar(db):
    db.query(MovimientoBanco).delete()
    db.query(ExtractoBancario).delete()
    db.commit()


def test_preview_reconoce_el_banco_solo_por_el_cbu(client, db):
    cbu = cbu_ficticio("007")
    r = _preview(client, _h(db, "admin1@t.test"), _extracto([["Resumen de cuenta"], [f"CBU: {cbu}"]]))
    b = r.json()
    assert b["banco_clave"] == "galicia" and b["banco"] == "Galicia"
    assert b["banco_deteccion"]["motivo"] == "por el CBU de la cuenta"
    assert b["banco_deteccion"]["pedir_confirmacion"] is False


def test_cbu_le_gana_al_nombre_y_avisa(client, db):
    cbu = cbu_ficticio("072")
    b = _preview(client, _h(db, "admin1@t.test"),
                 _extracto([["Banco Macro"], [f"Cuenta {cbu}"]])).json()
    assert b["banco_clave"] == "santander"
    assert "Banco Macro" in b["banco_deteccion"]["conflicto"]


def test_cbu_de_un_movimiento_no_cuenta(client, db):
    """El CBU de la contraparte en el concepto de un movimiento no define el banco."""
    otro = cbu_ficticio("285")
    conceptos = [f"TRANSF DESDE CBU {otro}"] * 4
    b = _preview(client, _h(db, "admin1@t.test"), _extracto([["Resumen"]], conceptos=conceptos)).json()
    assert b["banco_clave"] == "generico"
    assert b["banco_deteccion"]["pedir_confirmacion"] is True


def test_cbu_en_el_nombre_del_archivo(client, db):
    cbu = cbu_ficticio("191")
    b = _preview(client, _h(db, "admin1@t.test"), _extracto([["Resumen"]]), nombre=f"mov_{cbu}.xlsx").json()
    assert b["banco_clave"] == "credicoop"


def test_estructura_macro_sin_nombre(client, db):
    b = _preview(client, _h(db, "admin1@t.test"), xlsx_estilo_macro(6, titulo="Extracto mayo")).json()
    assert b["banco_clave"] == "macro"
    assert b["banco_deteccion"]["motivo"] == "por el formato del archivo"


def test_estructura_macro_por_conceptos(client, db):
    conceptos = ["ING TRANSF: GOMEZ", "ING TRANSF: PEREZ", "COMISION", "ING TRANSF: DIAZ"]
    b = _preview(client, _h(db, "admin1@t.test"), _extracto([["Resumen"]], conceptos=conceptos)).json()
    assert b["banco_clave"] == "macro"


def test_sin_señales_es_generico_y_pide_elegir(client, db):
    b = _preview(client, _h(db, "admin1@t.test"), _extracto([["Resumen de cuenta"]])).json()
    assert b["banco_clave"] == "generico" and b["banco"] is None
    assert b["banco_deteccion"]["confianza"] == 0.0
    assert b["banco_deteccion"]["pedir_confirmacion"] is True


def test_upload_guarda_el_banco_detectado_por_cbu(client, db):
    cbu = cbu_ficticio("017")
    r = _upload(client, _h(db, "admin1@t.test"), _extracto([[f"CBU {cbu}"]]))
    assert r.status_code == 200, r.text
    assert db.query(ExtractoBancario).one().banco == "BBVA"


def test_banco_elegido_se_guarda_y_se_recuerda_por_org(client, db):
    h1, h2 = _h(db, "admin1@t.test"), _h(db, "admin2@t.test")
    archivo = _extracto([["Resumen de cuenta"]])
    assert _preview(client, h1, archivo).json()["banco_clave"] == "generico"
    r = _upload(client, h1, archivo, banco_clave="brubank")
    assert r.status_code == 200, r.text
    assert db.query(ExtractoBancario).one().banco == "Brubank"
    p = db.query(PlantillaExtractoExcel).one()
    assert p.organizacion_id == 1 and p.banco_clave == "brubank" and p.mapeo.get("banco_confirmado")

    # La próxima vez en la misma org: "confirmado antes".
    b = _preview(client, h1, archivo).json()
    assert b["banco_clave"] == "brubank"
    assert b["banco_deteccion"]["motivo"] == "confirmado antes"
    _limpiar(db)
    assert _upload(client, h1, archivo).status_code == 200
    assert db.query(ExtractoBancario).one().banco == "Brubank"

    # Otra org no ve lo que eligió la org 1.
    b2 = _preview(client, h2, archivo).json()
    assert b2["banco_clave"] == "generico"


def test_correccion_le_gana_al_cbu_la_proxima_vez(client, db):
    h = _h(db, "admin1@t.test")
    archivo = _extracto([[f"CBU {cbu_ficticio('285')}"]])
    assert _preview(client, h, archivo).json()["banco_clave"] == "macro"
    assert _upload(client, h, archivo, banco_clave="nacion").status_code == 200
    assert db.query(ExtractoBancario).one().banco == "Banco Nación"
    b = _preview(client, h, archivo).json()
    assert b["banco_clave"] == "nacion"
    assert b["banco_deteccion"]["motivo"] == "confirmado antes"
    assert "Banco Macro" in b["banco_deteccion"]["conflicto"]


def test_aceptar_el_banco_detectado_con_seguridad_no_crea_plantilla(client, db):
    """Si el banco salió por el CBU y la persona lo deja como está, no hay nada que aprender."""
    archivo = _extracto([[f"CBU {cbu_ficticio('285')}"]])
    assert _upload(client, _h(db, "admin1@t.test"), archivo, banco_clave="macro").status_code == 200
    assert db.query(PlantillaExtractoExcel).count() == 0


def test_otro_banco_no_queda_como_macro(client, db):
    r = _upload(client, _h(db, "admin1@t.test"), _extracto([["Resumen"]]), banco_clave="generico")
    assert r.status_code == 200, r.text
    assert db.query(ExtractoBancario).one().banco == "Otro banco"


def test_banco_invalido_400(client, db):
    r = _upload(client, _h(db, "admin1@t.test"), _extracto([["Resumen"]]), banco_clave="inventado")
    assert r.status_code == 400


def test_lista_de_bancos(client, db):
    r = client.get("/extractos/bancos", headers=_h(db, "admin1@t.test"))
    claves = {b["clave"] for b in r.json()["items"]}
    assert {"macro", "galicia", "mercadopago", "brubank"} <= claves
