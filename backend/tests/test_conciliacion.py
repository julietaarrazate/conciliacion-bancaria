"""Tests para el algoritmo de conciliación.

Cubre las funciones puras (parseo de importes, normalización de CUIT, extracción)
y los casos básicos de matching con la config default.
"""

from datetime import date
from app.services.conciliacion import (
    buscar_match,
    parse_importe,
    norm_cuit,
    extraer_cuit,
    extraer_cbu,
    CONFIG_DEFAULT_ORG,
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
        org_config=CONFIG_DEFAULT_ORG,
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
        org_config=CONFIG_DEFAULT_ORG,
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
        org_config=CONFIG_DEFAULT_ORG,
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
        org_config=CONFIG_DEFAULT_ORG,
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
        org_config=CONFIG_DEFAULT_ORG,
    )
    assert resultado is not None
    assert resultado.id == 2
    assert status == "ok"


# ─── Regresión: asiento agrupado en re-conciliación (v3.13) ───────────────────
# Verifica que re-conciliar una planilla (solo_pendientes=True) deje el asiento
# um_reclass_planilla con el TOTAL de todas las filas ok, no solo el delta nuevo.

import pytest as _pytest
from decimal import Decimal as _Dec
from sqlalchemy import create_engine as _ce
from sqlalchemy.orm import sessionmaker as _sm
from app.database import Base as _Base
from app.models.organizacion import Organizacion as _Org
from app.models.cliente import Cliente as _Cli
from app.models.contabilidad import PlanCuenta as _PC, Asiento as _As
from app.models.planilla import Planilla as _Pl, PlanillaRow as _PR
from app.services.conciliacion import conciliar_planilla as _conciliar


@_pytest.fixture
def _db_cc():
    eng = _ce("sqlite:///:memory:", connect_args={"check_same_thread": False})
    _Base.metadata.create_all(bind=eng)
    s = _sm(bind=eng, autoflush=False, autocommit=False)()
    s.add(_Org(id=1, nombre="Test", plan="pro", activo=True))
    s.flush()
    # Plan mínimo: No identificado + padre cliente + cuenta del cliente
    s.add(_PC(id=1, codigo="2-1-1-1", nombre="No identificado", tipo="pasivo", nivel=4, activo=True, organizacion_id=1))
    padre = _PC(id=2, codigo="2-1-2-0", nombre="Clientes", tipo="pasivo", nivel=3, activo=True, organizacion_id=1)
    s.add(padre); s.flush()
    cuenta_cli = _PC(id=3, codigo="2-1-2-1", nombre="Green", tipo="pasivo", nivel=4, activo=True, organizacion_id=1, parent_id=2)
    s.add(cuenta_cli); s.flush()
    cli = _Cli(id=1, nombre="Green", organizacion_id=1, cuenta_contable_id=3)
    s.add(cli)
    s.add(_Pl(id=1, cliente_id=1, usuario_id=1, organizacion_id=1, nombre_archivo="green.xlsx"))
    s.flush()
    yield s
    s.close()


def _mov_um(s, id, monto, titular="GREEN SA 20111111119"):
    m = MovimientoBanco(id=id, extracto_id=1, monto=monto, titular=titular,
                        source="um", um_lote=1, fecha=date(2026, 5, 20))
    s.add(m); s.flush()
    return m


def _row_pl(s, id, monto):
    r = _PR(id=id, planilla_id=1, organizacion_id=1, monto=monto,
            cuit="20111111119", titular="GREEN SA", status="pendiente")
    s.add(r); s.flush()
    return r


def _total_asiento_planilla(s):
    a = s.query(_As).filter(_As.modulo == "um_reclass_planilla", _As.referencia_id == 1).all()
    assert len(a) == 1, f"esperaba 1 asiento agrupado, hay {len(a)}"
    return sum(l.debe for l in a[0].lineas)


def test_reconciliacion_asiento_agrupado_suma_total(_db_cc):
    """Bug v3.13: re-conciliar debe dejar el asiento con el total acumulado."""
    s = _db_cc
    r1 = _row_pl(s, 1, _Dec("1000"))
    r2 = _row_pl(s, 2, _Dec("2000"))
    m1 = _mov_um(s, 101, _Dec("1000"))

    # 1ª conciliación: solo está m1 → r1 ok, r2 queda pendiente
    _conciliar(s, planilla_rows=[r1, r2], movimientos=[m1],
               cliente_nombre="Green", fecha_acred_str="hoy", org_id=1, cliente_id=1)
    assert r1.status == "ok"
    assert _total_asiento_planilla(s) == _Dec("1000")

    # 2ª conciliación (re-conciliar): aparece m2 → r2 ok. El asiento debe
    # reflejar 1000 + 2000 = 3000, NO solo el delta (2000).
    m2 = _mov_um(s, 102, _Dec("2000"))
    _conciliar(s, planilla_rows=[r1, r2], movimientos=[m1, m2],
               cliente_nombre="Green", fecha_acred_str="hoy", org_id=1,
               cliente_id=1, solo_pendientes=True)
    assert r2.status == "ok"
    assert _total_asiento_planilla(s) == _Dec("3000")
