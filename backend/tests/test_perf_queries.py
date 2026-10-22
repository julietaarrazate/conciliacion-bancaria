"""Regresión de performance: cantidad de statements SQL por endpoint (anti N+1).

Usa el seed del harness (`scripts/perf/seed.py`, escala chica: 2 orgs con extractos,
planillas conciliadas, cheques y pagos con foto, arqueos, sueldos). Cada endpoint de
listado tiene un tope FIJO de statements: si alguien vuelve a serializar una relación
lazy en un loop (N+1), la cuenta crece con las filas y el test falla.

Además verifica que las versiones optimizadas devuelven lo mismo que el cálculo directo
(oráculo) y que no se mezclan datos de la otra organización.

Para medir a escala real (tabla antes/después): `cd backend && python3 -m scripts.perf.bench`.
"""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func

from app.database import get_db
from app.main import app
from app.models.cheque import Cheque
from app.models.egreso import Egreso
from app.models.extracto import MovimientoBanco
from app.models.planilla import Planilla, PlanillaRow
from scripts.perf.bench import StatementCounter, armar_entorno, limpiar_caches, token_para
from scripts.perf.seed import ESCALA_CHICA


@pytest.fixture(scope="module")
def entorno():
    engine, Session, client, ids = armar_entorno(ESCALA_CHICA)
    counter = StatementCounter(engine)
    headers = token_para(ids["principal"]["admin"])
    yield {"Session": Session, "client": client, "ids": ids, "counter": counter, "headers": headers}
    app.dependency_overrides.pop(get_db, None)


def _get(entorno, path):
    limpiar_caches()
    with entorno["counter"].medir() as c:
        r = entorno["client"].get(path, headers=entorno["headers"])
    assert r.status_code == 200, (path, r.text[:300])
    return r.json(), c.count


# Tope de statements por endpoint (2 son de auth: token revocado + usuario). Ninguno de
# estos depende de la cantidad de filas: si crece, volvió un N+1.
TOPES = {
    "/cheques": 4,
    "/cheques/deposito?fecha=2026-07-06": 3,
    "/pagos": 4,
    "/caja/arqueo/historial": 4,
    "/extractos": 5,
    "/historial/extractos": 5,
    "/historial/planillas": 5,
    "/sueldos/liquidacion?periodo=2026-08": 5,
    "/analisis/evolucion": 3,
    "/analisis/flujo-caja": 4,
    "/analisis/dashboard": 19,
}


@pytest.mark.parametrize("path,tope", sorted(TOPES.items()))
def test_statements_por_endpoint_acotados(entorno, path, tope):
    _, n = _get(entorno, path)
    assert n <= tope, f"{path}: {n} statements (tope {tope}) — ¿volvió un N+1?"


def test_listados_no_dependen_de_la_cantidad_de_filas(entorno):
    """Pedir 1 fila o todas hace la misma cantidad de queries."""
    for base in ("/cheques", "/pagos", "/caja/arqueo/historial"):
        sep = "&" if "?" in base else "?"
        _, n1 = _get(entorno, f"{base}{sep}limit=1")
        _, n_todo = _get(entorno, f"{base}{sep}limit=500")
        assert n1 == n_todo, f"{base}: {n1} statements con limit=1 vs {n_todo} con todo"


def test_cheques_y_pagos_mismo_contenido_y_solo_la_org(entorno):
    s = entorno["Session"]()
    try:
        data, _ = _get(entorno, "/cheques?limit=500")
        cheques = {c.id: c for c in s.query(Cheque).filter(Cheque.organizacion_id == 1)}
        assert data["total"] == len(cheques)
        assert {i["id"] for i in data["items"]} == set(cheques)
        for it in data["items"]:
            c = cheques[it["id"]]
            assert it["tiene_foto"] == bool(c.foto_comprobante)
            assert it["cliente_nombre"] == (c.cliente.nombre if c.cliente else None)
            assert it["portador_nombre"] == (c.portador.nombre if c.portador else None)
        assert any(i["tiene_foto"] for i in data["items"]) and not all(i["tiene_foto"] for i in data["items"])

        data, _ = _get(entorno, "/pagos?limit=500")
        egresos = {e.id: e for e in s.query(Egreso).filter(Egreso.organizacion_id == 1)}
        assert data["total"] == len(egresos)
        for it in data["items"]:
            e = egresos[it["id"]]
            assert it["tiene_foto"] == bool(e.foto_comprobante)
            assert it["foto_base64"] is None
            assert it["cliente_nombre"] == (e.cliente.nombre if e.cliente else None)
    finally:
        s.close()


