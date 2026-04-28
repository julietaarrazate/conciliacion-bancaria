"""Tests para el algoritmo de conciliación"""

import pytest
from datetime import date
from app.services.conciliacion import (
    buscar_match,
    parse_importe,
    norm_cuit,
    extraer_cuit_titular
)
from app.models.extracto import MovimientoBanco

def test_parse_importe():
    """Test parseo de importes con diversos formatos"""
    assert parse_importe(1000.50) == 1000.50
    assert parse_importe("$1000.50") == 1000.50
    assert parse_importe("1.000,50") == 1000.50  # Formato europeo
    assert parse_importe("1,000.50") == 1000.50  # Formato inglés
    assert parse_importe("") is None
    assert parse_importe(None) is None

def test_norm_cuit():
    """Test normalización de CUIT"""
    assert norm_cuit("20-12345678-9") == "20123456789"
    assert norm_cuit(20123456789) == "20123456789"
    assert norm_cuit(None) == ""
    assert norm_cuit("") == ""

def test_extraer_cuit_titular():
    """Test extracción de CUIT del titular"""
    assert extraer_cuit_titular("EMPRESA SA 20123456789 CONCEPTO") == "20123456789"
    assert extraer_cuit_titular("27-98765432-1 OTRO") == "2798765432"
    assert extraer_cuit_titular("SIN CUIT") == ""
    assert extraer_cuit_titular(None) == ""

def test_buscar_match_monto_unico():
    """Test buscar match cuando el monto es único"""
    # Crear movimiento ficticio
    mov = MovimientoBanco(
        id=1,
        extracto_id=1,
        monto=1000.0,
        titular="EMPRESA 20123456789",
        cliente_acreditado=None  # Está libre
    )

    # Buscar match
    resultado, status = buscar_match(
        monto=1000.0,
        cuit_planilla="20123456789",
        titular_planilla="EMPRESA SA",
        movimientos=[mov],
        movimientos_procesados=set()
    )

    assert resultado is not None
    assert resultado.id == 1
    assert status == "ok"

def test_buscar_match_no_encontrado():
    """Test cuando el monto no existe en el extracto"""
    mov = MovimientoBanco(
        id=1,
        extracto_id=1,
        monto=1000.0,
        titular="EMPRESA 20123456789",
        cliente_acreditado=None
    )

    resultado, status = buscar_match(
        monto=2000.0,  # Monto diferente
        cuit_planilla="20123456789",
        titular_planilla="EMPRESA SA",
        movimientos=[mov],
        movimientos_procesados=set()
    )

    assert resultado is None
    assert status == "no está"

def test_buscar_match_duplicado():
    """Test cuando el movimiento ya fue acreditado"""
    mov = MovimientoBanco(
        id=1,
        extracto_id=1,
        monto=1000.0,
        titular="EMPRESA 20123456789",
        cliente_acreditado="OTRO_CLIENTE"  # Ya acreditado
    )

    resultado, status = buscar_match(
        monto=1000.0,
        cuit_planilla="20123456789",
        titular_planilla="EMPRESA SA",
        movimientos=[mov],
        movimientos_procesados={1}  # Ya procesado
    )

    assert resultado is None
    assert status == "duplicado"

def test_buscar_match_monto_comun_sin_cuit():
    """Test cuando el monto es común pero no hay CUIT"""
    # 3 movimientos con el mismo monto (monto común)
    movimientos = [
        MovimientoBanco(id=1, extracto_id=1, monto=5000.0, titular="EMPRESA 20123456789", cliente_acreditado=None),
        MovimientoBanco(id=2, extracto_id=1, monto=5000.0, titular="OTRA 27987654321", cliente_acreditado=None),
        MovimientoBanco(id=3, extracto_id=1, monto=5000.0, titular="TERCERA 23456789012", cliente_acreditado=None),
    ]

    # Sin CUIT ni titular en la planilla
    resultado, status = buscar_match(
        monto=5000.0,
        cuit_planilla=None,
        titular_planilla=None,
        movimientos=movimientos,
        movimientos_procesados=set()
    )

    assert resultado is None
    assert status == "faltan datos"
