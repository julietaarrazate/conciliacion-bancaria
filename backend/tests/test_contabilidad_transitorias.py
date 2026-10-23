"""Modelo de cuentas transitorias estilo Odoo (oct 2026).

La cuenta del banco (Banco Macro 1-1-1-3-1) la mueven SOLO los datos del banco
(extracto principal + UM); los módulos pegan contra las transitorias:
  2-1-1-1 No identificado  = cobros a imputar
  2-1-1-2 Pagos a imputar  = pagos a imputar
Cubre: asiento del extracto al subirlo (por día, UM afuera), pago por banco,
conciliación, "Empezar limpio" (conserva lo que no rehace), el endpoint de
corrección del histórico y el control del banco — y que nada de la org 2 se toque.

Reusa los fixtures de tests/test_contabilidad_integration.py.
"""
# Los fixtures importados (db, client) se reciben como parámetros con el mismo nombre.
# ruff: noqa: F811
import io
from datetime import date, datetime
from decimal import Decimal

import openpyxl
import pytest

from app.models.auditoria import AuditoriaLog
from app.models.cliente import Cliente
from app.models.contabilidad import Asiento, AsientoDetalle, PlanCuenta
from app.models.extracto import ExtractoBancario, MovimientoBanco
from app.models.organizacion import Organizacion
from app.models.planilla import Planilla, PlanillaRow
from app.models.user import User
from app.services import motor_contable as mc
from app.services.asientos_banco import saldo_cuenta
from app.services.auth import create_access_token, get_password_hash
from app.services.seed_contable import seed_contabilidad_org
from tests.test_contabilidad_integration import _auth, _token, client, db  # noqa: F401

BANCO = "1-1-1-3-1"
NO_ID = "2-1-1-1"
PAGOS = "2-1-1-2"
PASIVO_CTE = "2-1-0-0"


# ── Helpers ──────────────────────────────────────────────────────────────────

@pytest.fixture
def superadmin(db):
    sa = User(
        email="sa@trans.test", full_name="Superadmin", hashed_password=get_password_hash("pw"),
        organizacion_id=1, is_active=True, role="admin", is_superadmin=True,
    )
    db.add(sa)
    db.commit()
    return create_access_token({"sub": sa.email, "user_id": sa.id, "role": sa.role})


@pytest.fixture
def org2(db):
    db.add(Organizacion(id=2, nombre="Org Dos"))
    db.commit()
    seed_contabilidad_org(db, 2)
    return 2


def _cuenta(db, codigo, oid=1):
    return db.query(PlanCuenta).filter(PlanCuenta.codigo == codigo, PlanCuenta.organizacion_id == oid).first()


def _saldo(db, codigo, oid=1):
    return saldo_cuenta(db, oid, codigo)


def _asientos(db, modulo, oid=1):
    return (
        db.query(Asiento).filter(Asiento.modulo == modulo, Asiento.organizacion_id == oid)
        .order_by(Asiento.fecha, Asiento.id).all()
    )


def _balanceado(a):
    return sum(Decimal(str(ln.debe)) for ln in a.lineas) == sum(Decimal(str(ln.haber)) for ln in a.lineas)


