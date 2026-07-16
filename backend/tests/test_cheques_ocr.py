"""Tests de las funciones puras de OCR de cheques (carga masiva por foto).

Cubren el parseo de la respuesta de Gemini (array o objeto único, con/ sin
fences markdown) y la normalización de cada cheque, incluido el casteo de monto
tolerante al formato argentino. No tocan la red ni la API de Gemini.
"""
from app.routers.cheques_common import (
    _parse_ocr_response,
    _normalize_ocr_cheque,
    _parse_monto_ocr,
)


# ── _parse_ocr_response ───────────────────────────────────────────

def test_parse_array_varios_cheques():
    texto = '[{"numero": "111"}, {"numero": "222"}, {"numero": "333"}]'
    out = _parse_ocr_response(texto)
    assert [c["numero"] for c in out] == ["111", "222", "333"]


def test_parse_objeto_unico_se_envuelve_en_lista():
    out = _parse_ocr_response('{"numero": "111", "monto": 350000}')
    assert len(out) == 1
    assert out[0]["numero"] == "111"


def test_parse_limpia_fences_markdown():
    texto = '```json\n[{"numero": "111"}]\n```'
    out = _parse_ocr_response(texto)
    assert out == [{"numero": "111"}]


def test_parse_texto_vacio_devuelve_lista_vacia():
    assert _parse_ocr_response("") == []
    assert _parse_ocr_response("   ") == []


def test_parse_descarta_objetos_todo_null():
    texto = '[{"numero": null, "monto": null}, {"numero": "222"}]'
    out = _parse_ocr_response(texto)
    assert len(out) == 1
    assert out[0]["numero"] == "222"


def test_parse_json_invalido_propaga_decode_error():
    import json
    import pytest
    with pytest.raises(json.JSONDecodeError):
        _parse_ocr_response("no soy json")


# ── _parse_monto_ocr (formato argentino) ──────────────────────────

def test_monto_numero_directo():
    assert _parse_monto_ocr(350000) == 350000.0
    assert _parse_monto_ocr(150000.5) == 150000.5


def test_monto_string_plano():
    assert _parse_monto_ocr("350000") == 350000.0


def test_monto_argentino_con_decimales():
    # "350.000,00" → coma decimal, punto de miles
    assert _parse_monto_ocr("350.000,00") == 350000.0


def test_monto_argentino_solo_miles():
    # "1.005.282" → varios puntos, sin coma → separador de miles
    assert _parse_monto_ocr("1.005.282") == 1005282.0


def test_monto_decimal_plano_no_se_rompe():
    # "1005282.00" → un solo punto, sin coma → decimal, NO miles
    assert _parse_monto_ocr("1005282.00") == 1005282.0


def test_monto_con_signo_pesos():
    assert _parse_monto_ocr("$ 270.000,00") == 270000.0


def test_monto_none_o_invalido():
    assert _parse_monto_ocr(None) is None
    assert _parse_monto_ocr("no es un número") is None
    assert _parse_monto_ocr("") is None


# ── _normalize_ocr_cheque ─────────────────────────────────────────

def test_normalize_mapea_index_y_campos():
    datos = {
        "numero": " 91678722 ",
        "banco_origen": "Banco Provincia",
        "librador": "OSCAR DI ZILLO",
        "monto": "350.000,00",
        "fecha_emision": "2026-07-02",
        "fecha_deposito": None,
        "codigo_postal": "6620",
    }
    item = _normalize_ocr_cheque(datos, index=3, filename="lote.jpg")
    assert item["index"] == 3
    assert item["filename"] == "lote.jpg"
    assert item["numero"] == "91678722"          # trim
    assert item["banco_origen"] == "Banco Provincia"
    assert item["monto"] == 350000.0
    assert item["fecha_emision"] == "2026-07-02"
    assert item["fecha_deposito"] is None
    assert item["codigo_postal"] == "6620"
    assert item["local_interior"] == "interior"  # CP >= 2000
    assert item["error"] is False


def test_normalize_varios_cheques_misma_foto_comparten_index():
    crudos = [{"numero": "111", "monto": 100}, {"numero": "222", "monto": 200}]
    items = [_normalize_ocr_cheque(d, index=0, filename="mesa.jpg") for d in crudos]
    assert all(it["index"] == 0 for it in items)
    assert [it["numero"] for it in items] == ["111", "222"]


def test_normalize_monto_ilegible_queda_none():
    item = _normalize_ocr_cheque({"numero": "111", "monto": "ilegible"}, 0, "f.jpg")
    assert item["monto"] is None
    assert item["numero"] == "111"


def test_normalize_local_para_cp_bajo():
    item = _normalize_ocr_cheque({"codigo_postal": "1425"}, 0, "f.jpg")
    assert item["local_interior"] == "local"     # CP < 2000
