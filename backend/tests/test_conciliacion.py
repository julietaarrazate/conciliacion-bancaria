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


def test_buscar_match_monto_duplicado_con_dni_embebido_en_cuit_del_mov_acredita():
    """Regresión ago 2026 (caso real SMT): la planilla trae solo el DNI (8 dígitos,
    no el CUIT/CUIL completo de 11). Con monto duplicado, el DNI embebido en el
    CUIT del movimiento correcto debe desempatar — el otro candidato, sin ninguna
    coincidencia de identidad, no debe competir."""
    movimientos = [
        _mov(24675.0, titular="ING TRANSF:XIMENA NATALIA BELLOFA-27314529583", id=858,
             fecha=date(2026, 8, 7)),
        _mov(24675.0, titular="TRANSF DIAZ, FAB 23419881279 VAR VARIOS VARIO", id=87,
             fecha=date(2026, 8, 19)),
    ]
    resultado, status = buscar_match(
        monto=24675.0,
        cuit_planilla="41988127",   # DNI, no CUIT completo
        titular_planilla="Fabio Joel Diaz",
        referencia_planilla=None,
        fecha_planilla=date(2026, 8, 19),
        movimientos=movimientos,
        procesados=set(),
        org_config=CONFIG_DEFAULT_ORG,
    )
    assert resultado is not None, "el DNI embebido en el CUIT del movimiento debe alcanzar para acreditar"
    assert resultado.id == 87
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


# ── Tests: diagnóstico read-only de conciliación ──────────────────────────────

from types import SimpleNamespace
from app.services.conciliacion import diagnostico_conciliacion


def _row_diag(monto, cuit=None, titular=None, fecha=None, status="pendiente"):
    return SimpleNamespace(monto=monto, cuit=cuit, titular=titular, fecha=fecha, status=status)


def test_diagnostico_banco_sin_identidad():
    """Banco Comercio: todos los créditos genéricos → banco_trae_identidad False."""
    movs = [
        _mov(5000.0, titular="CREDITO POR CREDIN", id=1),
        _mov(3000.0, titular="CREDITO POR TRANSFERENCIA", id=2),
        _mov(2000.0, titular="CREDITO POR CREDIN", id=3),
    ]
    rows = [_row_diag(5000.0)]
    d = diagnostico_conciliacion(rows, movs)
    assert d["banco_trae_identidad"] is False


def test_diagnostico_banco_con_identidad():
    """Titulares con CUIT o nombre y apellido → banco_trae_identidad True."""
    movs = [
        _mov(5000.0, titular="GARCIA MARIA LAURA", id=1),
        _mov(3000.0, titular="EMPRESA SA 20111111110", id=2),
        _mov(2000.0, titular="RODRIGUEZ JUAN", id=3),
    ]
    d = diagnostico_conciliacion([_row_diag(5000.0)], movs)
    assert d["banco_trae_identidad"] is True


def test_diagnostico_banco_sin_movimientos_es_none():
    d = diagnostico_conciliacion([_row_diag(5000.0)], [])
    assert d["banco_trae_identidad"] is None


def test_diagnostico_cobertura_montos():
    """Planilla con 5 montos, extracto tiene 3 de esos → {en_extracto:3, total:5}."""
    movs = [
        _mov(1000.0, titular="X", id=1),
        _mov(2000.0, titular="X", id=2),
        _mov(3000.0, titular="X", id=3),
    ]
    rows = [
        _row_diag(1000.0),
        _row_diag(2000.0),
        _row_diag(3000.0),
        _row_diag(4000.0),
        _row_diag(5000.0),
    ]
    d = diagnostico_conciliacion(rows, movs)
    assert d["cobertura_montos"] == {"en_extracto": 3, "total": 5}


def test_diagnostico_cobertura_tolerancia_centavos():
    """Tolerancia de 1 peso: 1000.50 en planilla matchea 1000.00 en extracto."""
    movs = [_mov(1000.00, titular="X", id=1)]
    rows = [_row_diag(1000.50)]
    d = diagnostico_conciliacion(rows, movs)
    assert d["cobertura_montos"] == {"en_extracto": 1, "total": 1}


def test_diagnostico_fechas_no_solapan():
    """Planilla junio 3-5, extracto junio 17-24 → solapan_fechas False."""
    rows = [
        _row_diag(1000.0, fecha=date(2026, 6, 3)),
        _row_diag(2000.0, fecha=date(2026, 6, 5)),
    ]
    movs = [
        _mov(9000.0, titular="X", id=1, fecha=date(2026, 6, 17)),
        _mov(8000.0, titular="X", id=2, fecha=date(2026, 6, 24)),
    ]
    d = diagnostico_conciliacion(rows, movs)
    assert d["solapan_fechas"] is False
    assert d["periodo_planilla"] == {"desde": date(2026, 6, 3), "hasta": date(2026, 6, 5)}
    assert d["periodo_extracto"] == {"desde": date(2026, 6, 17), "hasta": date(2026, 6, 24)}


def test_diagnostico_fechas_solapan():
    rows = [_row_diag(1000.0, fecha=date(2026, 6, 10)), _row_diag(2000.0, fecha=date(2026, 6, 20))]
    movs = [_mov(9000.0, titular="X", id=1, fecha=date(2026, 6, 15))]
    d = diagnostico_conciliacion(rows, movs)
    assert d["solapan_fechas"] is True


def test_diagnostico_fechas_faltantes_no_alarma():
    """Si falta algún extremo de fecha → solapan_fechas True (no alarmar de más)."""
    rows = [_row_diag(1000.0, fecha=None)]
    movs = [_mov(1000.0, titular="X", id=1, fecha=date(2026, 6, 15))]
    d = diagnostico_conciliacion(rows, movs)
    assert d["solapan_fechas"] is True


def test_diagnostico_no_muta_rows_ni_movimientos():
    """READ-ONLY: no cambia status de rows ni ningún campo de movimientos."""
    rows = [_row_diag(5000.0, status="pendiente"), _row_diag(3000.0, status="ok")]
    movs = [_mov(5000.0, titular="GARCIA MARIA", cliente_acreditado="Green", id=1)]
    d = diagnostico_conciliacion(rows, movs)
    assert rows[0].status == "pendiente"
    assert rows[1].status == "ok"
    assert movs[0].cliente_acreditado == "Green"
    assert movs[0].titular == "GARCIA MARIA"
    # shape completo
    assert set(d.keys()) == {
        "banco_trae_identidad", "cobertura_montos",
        "periodo_planilla", "periodo_extracto", "solapan_fechas",
    }