def _xlsx(filas):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Fecha", "Titular", "Monto", "Saldo"])
    for fila in filas:
        ws.append(list(fila))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _subir(client, token, filas, org_id=1):
    r = client.post(
        f"/extractos/upload?org_id={org_id}",
        files={"file": ("extracto.xlsx", _xlsx(filas),
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _extracto(db, montos_fechas, oid=1, source="extracto", extracto=None):
    """Crea (o completa) un extracto con movimientos SIN asiento."""
    if extracto is None:
        extracto = ExtractoBancario(nombre_archivo=f"ext-{oid}.xlsx", creado_por=1, organizacion_id=oid,
                                    fecha_creacion=datetime(2026, 9, 1))
        db.add(extracto)
        db.flush()
    movs = []
    for i, (fecha, monto) in enumerate(montos_fechas, start=1):
        m = MovimientoBanco(extracto_id=extracto.id, orden=i, fecha=fecha, titular=f"Mov {i}",
                            monto=Decimal(str(monto)), source=source, organizacion_id=oid,
                            um_lote=1 if source == "um" else None)
        db.add(m)
        movs.append(m)
    db.commit()
    return extracto, movs


def _cliente(db, nombre="Cliente Norte", oid=1):
    c = Cliente(nombre=nombre, organizacion_id=oid)
    db.add(c)
    db.commit()
    return c


def _planilla_conciliada(db, cliente, extracto, mov, monto, comision=None, oid=1):
    p = Planilla(cliente_id=cliente.id, extracto_id=extracto.id, usuario_id=1, nombre_archivo="pl.xlsx",
                 organizacion_id=oid, fecha_carga=datetime(2026, 9, 2),
                 porcentaje_comision=Decimal(str(comision)) if comision else None)
    db.add(p)
    db.flush()
    db.add(PlanillaRow(planilla_id=p.id, monto=Decimal(str(monto)), titular=cliente.nombre, status="ok",
                       orden_movimiento_acreditado=mov.id, fecha_acred=mov.fecha, organizacion_id=oid))
    db.commit()
    return p


def _asiento_legacy(db, modulo, ref, fecha, lineas, oid=1):
    """Asiento como los del modelo viejo (no existe más la función que los armaba)."""
    a = Asiento(fecha=fecha, descripcion=f"legacy {modulo}", modulo=modulo, referencia_id=ref,
                organizacion_id=oid, numero_asiento=mc._next_numero_asiento(db, oid))
    db.add(a)
    db.flush()
    for codigo, debe, haber in lineas:
        db.add(AsientoDetalle(asiento_id=a.id, cuenta_id=_cuenta(db, codigo, oid).id,
                              debe=Decimal(str(debe)), haber=Decimal(str(haber))))
    db.commit()
    return a


def _estado_legacy(db, oid=1):
    """Org con historia del modelo viejo: extracto sin asientos nuevos, el
    asiento "extracto" viejo (abs() de todo en el Debe de la cuenta madre contra
    Pasivo Corriente) y una reclasificación contra Pasivo Corriente + comisión."""
    ext, (m_ing, m_eg) = _extracto(db, [(date(2026, 9, 1), 10000), (date(2026, 9, 3), -2500)], oid=oid)
    cli = _cliente(db, "Cliente Viejo", oid=oid)
    pl = _planilla_conciliada(db, cli, ext, m_ing, 10000, comision=2, oid=oid)
    cuenta_cli = mc._get_o_crear_cuenta_cliente(db, cli.id, oid)
    db.commit()
    viejo_ext = _asiento_legacy(db, "extracto", ext.id, date(2026, 10, 20),
                                [("1-1-1-3", 12500, 0), (PASIVO_CTE, 0, 12500)], oid=oid)
    viejo_rec = _asiento_legacy(db, "reclass_planilla_extracto", pl.id, date(2026, 9, 1),
                                [(PASIVO_CTE, 9800, 0), (cuenta_cli.codigo, 0, 9800)], oid=oid)
    viejo_com = _asiento_legacy(db, "reclass_planilla_extracto_comision", pl.id, date(2026, 9, 1),
                                [(PASIVO_CTE, 200, 0), ("3-1-1-0", 0, 200)], oid=oid)
    return {"extracto": ext, "planilla": pl, "cliente": cli, "cuenta_cli": cuenta_cli,
            "viejos": [viejo_ext, viejo_rec, viejo_com]}


def _foto_asientos(db, oid):
    return sorted(
        (a.id, a.modulo, a.numero_asiento, a.fecha,
         tuple(sorted((ln.cuenta_id, str(ln.debe), str(ln.haber)) for ln in a.lineas)))
        for a in db.query(Asiento).filter(Asiento.organizacion_id == oid).all()
    )


# ── Seed / helpers de cuenta ─────────────────────────────────────────────────

def test_seed_agrega_pagos_a_imputar_bajo_pasivo_a_confirmar(db):
    c = _cuenta(db, PAGOS)
    assert c is not None and c.nombre == "Pagos a imputar" and c.tipo == "pasivo"
    assert c.parent_id == _cuenta(db, "2-1-1-0").id
    assert _cuenta(db, NO_ID).nombre == "No identificado"
    assert mc.cuenta_banco_transitoria(db, 1, "ingreso").codigo == NO_ID
    assert mc.cuenta_banco_transitoria(db, 1, "egreso").codigo == PAGOS
    with pytest.raises(ValueError):
        mc.cuenta_banco_transitoria(db, 1, "otro")


def test_transitoria_de_pagos_se_crea_si_la_org_no_la_tiene(db):
    db.query(PlanCuenta).filter(PlanCuenta.codigo == PAGOS).delete()
    db.commit()
    c = mc.cuenta_banco_transitoria(db, 1, "egreso")
    assert c is not None and c.codigo == PAGOS and c.organizacion_id == 1
    assert db.query(PlanCuenta).filter(PlanCuenta.codigo == PAGOS, PlanCuenta.organizacion_id == 1).count() == 1


# ── Upload del extracto ──────────────────────────────────────────────────────

def test_upload_extracto_asiento_por_dia_con_cuentas_y_fechas_reales(client, db, superadmin):
    ext_id = _subir(client, superadmin, [
        ("2026-09-02", "Cobro B", 300, 4100),
        ("2026-09-01", "Pago proveedor", -1200, 3800),
        ("2026-09-01", "Cobro A", 5000, 5000),
    ])
    # Un UM agregado después NO entra en el asiento del extracto (lo cubre um_lote).
    ext = db.query(ExtractoBancario).get(ext_id)
    _extracto(db, [(date(2026, 9, 2), 777)], source="um", extracto=ext)
    mc.registrar_asientos_extracto(db, ext_id, None)

    asientos = _asientos(db, "extracto_banco")
    assert [a.fecha for a in asientos] == [date(2026, 9, 1), date(2026, 9, 2)]
    assert all(_balanceado(a) for a in asientos)
    banco, no_id, pagos = _cuenta(db, BANCO), _cuenta(db, NO_ID), _cuenta(db, PAGOS)

    dia1 = {(ln.cuenta_id, ln.debe, ln.haber) for ln in asientos[0].lineas}
    assert dia1 == {
        (banco.id, Decimal("5000"), Decimal("0")), (no_id.id, Decimal("0"), Decimal("5000")),
        (pagos.id, Decimal("1200"), Decimal("0")), (banco.id, Decimal("0"), Decimal("1200")),
    }
    # Saldo del banco = ingresos − egresos del extracto principal, sin el UM
    assert _saldo(db, BANCO) == Decimal("4100")
    assert _saldo(db, NO_ID) == Decimal("-5300")
    assert _saldo(db, PAGOS) == Decimal("1200")
    # La cuenta madre y Pasivo Corriente ya no se tocan
    assert _saldo(db, "1-1-1-3") == 0 and _saldo(db, PASIVO_CTE) == 0
    # Cada movimiento del extracto principal quedó marcado; el UM no
    movs = db.query(MovimientoBanco).filter(MovimientoBanco.extracto_id == ext_id).all()
    assert all(m.asiento_id for m in movs if m.source != "um")
    assert all(m.asiento_id is None for m in movs if m.source == "um")


def test_registrar_extracto_es_idempotente_y_no_registra_borrados(db):
    ext, _ = _extracto(db, [(date(2026, 9, 1), 100), (date(2026, 9, 1), -40)])
    assert mc.registrar_asientos_extracto(db, ext.id, None)
    assert mc.registrar_asientos_extracto(db, ext.id, None)
    assert len(_asientos(db, "extracto_banco")) == 1

    borrado, _ = _extracto(db, [(date(2026, 9, 5), 999)])
    borrado.deleted_at = datetime(2026, 9, 6)
    db.commit()
    mc.registrar_asientos_extracto(db, borrado.id, None)
    assert len(_asientos(db, "extracto_banco")) == 1


def test_um_egreso_va_contra_pagos_a_imputar(db):
    ext, movs = _extracto(db, [(date(2026, 9, 1), 800), (date(2026, 9, 1), -300)], source="um")
    mc.registrar_um_import(db, ext.id, 1, None, movs)
    a = _asientos(db, "um_lote")[0]
    assert _balanceado(a)
    assert _saldo(db, PAGOS) == Decimal("300") and _saldo(db, NO_ID) == Decimal("-800")
    assert _saldo(db, BANCO) == Decimal("500")


# ── Pago por banco ───────────────────────────────────────────────────────────

def test_pago_por_banco_acredita_pagos_a_imputar_y_netea_con_el_debito(client, db, superadmin):
    token = _token(db, "admin@ctb.test")
    r = client.post("/pagos", json={"tipo": "gasto", "forma_pago": "banco", "monto": "1200",
                                    "fecha": "2026-09-01", "concepto": "Alquiler"}, headers=_auth(token))
    assert r.status_code == 200, r.text
    egreso = _asientos(db, "egreso")[0]
    assert {ln.cuenta_id for ln in egreso.lineas if ln.haber > 0} == {_cuenta(db, PAGOS).id}
    assert all(ln.cuenta_id != _cuenta(db, BANCO).id for ln in egreso.lineas)
    assert _saldo(db, PAGOS) == Decimal("-1200")  # pago cargado que el banco todavía no debitó

    _subir(client, superadmin, [("2026-09-01", "Alquiler", -1200, 8800), ("2026-09-01", "Cobro", 10000, 10000)])
    assert _saldo(db, PAGOS) == 0
    assert _saldo(db, BANCO) == Decimal("8800")


def test_resolver_debito_con_pago_vinculado_netea_pagos_a_imputar(client, db, superadmin):
    """v3.32: el pago vinculado al débito queda Gasto D / 2-1-1-2 H y el
    extracto 2-1-1-2 D / Banco H → la transitoria queda en cero."""
    ext_id = _subir(client, superadmin, [("2026-09-03", "Luz", -450, 9550), ("2026-09-01", "Cobro", 10000, 10000)])
    debito = db.query(MovimientoBanco).filter(MovimientoBanco.extracto_id == ext_id,
                                              MovimientoBanco.monto < 0).one()
    token = _token(db, "admin@ctb.test")
    r = client.post("/pagos", json={"tipo": "gasto", "forma_pago": "banco", "monto": "450",
                                    "fecha": "2026-09-03", "concepto": "Luz",
                                    "movimiento_banco_id": debito.id}, headers=_auth(token))
    assert r.status_code == 200, r.text
    assert _saldo(db, PAGOS) == 0
    assert _saldo(db, "3-2-0-0") == Decimal("450")


# ── Conciliación ─────────────────────────────────────────────────────────────

def test_conciliar_movimiento_del_extracto_debita_no_identificado(db):
    from app.services.conciliacion import CONFIG_DEFAULT_ORG, conciliar_planilla

    ext, (mov,) = _extracto(db, [(date(2026, 9, 1), 98000)])
    mov.titular = "JUAN PEREZ"
    db.commit()
    mc.registrar_asientos_extracto(db, ext.id, None)
    cli = _cliente(db, "Cliente Este")
    p = Planilla(cliente_id=cli.id, extracto_id=ext.id, usuario_id=1, nombre_archivo="pl.xlsx", organizacion_id=1)
    db.add(p)
    db.flush()
    row = PlanillaRow(planilla_id=p.id, monto=Decimal("98000"), titular="Juan Perez", status="pendiente",
                      fecha=date(2026, 9, 1), organizacion_id=1)
    db.add(row)
    db.commit()

    res = conciliar_planilla(db=db, planilla_rows=[row], movimientos=[mov], cliente_nombre="Cliente Este",
                             fecha_acred_str="2026-09-01", org_config=CONFIG_DEFAULT_ORG, org_id=1,
                             cliente_id=cli.id)
    assert res["acreditadas"] == 1
    (reclass,) = _asientos(db, "reclass_planilla_principal")
    assert {ln.cuenta_id for ln in reclass.lineas if ln.debe > 0} == {_cuenta(db, NO_ID).id}
    assert _saldo(db, NO_ID) == 0
    assert _saldo(db, PASIVO_CTE) == 0
    cuenta_cli = db.query(Cliente).get(cli.id).cuenta_contable_id
    assert saldo_cuenta(db, 1, db.query(PlanCuenta).get(cuenta_cli).codigo) == Decimal("-98000")


def test_reconciliar_planilla_con_asiento_viejo_vigente_lo_actualiza_sin_duplicar(db):
    """Mientras no se corra la corrección, la reclasificación vieja (2-1-0-0)
    sigue siendo la de esa planilla: re-conciliar la actualiza, no crea otra
    (si no, el cliente quedaría acreditado dos veces)."""
    e = _estado_legacy(db)
    mc.registrar_reclasificacion_planilla(db, e["planilla"].id, 1, None, e["cliente"].id, e["cliente"].nombre,
                                          Decimal("10000"), date(2026, 9, 1), origen="extracto",
                                          comision_pct=Decimal("2"))
    assert _asientos(db, "reclass_planilla_principal") == []
    assert len(_asientos(db, "reclass_planilla_extracto")) == 1


# ── Empezar limpio (reset-y-rebuild) ─────────────────────────────────────────

def _preparar_libro_mixto(client, db, superadmin):
    _subir(client, superadmin, [("2026-09-02", "Luz", -450, 9550), ("2026-09-01", "Cobro", 10000, 10000)])
    token = _token(db, "admin@ctb.test")
    r = client.post("/pagos", json={"tipo": "gasto", "forma_pago": "banco", "monto": "450",
                                    "fecha": "2026-09-02", "concepto": "Luz"}, headers=_auth(token))
    assert r.status_code == 200, r.text
    h1, h2 = _cuenta(db, "1-1-1-2").id, _cuenta(db, "3-2-2-1").id
    r = client.post("/contabilidad/asiento-manual", json={"cuenta_debe_id": h2, "cuenta_haber_id": h1,
                                                           "monto": 75, "fecha": "2026-09-05",
                                                           "descripcion": "Ajuste"}, headers=_auth(token))
    assert r.status_code == 200, r.text


def test_reset_conserva_egresos_y_ajustes_y_renumera_sin_huecos(client, db, superadmin):
    _preparar_libro_mixto(client, db, superadmin)
    conservados_antes = {
        (a.id, tuple(sorted((ln.cuenta_id, str(ln.debe), str(ln.haber)) for ln in a.lineas)))
        for a in db.query(Asiento).filter(Asiento.modulo.in_(["egreso", "ajuste_manual"])).all()
    }
    assert len(conservados_antes) == 2

    prev = client.post("/contabilidad/reset-y-rebuild?dry_run=true", headers=_auth(superadmin)).json()
    assert prev["a_conservar"]["asientos"] == 2
    assert prev["a_conservar"]["por_modulo"] == {"ajuste_manual": 1, "egreso": 1}
    assert prev["a_borrar"]["por_modulo"] == {"extracto_banco": 2}
    assert prev["a_crear"]["dias_extracto"] == 2

    for _ in range(2):  # idempotente
        r = client.post("/contabilidad/reset-y-rebuild?dry_run=false", headers=_auth(superadmin))
        assert r.status_code == 200, r.text
        assert r.json()["conservados"] == 2
        db.expire_all()
        conservados = {
            (a.id, tuple(sorted((ln.cuenta_id, str(ln.debe), str(ln.haber)) for ln in a.lineas)))
            for a in db.query(Asiento).filter(Asiento.modulo.in_(["egreso", "ajuste_manual"])).all()
        }
        assert conservados == conservados_antes
        assert len(_asientos(db, "extracto_banco")) == 2
        nums = sorted(a.numero_asiento for a in db.query(Asiento).filter(Asiento.organizacion_id == 1))
        assert nums == list(range(1, 5))
        assert _saldo(db, PAGOS) == 0 and _saldo(db, BANCO) == Decimal("9550")
    assert db.query(AuditoriaLog).filter(AuditoriaLog.accion == "RESET_Y_REBUILD").count() == 2


def test_reset_rehace_reclasificaciones_contra_no_identificado(client, db, superadmin):
    e = _estado_legacy(db)
    r = client.post("/contabilidad/reset-y-rebuild?dry_run=false", headers=_auth(superadmin))
    assert r.status_code == 200, r.text
    db.expire_all()
    assert _asientos(db, "extracto") == [] and _asientos(db, "reclass_planilla_extracto") == []
    assert len(_asientos(db, "reclass_planilla_principal")) == 1
    assert len(_asientos(db, "reclass_planilla_principal_comision")) == 1
    assert _saldo(db, PASIVO_CTE) == 0 and _saldo(db, "1-1-1-3") == 0
    assert _saldo(db, NO_ID) == 0  # el cobro de 10000 quedó imputado (9800 cliente + 200 comisión)
    assert _saldo(db, BANCO) == Decimal("7500")
    assert saldo_cuenta(db, 1, e["cuenta_cli"].codigo) == Decimal("-9800")


def test_reset_requiere_superadmin(client, db):
    r = client.post("/contabilidad/reset-y-rebuild?dry_run=false", headers=_auth(_token(db, "admin@ctb.test")))
    assert r.status_code == 403


# ── Corrección del histórico ─────────────────────────────────────────────────

def test_correccion_dry_run_no_escribe_nada(client, db, superadmin):
    _estado_legacy(db)
    foto = _foto_asientos(db, 1)
    r = client.post("/contabilidad/corregir-asientos-banco", headers=_auth(superadmin))  # dry_run default
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["dry_run"] is True
    assert len(d["a_reversar"]) == 3
    assert d["a_crear_por_modulo"] == {
        "extracto_banco": 2, "extracto_reverso": 1,
        "reclass_planilla_extracto_comision_reverso": 1, "reclass_planilla_extracto_reverso": 1,
        "reclass_planilla_principal": 1, "reclass_planilla_principal_comision": 1,
    }
    assert d["saldos_antes"]["pasivo_corriente"]["saldo"] == "-2500.00"
    assert d["saldos_despues"]["pasivo_corriente"]["saldo"] == "0.00"
    assert d["saldos_despues"]["banco"]["saldo"] == "7500.00"
    assert d["saldos_despues"]["banco_cuenta_madre"]["saldo"] == "0.00"
    assert d["saldos_despues"]["cobros_a_imputar"]["saldo"] == "0.00"
    assert d["saldos_despues"]["pagos_a_imputar"]["saldo"] == "2500.00"  # débito sin pago cargado
    assert d["cuenta_pagos_a_imputar"]["ok"] is True
    db.expire_all()
    assert _foto_asientos(db, 1) == foto
    assert db.query(MovimientoBanco).filter(MovimientoBanco.asiento_id.isnot(None)).count() == 0
    assert db.query(AuditoriaLog).filter(AuditoriaLog.accion == "CORREGIR_ASIENTOS_BANCO").count() == 0


def test_correccion_reversa_lo_viejo_crea_lo_nuevo_y_es_idempotente(client, db, superadmin):
    e = _estado_legacy(db)
    foto_viejos = [x for x in _foto_asientos(db, 1)]
    r = client.post("/contabilidad/corregir-asientos-banco?dry_run=false", headers=_auth(superadmin))
    assert r.status_code == 200, r.text
    db.expire_all()

    # Los asientos viejos siguen ahí, sin cambios (ni montos ni número)
    foto = {x[0]: x for x in _foto_asientos(db, 1)}
    assert all(foto[v[0]] == v for v in foto_viejos)
    # Cada viejo tiene su reverso, con la fecha del original
    for viejo in e["viejos"]:
        rev = db.query(Asiento).filter(Asiento.modulo == f"{viejo.modulo}_reverso",
                                       Asiento.referencia_id == viejo.id).one()
        assert rev.fecha == viejo.fecha and _balanceado(rev)
    nuevo = _asientos(db, "reclass_planilla_principal")[0]
    assert nuevo.referencia_id == e["planilla"].id and _balanceado(nuevo)
    assert {ln.cuenta_id for ln in nuevo.lineas if ln.debe > 0} == {_cuenta(db, NO_ID).id}
    assert [a.fecha for a in _asientos(db, "extracto_banco")] == [date(2026, 9, 1), date(2026, 9, 3)]
    assert _saldo(db, PASIVO_CTE) == 0 and _saldo(db, "1-1-1-3") == 0 and _saldo(db, NO_ID) == 0
    assert _saldo(db, BANCO) == Decimal("7500")
    assert saldo_cuenta(db, 1, e["cuenta_cli"].codigo) == Decimal("-9800")  # el cliente no cambia
    assert db.query(AuditoriaLog).filter(AuditoriaLog.accion == "CORREGIR_ASIENTOS_BANCO").count() == 1
    # Los nuevos se numeran a continuación (no se renumera lo existente)
    nums = sorted(a.numero_asiento for a in db.query(Asiento).filter(Asiento.organizacion_id == 1))
    assert nums == list(range(1, len(nums) + 1))

    # Segunda corrida: nada que hacer
    foto2 = _foto_asientos(db, 1)
    r2 = client.post("/contabilidad/corregir-asientos-banco?dry_run=false", headers=_auth(superadmin))
    assert r2.status_code == 200, r2.text
    assert r2.json()["nada_que_corregir"] is True and r2.json()["a_reversar"] == []
    db.expire_all()
    assert _foto_asientos(db, 1) == foto2
    assert db.query(AuditoriaLog).filter(AuditoriaLog.accion == "CORREGIR_ASIENTOS_BANCO").count() == 1

    # Después de corregir, re-conciliar la planilla actualiza la reclasificación NUEVA
    mc.registrar_reclasificacion_planilla(db, e["planilla"].id, 1, None, e["cliente"].id, e["cliente"].nombre,
                                          Decimal("10000"), date(2026, 9, 1), origen="extracto",
                                          comision_pct=Decimal("2"))
    assert len(_asientos(db, "reclass_planilla_principal")) == 1
    assert _foto_asientos(db, 1) == foto2


def test_correccion_solo_superadmin(client, db):
    _estado_legacy(db)
    for email in ("admin@ctb.test", "op@ctb.test"):
        r = client.post("/contabilidad/corregir-asientos-banco?dry_run=true", headers=_auth(_token(db, email)))
        assert r.status_code == 403


# ── Control del banco ────────────────────────────────────────────────────────

def test_control_banco_cuadra_con_los_extractos(client, db, superadmin):
    _subir(client, superadmin, [("2026-09-02", "Luz", -450, 9550), ("2026-09-01", "Cobro", 10000, 10000)])
    d = client.get("/contabilidad/control-banco", headers=_auth(_token(db, "admin@ctb.test"))).json()
    assert d["saldo_libro_banco"] == "9550.00"
    assert d["diferencia_libro_vs_movimientos"] == "0.00"
    assert d["saldo_ultimo_extracto"] == "9550.00" and d["saldo_inicial_primer_extracto"] == "0.00"
    assert d["diferencia_libro_vs_extracto"] == "0.00"
    assert d["movimientos_extracto_sin_asiento"] == 0 and d["ok"] is True
    assert d["saldos"]["cobros_a_imputar"]["saldo"] == "-10000.00"
    assert d["saldos"]["pagos_a_imputar"]["saldo"] == "450.00"


def test_control_banco_detecta_movimientos_sin_asiento(db, client):
    _estado_legacy(db)
    d = client.get("/contabilidad/control-banco", headers=_auth(_token(db, "admin@ctb.test"))).json()
    assert d["ok"] is False and d["movimientos_extracto_sin_asiento"] == 2


# ── Multi-tenant ─────────────────────────────────────────────────────────────

def test_upload_en_org2_usa_las_cuentas_de_org2(client, db, superadmin, org2):
    _subir(client, superadmin, [("2026-09-01", "Cobro", 700, 700), ("2026-09-01", "Gasto", -100, 600)], org_id=2)
    (a,) = _asientos(db, "extracto_banco", oid=2)
    assert {ln.cuenta.organizacion_id for ln in a.lineas} == {2}
    assert _asientos(db, "extracto_banco", oid=1) == []
    assert saldo_cuenta(db, 2, BANCO) == Decimal("600")


def test_reset_y_correccion_de_org1_no_tocan_org2(client, db, superadmin, org2):
    _estado_legacy(db, oid=1)
    _estado_legacy(db, oid=2)
    foto_org2 = _foto_asientos(db, 2)
    movs_org2 = sorted((m.id, m.asiento_id) for m in db.query(MovimientoBanco).filter(MovimientoBanco.organizacion_id == 2))

    r = client.post("/contabilidad/corregir-asientos-banco?dry_run=false&org_id=1", headers=_auth(superadmin))
    assert r.status_code == 200, r.text
    r = client.post("/contabilidad/reset-y-rebuild?dry_run=false&org_id=1", headers=_auth(superadmin))
    assert r.status_code == 200, r.text
    db.expire_all()
    assert _foto_asientos(db, 2) == foto_org2
    assert sorted((m.id, m.asiento_id) for m in db.query(MovimientoBanco)
                  .filter(MovimientoBanco.organizacion_id == 2)) == movs_org2

    # Y la org 2 se corrige sola cuando se pide explícitamente para ella
    r = client.post("/contabilidad/corregir-asientos-banco?dry_run=true&org_id=2", headers=_auth(superadmin))
    assert r.status_code == 200 and r.json()["org_id"] == 2 and len(r.json()["a_reversar"]) == 3