def test_conteos_de_extractos_y_planillas_igual_al_calculo_directo(entorno):
    s = entorno["Session"]()
    try:
        lista, _ = _get(entorno, "/extractos")
        hist, _ = _get(entorno, "/historial/extractos")
        for it in lista["items"] + hist["items"]:
            movs = s.query(MovimientoBanco).filter(MovimientoBanco.extracto_id == it["id"]).all()
            assert it["total_movimientos"] == len(movs)
            if "acreditados" in it:
                assert it["acreditados"] == sum(1 for m in movs if m.cliente_acreditado)

        data, _ = _get(entorno, "/historial/planillas")
        assert data["total"] == s.query(Planilla).filter(Planilla.organizacion_id == 1).count()
        for it in data["items"]:
            rows = s.query(PlanillaRow).filter(PlanillaRow.planilla_id == it["id"]).all()
            st = [r.status for r in rows]
            assert it["total_filas"] == len(rows)
            assert it["acreditadas"] == st.count("ok")
            assert it["no_encontradas"] == st.count("no está")
            assert it["sin_datos"] == st.count("faltan datos")
            assert it["duplicadas"] == sum(1 for x in st if x == "duplicado" or x.startswith("acreditado"))
            esperado = sum((r.monto for r in rows if r.status == "ok"), Decimal("0"))
            assert it["monto_conciliado"] == pytest.approx(float(esperado))
    finally:
        s.close()


def test_evolucion_y_flujo_caja_igual_al_calculo_por_mes(entorno):
    """Las versiones agrupadas dan lo mismo que sumar mes por mes (el cálculo anterior)."""
    from app.services.reportes_service import (
        STATUS_OK, STATUS_PENDIENTE, _meses_atras, _suma_planilla_rows, rango_mes,
    )
    s = entorno["Session"]()
    try:
        evo, _ = _get(entorno, "/analisis/evolucion?meses=6")
        flujo, _ = _get(entorno, "/analisis/flujo-caja?meses=6")
        assert any(m["conciliado"] for m in evo["meses"]), "el seed debería tener meses con datos"
        for m, f, (a, mes) in zip(evo["meses"], flujo["meses"], _meses_atras(6)):
            desde, hasta = rango_mes(a, mes)
            conc = _suma_planilla_rows(s, 1, desde, hasta, STATUS_OK)["total"]
            pend = _suma_planilla_rows(s, 1, desde, hasta, STATUS_PENDIENTE)["total"]
            todo = _suma_planilla_rows(s, 1, desde, hasta, None)["total"]
            assert (m["anio"], m["mes"]) == (a, mes)
            assert m["conciliado"] == pytest.approx(float(round(conc, 2)))
            assert m["pendiente"] == pytest.approx(float(round(pend, 2)))
            tasa = round(conc / todo * 100, 1) if todo > 0 else 0.0
            assert m["tasa_pct"] == pytest.approx(float(tasa))

            ing = s.query(func.sum(MovimientoBanco.monto)).filter(
                MovimientoBanco.organizacion_id == 1, MovimientoBanco.fecha >= desde,
                MovimientoBanco.fecha <= hasta).scalar() or 0
            egr = s.query(func.sum(Egreso.monto)).filter(
                Egreso.organizacion_id == 1, Egreso.fecha >= desde, Egreso.fecha <= hasta).scalar() or 0
            assert f["ingresos"] == pytest.approx(float(round(ing, 2)))
            assert f["egresos"] == pytest.approx(float(round(egr, 2)))
            assert f["neto"] == pytest.approx(float(round(Decimal(str(ing)) - Decimal(str(egr)), 2)))
    finally:
        s.close()


def test_sueldos_usa_el_basico_de_la_categoria(entorno):
    data, _ = _get(entorno, "/sueldos/liquidacion?periodo=2026-08")
    assert data["detalle"], "el seed tiene empleados"
    for d in data["detalle"]:
        assert d["detalle_json"]["sueldo_basico"] == pytest.approx(950000.0)


def test_caja_historial_trae_los_egresos_de_cada_arqueo(entorno):
    s = entorno["Session"]()
    try:
        data, _ = _get(entorno, "/caja/arqueo/historial")
        for a in data:
            esperados = {e.id for e in s.query(Egreso).filter(Egreso.arqueo_id == a["id"])}
            assert {e["id"] for e in a["egresos"]} == esperados
        assert date.fromisoformat(data[0]["fecha"]) >= date.fromisoformat(data[-1]["fecha"])
    finally:
        s.close()
