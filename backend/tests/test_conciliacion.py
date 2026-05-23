"""Tests para el algoritmo de conciliación.

Cubre las funciones puras (parseo de importes, normalización de CUIT, extracción)
y los casos básicos de matching con la config default de Caneland.
"""

import pytest
from datetime import date
from app.services.conciliacion import (
    buscar_match,
    parse_importe,
    norm_cuit,
    extraer_cuit,
    extraer_cbu,
    CONFIG_CANELAND,
)
from app.models.extracto import MovimientoBanco


def test_parse_importe_formatos_varios():
    assert parse_importe(1000.50) == 1000.50
    assert parse_importe("$1000.50") == 1000.50
    assert parse_importe("1.000,50") == 1000.50
    assert parse_importe("1,000.50") == 1000.50
    assert parse_importe("") is None
    assert parse_importe(None) is None


def test_norm_cuit():
    assert norm_cuit("20-12345678-9") == "20123456789"
    assert norm_cuit(20123456789) == "20123456789"
    assert norm_cuit(None) == ""
    assert norm_cuit("") == ""


def test_extraer_cuit_del_titular():
    assert extraer_cuit("EMPRESA SA 20123456789 CONCEPTO") == "20123456789"
    assert extraer_cuit("SIN CUIT") == ""
    assert extraer_cuit(None) == ""


def test_extraer_cbu_solo_22_digitos():
    assert extraer_cbu("CBU 2850590940090418135201 EMPRESA") == "2850590940090418135201"
    assert extraer_cbu("solo 11 digitos 20123456789") == ""
    assert extraer_cbu(None) == ""


def _mov(monto, titular="", cliente_acreditado=None, id=1, fecha=None):
    return MovimientoBanco(
        id=id, extracto_id=1, monto=monto, titular=titular,
        cliente_acreditado=cliente_acreditado, fecha=fecha,
    )


def test_buscar_match_monto_unico_acredita_directo():
    """Si el monto aparece UNA sola vez en el extracto, se acredita aunque no haya CUIT."""
    mov = _mov(1000.0, titular="EMPRESA 20123456789")
    resultado, status = buscar_match(
        monto=1000.0,
        cuit_planilla="20123456789",
        titular_planilla="EMPRESA SA",
        referencia_planilla=None,
        fecha_planilla=None,
        movimientos=[mov],
        procesados=set(),
        org_config=CONFIG_CANELAND,
    )
    assert resultado is not None and resultado.id == 1
    assert status == "ok"


def test_buscar_match_monto_inexistente():
    mov = _mov(1000.0)
    resultado, status = buscar_match(
        monto=2000.0,
        cuit_planilla="20123456789",
        titular_planilla="EMPRESA SA",
        referencia_planilla=None,
        fecha_planilla=None,
        movimientos=[mov],
        procesados=set(),
        org_config=CONFIG_CANELAND,
    )
    assert resultado is None
    assert "no" in status.lower() or "está" in status.lower()


def test_buscar_match_ya_procesado_no_se_duplica():
    """Un movimiento que ya fue acreditado a otra fila no debe re-acreditarse."""
    mov = _mov(1000.0, titular="EMPRESA 20123456789")
    resultado, status = buscar_match(
        monto=1000.0,
        cuit_planilla="20123456789",
        titular_planilla="EMPRESA SA",
        referencia_planilla=None,
        fecha_planilla=None,
        movimientos=[mov],
        procesados={1},  # ya usado
        org_config=CONFIG_CANELAND,
    )
    assert resultado is None


def test_buscar_match_monto_duplicado_exige_identidad():
    """REGLA CRÍTICA: si el monto aparece 2+ veces, NUNCA acreditar sin identidad."""
    movimientos = [
        _mov(5000.0, titular="EMPRESA A 20111111110", id=1),
        _mov(5000.0, titular="EMPRESA B 27222222220", id=2),
        _mov(5000.0, titular="EMPRESA C 30333333330", id=3),
    ]
    # Sin CUIT ni titular en la planilla — no se puede identificar
    resultado, status = buscar_match(
        monto=5000.0,
        cuit_planilla=None,
        titular_planilla=None,
        referencia_planilla=None,
        fecha_planilla=None,
        movimientos=movimientos,
        procesados=set(),
        org_config=CONFIG_CANELAND,
    )
    assert resultado is None, "no debe acreditar sin identidad cuando el monto se repite"


def test_buscar_match_monto_duplicado_con_cuit_correcto_acredita():
    """Con monto duplicado, el CUIT correcto desempata."""
    movimientos = [
        _mov(5000.0, titular="EMPRESA A 20111111110", id=1),
        _mov(5000.0, titular="EMPRESA B 27222222220", id=2),
    ]
    resultado, status = buscar_match(
        monto=5000.0,
        cuit_planilla="27222222220",
        titular_planilla="EMPRESA B",
        referencia_planilla=None,
        fecha_planilla=None,
        movimientos=movimientos,
        procesados=set(),
        org_config=CONFIG_CANELAND,
    )
    assert resultado is not None
    assert resultado.id == 2
    assert status == "ok"
