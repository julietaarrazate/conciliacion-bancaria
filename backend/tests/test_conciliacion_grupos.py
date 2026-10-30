"""Conciliación en grupos (oct 2026): un movimiento ↔ varias filas (A) y varios
movimientos ↔ una fila (B), más la marca de calidad del match ("coincidencia").

Cubre: búsqueda acotada (subset-sum), sugerencias A y B, ambigüedad → solo
sugerencia, auto-confirmación opt-in con CUIT fuerte, confirmar / armar a mano /
deshacer por API, contabilidad por origen (extracto vs UM) y partida doble,
"Empezar limpio", permisos y aislamiento entre organizaciones.
"""
from datetime import date, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.cliente import Cliente
from app.models.conciliacion_grupo import ConciliacionGrupo
from app.models.contabilidad import Asiento
from app.models.extracto import ExtractoBancario, MovimientoBanco
from app.models.organizacion import Organizacion
from app.models.planilla import Planilla, PlanillaRow
from app.models.user import User
from app.services import conciliacion_grupos as cg
from app.services.auth import create_access_token, get_password_hash
from app.services.conciliacion import CONFIG_DEFAULT_ORG, coincidencia_match
from app.services.seed_contable import seed_contabilidad_org

F = date(2026, 10, 10)


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    s = sessionmaker(bind=engine)()
    s.add_all([Organizacion(id=1, nombre="Org1"), Organizacion(id=2, nombre="Org2")])
    s.commit()
    seed_contabilidad_org(s, 1)
    seed_contabilidad_org(s, 2)
    for email, org, rol in (("admin1@g.test", 1, "admin"), ("rev1@g.test", 1, "revisor"),
                            ("admin2@g.test", 2, "admin")):
        s.add(User(email=email, full_name=email, hashed_password=get_password_hash("pw123456"),
                   organizacion_id=org, is_active=True, role=rol, is_superadmin=False))
    s.commit()
    yield s
    s.close()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app, raise_server_exceptions=True)
    app.dependency_overrides.pop(get_db, None)


def _auth(db, email):
    u = db.query(User).filter(User.email == email).first()
    return {"Authorization": f"Bearer {create_access_token({'sub': u.email, 'user_id': u.id, 'role': u.role})}"}


def _config(db, oid=1, **extra):
    org = db.query(Organizacion).get(oid)
    org.configuracion = {**CONFIG_DEFAULT_ORG, **extra}
    db.commit()


def _escenario(db, movs, filas, oid=1, cliente="Cliente Grupo"):
    """movs: [(monto, titular, fecha, source)] · filas: [(monto, cuit, titular, fecha)]."""
    ext = ExtractoBancario(nombre_archivo=f"ext{oid}.xlsx", creado_por=1, organizacion_id=oid,
                           fecha_creacion=datetime(2026, 10, 1))
    db.add(ext)
    db.flush()
    ms = []
    for i, (monto, titular, fecha, source) in enumerate(movs, start=1):
        m = MovimientoBanco(extracto_id=ext.id, orden=i, fecha=fecha, titular=titular, monto=Decimal(str(monto)),
                            source=source, organizacion_id=oid)
        db.add(m)
        ms.append(m)
    cli = Cliente(nombre=cliente, organizacion_id=oid)
    db.add(cli)
    db.flush()
    p = Planilla(cliente_id=cli.id, extracto_id=ext.id, usuario_id=1, nombre_archivo="pl.xlsx",
                 organizacion_id=oid, fecha_carga=datetime(2026, 10, 12))
    db.add(p)
    db.flush()
    rs = []
    for monto, cuit, titular, fecha in filas:
        r = PlanillaRow(planilla_id=p.id, monto=Decimal(str(monto)), cuit=cuit, titular=titular, fecha=fecha,
                        status="pendiente", organizacion_id=oid)
        db.add(r)
        rs.append(r)
    db.commit()
    return p, ms, rs


def _conciliar(client, db, p, email="admin1@g.test"):
    r = client.post(f"/planillas/{p.id}/conciliar", params={"fecha_acred": "2026-10-11"}, headers=_auth(db, email))
    assert r.status_code == 200, r.text
    db.expire_all()
    return r.json()


def _asientos(db, modulo, ref, oid=1):
    return db.query(Asiento).filter(Asiento.modulo == modulo, Asiento.referencia_id == ref,
                                    Asiento.organizacion_id == oid).all()


def _balanceado(a):
    return sum(Decimal(str(ln.debe)) for ln in a.lineas) == sum(Decimal(str(ln.haber)) for ln in a.lineas)


def _total_debe(a):
    return sum(Decimal(str(ln.debe)) for ln in a.lineas)


def _grupos(db, p):
    return db.query(ConciliacionGrupo).filter(ConciliacionGrupo.planilla_id == p.id).order_by(ConciliacionGrupo.id).all()


# ── 1. Búsqueda acotada ──────────────────────────────────────────────────────

def _c(*montos):
    return [(f"x{i}", Decimal(str(m)), 1) for i, m in enumerate(montos)]


def test_subset_sum_encuentra_la_combinacion():
    sols, cortado = cg.buscar_subconjuntos(Decimal("3000"), _c(1000, 2000, 500), Decimal("0.01"))
    assert sols == [(0, 1)] and not cortado


def test_subset_sum_varias_combinaciones():
    sols, _ = cg.buscar_subconjuntos(Decimal("3000"), _c(1000, 1000, 2000), Decimal("0.01"))
    assert sorted(sols) == [(0, 2), (1, 2)]


def test_subset_sum_respeta_el_maximo_de_items():
    # 700 = 7 × 100 necesita 7 filas: más que el máximo (6) → no hay grupo
    sols, _ = cg.buscar_subconjuntos(Decimal("700"), _c(*([100] * 7)), Decimal("0.01"), max_items=6)
    assert sols == []
    sols, _ = cg.buscar_subconjuntos(Decimal("600"), _c(*([100] * 6)), Decimal("0.01"), max_items=6)
    assert sols == [(0, 1, 2, 3, 4, 5)]


def test_subset_sum_corta_por_presupuesto():
    pres = cg._Presupuesto(5)
    sols, cortado = cg.buscar_subconjuntos(Decimal("200.5"), _c(*range(1, 21)), Decimal("0.01"), presupuesto=pres)
    assert cortado and pres.agotado


def test_subset_sum_un_solo_item_no_es_grupo():
    sols, _ = cg.buscar_subconjuntos(Decimal("3000"), _c(3000, 1000), Decimal("0.01"))
    assert sols == []


# ── 2. Sugerencias automáticas ───────────────────────────────────────────────

def test_a_un_movimiento_varias_filas_queda_sugerido(client, db):
    p, (mov,), rows = _escenario(
        db, [(3000, "TRANSF JUAN PEREZ 20123456786", F, "extracto")],
        [(1000, None, "Juan Perez", F), (2000, None, "Juan Perez", F), (777, None, "Otro", F)],
    )
    res = _conciliar(client, db, p)
    assert res["grupos_sugeridos"] == 1 and res["grupos_confirmados"] == 0
    (g,) = _grupos(db, p)
    assert g.estado == "sugerido" and g.diferencia == 0
    assert [r.status for r in rows] == ["SUGERIDO_GRUPO", "SUGERIDO_GRUPO", "no está"]
    assert mov.cliente_acreditado is None  # sugerido: el banco no se toca
    assert _asientos(db, "reclass_planilla_principal", p.id) == []


def test_b_una_fila_varios_movimientos_queda_sugerido(client, db):
    p, movs, (row,) = _escenario(
        db, [(2000, "JUAN PEREZ", F, "extracto"), (3000, "JUAN PEREZ", F, "extracto"), (900, "OTRO", F, "extracto")],
        [(5000, None, "Juan Perez", F)],
    )
    res = _conciliar(client, db, p)
    assert res["grupos_sugeridos"] == 1
    (g,) = _grupos(db, p)
    assert {it.movimiento_id for it in g.items if it.movimiento_id} == {movs[0].id, movs[1].id}
    assert row.status == "SUGERIDO_GRUPO"


def test_sin_identidad_ni_fecha_no_sugiere(client, db):
    p, _, rows = _escenario(
        db, [(3000, "CREDITO POR TRANSFERENCIA", F, "extracto")],
        [(1000, None, None, None), (2000, None, None, None)],
    )
    assert _conciliar(client, db, p)["grupos_sugeridos"] == 0
    assert all(r.status == "no está" for r in rows)


def test_fecha_fuera_de_la_ventana_poda_aunque_coincida_el_titular(client, db):
    p, _, _ = _escenario(
        db, [(3000, "JUAN PEREZ", F, "extracto")],
        [(1000, None, "Juan Perez", date(2026, 9, 1)), (2000, None, "Juan Perez", F)],
    )
    assert _conciliar(client, db, p)["grupos_sugeridos"] == 0


def test_solo_fecha_cercana_alcanza_como_apoyo(client, db):
    p, _, _ = _escenario(
        db, [(3000, "CREDITO POR TRANSFERENCIA", F, "extracto")],
        [(1000, None, None, F), (2000, None, None, date(2026, 10, 12))],
    )
    assert _conciliar(client, db, p)["grupos_sugeridos"] == 1


def test_mas_de_seis_filas_no_se_agrupan(client, db):
    p, _, _ = _escenario(
        db, [(700, "JUAN PEREZ", F, "extracto")], [(100, None, "Juan Perez", F)] * 7,
    )
    assert _conciliar(client, db, p)["grupos_sugeridos"] == 0


def test_empate_ambiguo_no_sugiere_nada(client, db):
    # {1000a, 2000} y {1000b, 2000} tienen el mismo apoyo → no se adivina
    p, _, _ = _escenario(
        db, [(3000, "JUAN PEREZ", F, "extracto")],
        [(1000, None, "Juan Perez", F), (1000, None, "Juan Perez", F), (2000, None, "Juan Perez", F)],
    )
    assert _conciliar(client, db, p)["grupos_sugeridos"] == 0
    assert _grupos(db, p) == []


def test_ambiguo_con_mejor_opcion_se_sugiere_pero_nunca_se_autoconfirma(client, db):
    _config(db, auto_confirmar_grupos=True)
    cuit = "20123456786"
    p, (mov,), rows = _escenario(
        db, [(3000, f"TRANSF JUAN PEREZ {cuit}", F, "extracto")],
        [(1000, cuit, "Juan Perez", F), (1000, None, None, date(2026, 10, 14)), (2000, cuit, "Juan Perez", F)],
    )
    res = _conciliar(client, db, p)
    assert res["grupos_sugeridos"] == 1 and res["grupos_confirmados"] == 0
    (g,) = _grupos(db, p)
    assert g.ambiguo is True and g.estado == "sugerido"
    filas_g = {it.planilla_row_id for it in g.items if it.planilla_row_id}
    assert filas_g == {rows[0].id, rows[2].id}  # la del CUIT, no la que solo tiene fecha
    assert mov.cliente_acreditado is None


def test_autoconfirma_solo_con_flag_cuit_fuerte_y_combinacion_unica(client, db):
    _config(db, auto_confirmar_grupos=True)
    cuit = "20123456786"
    p, (mov,), rows = _escenario(
        db, [(3000, f"TRANSF JUAN PEREZ {cuit}", F, "extracto")],
        [(1000, cuit, "Juan Perez", F), (2000, cuit, "Juan Perez", F)],
    )
    res = _conciliar(client, db, p)
    assert res["grupos_confirmados"] == 1 and res["acreditadas"] == 2 and res["no_encontradas"] == 0
    (g,) = _grupos(db, p)
    assert g.estado == "confirmado"
    assert [r.status for r in rows] == ["ok", "ok"]
    assert all(r.orden_movimiento_acreditado is None for r in rows)
    assert mov.cliente_acreditado == "Cliente Grupo"
    (a,) = _asientos(db, "reclass_planilla_principal", p.id)
    assert _balanceado(a) and _total_debe(a) == Decimal("3000")


def test_sin_flag_la_identidad_fuerte_queda_solo_sugerida(client, db):
    cuit = "20123456786"
    p, (mov,), _ = _escenario(
        db, [(3000, f"TRANSF {cuit}", F, "extracto")],
        [(1000, cuit, None, F), (2000, cuit, None, F)],
    )
    res = _conciliar(client, db, p)
    assert res["grupos_sugeridos"] == 1 and res["grupos_confirmados"] == 0
    assert mov.cliente_acreditado is None


def test_flag_sin_cuit_fuerte_no_autoconfirma(client, db):
    _config(db, auto_confirmar_grupos=True)
    p, _, _ = _escenario(
        db, [(3000, "JUAN PEREZ", F, "extracto")],
        [(1000, None, "Juan Perez", F), (2000, None, "Juan Perez", F)],
    )
    assert _conciliar(client, db, p)["grupos_confirmados"] == 0


def test_el_1a1_tiene_prioridad_sobre_los_grupos(client, db):
    # La fila de 3000 matchea 1:1; las de 1000 + 2000 no tienen otro movimiento → no hay grupo
    p, _, rows = _escenario(
        db, [(3000, "JUAN PEREZ", F, "extracto")],
        [(3000, None, "Juan Perez", F), (1000, None, "Juan Perez", F), (2000, None, "Juan Perez", F)],
    )
    res = _conciliar(client, db, p)
    assert rows[0].status == "ok" and res["grupos_sugeridos"] == 0


def test_reconciliar_recalcula_la_sugerencia_sin_duplicarla(client, db):
    p, _, _ = _escenario(
        db, [(3000, "JUAN PEREZ", F, "extracto")],
        [(1000, None, "Juan Perez", F), (2000, None, "Juan Perez", F)],
    )
    _conciliar(client, db, p)
    _conciliar(client, db, p)
    assert [g.estado for g in _grupos(db, p)] == ["sugerido"]


# ── 3. Confirmar / armar a mano / deshacer ───────────────────────────────────

def test_confirmar_sugerido_acredita_y_contabiliza(client, db):
    p, (mov,), rows = _escenario(
        db, [(3000, "JUAN PEREZ", F, "extracto")],
        [(1000, None, "Juan Perez", F), (2000, None, "Juan Perez", F)],
    )
    _conciliar(client, db, p)
    (g,) = _grupos(db, p)
    r = client.post(f"/planillas/grupos/{g.id}/confirmar", headers=_auth(db, "admin1@g.test"))
    assert r.status_code == 200, r.text
    db.expire_all()
    assert g.estado == "confirmado" and [x.status for x in rows] == ["ok", "ok"]
    assert mov.cliente_acreditado == "Cliente Grupo"
    (a,) = _asientos(db, "reclass_planilla_principal", p.id)
    assert _balanceado(a) and _total_debe(a) == Decimal("3000")
    # Re-conciliar respeta el grupo confirmado (no re-matchea ni lo duplica)
    res = _conciliar(client, db, p)
    assert res["acreditadas"] == 2
    assert [x.status for x in rows] == ["ok", "ok"]
    (a,) = _asientos(db, "reclass_planilla_principal", p.id)
    assert _total_debe(a) == Decimal("3000")


def test_confirmar_dos_veces_da_409(client, db):
    p, _, _ = _escenario(db, [(3000, "JUAN PEREZ", F, "extracto")],
                         [(1000, None, "Juan Perez", F), (2000, None, "Juan Perez", F)])
    _conciliar(client, db, p)
    (g,) = _grupos(db, p)
    h = _auth(db, "admin1@g.test")
    assert client.post(f"/planillas/grupos/{g.id}/confirmar", headers=h).status_code == 200
    assert client.post(f"/planillas/grupos/{g.id}/confirmar", headers=h).status_code == 409


def test_descartar_sugerido_no_vuelve_a_sugerirse(client, db):
    p, _, rows = _escenario(db, [(3000, "JUAN PEREZ", F, "extracto")],
                            [(1000, None, "Juan Perez", F), (2000, None, "Juan Perez", F)])
    _conciliar(client, db, p)
    (g,) = _grupos(db, p)
    r = client.post(f"/planillas/grupos/{g.id}/deshacer", headers=_auth(db, "admin1@g.test"))
    assert r.status_code == 200 and r.json()["estado"] == "descartado"
    db.expire_all()
    assert [x.status for x in rows] == ["pendiente", "pendiente"]
    assert _conciliar(client, db, p)["grupos_sugeridos"] == 0
    assert [g.estado for g in _grupos(db, p)] == ["descartado"]


def test_grupo_manual_que_cuadra(client, db):
    p, (mov, _otro), rows = _escenario(
        db, [(3000, "CREDITO POR TRANSFERENCIA", F, "extracto"), (50, "X", F, "extracto")],
        [(1000, None, None, None), (2000, None, None, None)],
    )
    r = client.post(f"/planillas/{p.id}/grupos", json={"row_ids": [x.id for x in rows], "movimiento_ids": [mov.id]},
                    headers=_auth(db, "admin1@g.test"))
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["estado"] == "confirmado" and data["origen"] == "manual" and Decimal(str(data["diferencia"])) == 0
    db.expire_all()
    assert [x.status for x in rows] == ["ok", "ok"]
    (a,) = _asientos(db, "reclass_planilla_principal", p.id)
    assert _balanceado(a) and _total_debe(a) == Decimal("3000")


def test_grupo_manual_con_diferencia_requiere_confirmacion_explicita(client, db):
    p, (mov,), rows = _escenario(
        db, [(2990, "CREDITO", F, "extracto")], [(1000, None, None, None), (2000, None, None, None)],
    )
    h = _auth(db, "admin1@g.test")
    body = {"row_ids": [x.id for x in rows], "movimiento_ids": [mov.id]}
    r = client.post(f"/planillas/{p.id}/grupos", json=body, headers=h)
    assert r.status_code == 400 and "No cuadra" in r.json()["detail"]
    assert _grupos(db, p) == []
    r = client.post(f"/planillas/{p.id}/grupos", json={**body, "con_diferencia": True}, headers=h)
    assert r.status_code == 200, r.text
    assert Decimal(str(r.json()["diferencia"])) == Decimal("-10")
    db.expire_all()
    assert [x.status for x in rows] == ["CONCILIADO_CON_DIFERENCIA"] * 2
    # La reclasificación cancela lo que entró al banco (2990), no lo declarado (3000)
    (a,) = _asientos(db, "reclass_planilla_principal", p.id)
    assert _balanceado(a) and _total_debe(a) == Decimal("2990")


def test_grupo_manual_valida_la_forma(client, db):
    p, movs, rows = _escenario(
        db, [(1000, "A", F, "extracto"), (2000, "B", F, "extracto")],
        [(1000, None, None, None), (2000, None, None, None)],
    )
    h = _auth(db, "admin1@g.test")
    # varias filas contra varios movimientos
    r = client.post(f"/planillas/{p.id}/grupos",
                    json={"row_ids": [x.id for x in rows], "movimiento_ids": [m.id for m in movs]}, headers=h)
    assert r.status_code == 400
    # 1:1 → usar asignar
    r = client.post(f"/planillas/{p.id}/grupos", json={"row_ids": [rows[0].id], "movimiento_ids": [movs[0].id]}, headers=h)
    assert r.status_code == 400


def test_deshacer_grupo_confirmado_libera_y_anula_el_asiento(client, db):
    p, (mov,), rows = _escenario(db, [(3000, "CREDITO", F, "extracto")],
                                 [(1000, None, None, None), (2000, None, None, None)])
    h = _auth(db, "admin1@g.test")
    gid = client.post(f"/planillas/{p.id}/grupos", json={"row_ids": [x.id for x in rows], "movimiento_ids": [mov.id]},
                      headers=h).json()["id"]
    assert len(_asientos(db, "reclass_planilla_principal", p.id)) == 1
    r = client.post(f"/planillas/grupos/{gid}/deshacer", headers=h)
    assert r.status_code == 200, r.text
    db.expire_all()
    assert [x.status for x in rows] == ["pendiente", "pendiente"]
    assert mov.cliente_acreditado is None and mov.fecha_acred is None
    assert _asientos(db, "reclass_planilla_principal", p.id) == []
    # Ya deshecho → 409
    assert client.post(f"/planillas/grupos/{gid}/deshacer", headers=h).status_code == 409


def test_fila_en_grupo_no_se_edita_suelta(client, db):
    p, (mov,), rows = _escenario(db, [(3000, "CREDITO", F, "extracto")],
                                 [(1000, None, None, None), (2000, None, None, None)])
    h = _auth(db, "admin1@g.test")
    client.post(f"/planillas/{p.id}/grupos", json={"row_ids": [x.id for x in rows], "movimiento_ids": [mov.id]}, headers=h)
    assert client.patch(f"/planillas/rows/{rows[0].id}", json={"status": "no está"}, headers=h).status_code == 409
    assert client.delete(f"/planillas/rows/{rows[0].id}", headers=h).status_code == 409


def test_movimiento_en_grupo_no_se_reusa(client, db):
    p, (mov,), rows = _escenario(db, [(3000, "CREDITO", F, "extracto")],
                                 [(1000, None, None, None), (2000, None, None, None), (500, None, None, None)])
    h = _auth(db, "admin1@g.test")
    assert client.post(f"/planillas/{p.id}/grupos", json={"row_ids": [rows[0].id, rows[1].id], "movimiento_ids": [mov.id]},
                       headers=h).status_code == 200
    r = client.get(f"/planillas/{p.id}/movimientos-libres", headers=h)
    assert r.status_code == 200 and r.json()["movimientos"] == []
    r = client.post(f"/planillas/{p.id}/grupos", json={"row_ids": [rows[2].id, rows[0].id], "movimiento_ids": [mov.id]},
                    headers=h)
    assert r.status_code == 409


# ── 4. Contabilidad: orígenes mezclados y "Empezar limpio" ───────────────────

def test_grupo_que_mezcla_extracto_y_um_reparte_por_origen(client, db):
    p, (m_ext, m_um, m_11), rows = _escenario(
        db, [(2000, "CREDITO", F, "extracto"), (3000, "CREDITO", F, "um"), (700, "JUAN PEREZ", F, "extracto")],
        [(5000, None, None, None), (700, None, "Juan Perez", F)],
    )
    h = _auth(db, "admin1@g.test")
    _conciliar(client, db, p)  # la fila de 700 va 1:1 contra el extracto
    assert rows[1].status == "ok"
    r = client.post(f"/planillas/{p.id}/grupos", json={"row_ids": [rows[0].id], "movimiento_ids": [m_ext.id, m_um.id]},
                    headers=h)
    assert r.status_code == 200, r.text
    (principal,) = _asientos(db, "reclass_planilla_principal", p.id)
    (um,) = _asientos(db, "um_reclass_planilla", p.id)
    assert _balanceado(principal) and _balanceado(um)
    assert _total_debe(principal) == Decimal("2700")  # 2000 del grupo + 700 del 1:1
    assert _total_debe(um) == Decimal("3000")
    db.expire_all()
    assert rows[0].monto_acreditado == Decimal("5000")


def test_grupo_con_comision_netea_por_bucket(client, db):
    p, (mov,), rows = _escenario(db, [(3000, "CREDITO", F, "extracto")],
                                 [(1000, None, None, None), (2000, None, None, None)])
    p.porcentaje_comision = Decimal("2")
    db.commit()
    client.post(f"/planillas/{p.id}/grupos", json={"row_ids": [x.id for x in rows], "movimiento_ids": [mov.id]},
                headers=_auth(db, "admin1@g.test"))
    (a,) = _asientos(db, "reclass_planilla_principal", p.id)
    (com,) = _asientos(db, "reclass_planilla_principal_comision", p.id)
    assert _total_debe(a) == Decimal("2940") and _total_debe(com) == Decimal("60")
    assert _balanceado(a) and _balanceado(com)


def test_empezar_limpio_incluye_los_grupos(client, db):
    from app.services.asientos_banco import _buckets_reclass

    p, (mov,), rows = _escenario(db, [(3000, "CREDITO", F, "um")],
                                 [(1000, None, None, None), (2000, None, None, None)])
    client.post(f"/planillas/{p.id}/grupos", json={"row_ids": [x.id for x in rows], "movimiento_ids": [mov.id]},
                headers=_auth(db, "admin1@g.test"))
    buckets = _buckets_reclass(db, 1, [p.extracto_id])
    assert buckets[(p.id, "um")]["grupos"] == Decimal("3000")


# ── 5. Permisos y aislamiento ────────────────────────────────────────────────

def test_revisor_no_puede_armar_confirmar_ni_deshacer(client, db):
    p, (mov,), rows = _escenario(db, [(3000, "JUAN PEREZ", F, "extracto")],
                                 [(1000, None, "Juan Perez", F), (2000, None, "Juan Perez", F)])
    _conciliar(client, db, p)
    (g,) = _grupos(db, p)
    h = _auth(db, "rev1@g.test")
    assert client.post(f"/planillas/grupos/{g.id}/confirmar", headers=h).status_code == 403
    assert client.post(f"/planillas/grupos/{g.id}/deshacer", headers=h).status_code == 403
    assert client.post(f"/planillas/{p.id}/grupos", json={"row_ids": [rows[0].id], "movimiento_ids": [mov.id]},
                       headers=h).status_code == 403
    # Leer sí puede
    assert client.get(f"/planillas/{p.id}/movimientos-libres", headers=h).status_code == 200


def test_otra_org_no_ve_ni_toca_los_grupos(client, db):
    p, (mov,), rows = _escenario(db, [(3000, "JUAN PEREZ", F, "extracto")],
                                 [(1000, None, "Juan Perez", F), (2000, None, "Juan Perez", F)])
    _conciliar(client, db, p)
    (g,) = _grupos(db, p)
    h2 = _auth(db, "admin2@g.test")
    assert client.post(f"/planillas/grupos/{g.id}/confirmar", headers=h2).status_code == 404
    assert client.post(f"/planillas/grupos/{g.id}/deshacer", headers=h2).status_code == 404
    assert client.get(f"/planillas/{p.id}/movimientos-libres", headers=h2).status_code == 404
    assert client.post(f"/planillas/{p.id}/grupos", json={"row_ids": [r.id for r in rows], "movimiento_ids": [mov.id]},
                       headers=h2).status_code == 404
    db.expire_all()
    assert g.estado == "sugerido"


def test_no_se_agrupa_con_un_movimiento_de_otra_org(client, db):
    p, _, rows = _escenario(db, [(10, "X", F, "extracto")], [(1000, None, None, None), (2000, None, None, None)])
    _p2, (mov_org2,), _ = _escenario(db, [(3000, "CREDITO", F, "extracto")], [(1, None, None, None)], oid=2,
                                     cliente="Cliente Org2")
    r = client.post(f"/planillas/{p.id}/grupos", json={"row_ids": [x.id for x in rows], "movimiento_ids": [mov_org2.id]},
                    headers=_auth(db, "admin1@g.test"))
    assert r.status_code == 404
    db.expire_all()
    assert mov_org2.cliente_acreditado is None


# ── 6. Coincidencia (calidad del match) ──────────────────────────────────────

class _R:
    def __init__(self, cuit=None, titular=None, referencia=None):
        self.cuit, self.titular, self.referencia = cuit, titular, referencia


class _M:
    def __init__(self, titular):
        self.titular, self.fecha = titular, None


def test_coincidencia_cuit_distinto_caso_real():
    # Caso real: la fila dice 20123456786 y el movimiento trae 20123456794 → matcheó solo por monto
    assert coincidencia_match(_R("20123456786", "Juan Perez"), _M("TRANSF 20123456794 JUAN PEREZ")) == "cuit_distinto"
    assert coincidencia_match(_R("20-12345678-6"), _M("TRANSF 20-12345679-4")) == "cuit_distinto"


def test_coincidencia_cuit_titular_y_solo_monto():
    assert coincidencia_match(_R("20123456786"), _M("TRANSF 20-12345678-6")) == "cuit"
    assert coincidencia_match(_R(None, "Juan Perez"), _M("TRANSF JUAN PEREZ")) == "titular"
    assert coincidencia_match(_R(None, "Juan Perez"), _M("CREDITO POR TRANSFERENCIA")) == "solo_monto"
    # La fila tiene CUIT pero el banco no trae ninguno: no es "distinto", se mira el resto
    assert coincidencia_match(_R("20123456786", "Juan Perez"), _M("JUAN PEREZ")) == "titular"
    assert coincidencia_match(_R("20123456786"), _M("CREDITO")) == "solo_monto"
    assert coincidencia_match(_R("20123456786"), None) is None


def test_coincidencia_en_grupo_gana_el_aviso():
    fila = _R("20123456786")
    assert coincidencia_match(fila, [_M("TRANSF 20123456786"), _M("TRANSF 20123456786")]) == "cuit"
    assert coincidencia_match(fila, [_M("TRANSF 20123456786"), _M("TRANSF 20123456794")]) == "cuit_distinto"


def test_detalle_y_export_exponen_coincidencia_sin_cambiar_el_match(client, db):
    from app.routers.planillas import _build_planilla_export_data

    p, (mov,), (row,) = _escenario(
        db, [(98765, "TRANSF 20123456794 JUAN PEREZ", F, "extracto")], [(98765, "20123456786", "Juan Perez", F)],
    )
    _conciliar(client, db, p)
    assert row.status == "ok"  # el match por monto único no cambia
    r = client.get(f"/planillas/{p.id}/detalle", headers=_auth(db, "admin1@g.test"))
    assert r.status_code == 200
    (fila,) = r.json()["rows"]
    assert fila["coincidencia"] == "cuit_distinto" and fila["grupo"] is None
    data, _movs, _f = _build_planilla_export_data(db, db.query(Planilla).get(p.id))
    assert data["rows"][0]["coincidencia"] == "cuit_distinto"


def test_detalle_muestra_el_grupo_de_cada_fila(client, db):
    p, (mov,), rows = _escenario(db, [(3000, "JUAN PEREZ", F, "extracto")],
                                 [(1000, None, "Juan Perez", F), (2000, None, "Juan Perez", F)])
    _conciliar(client, db, p)
    data = client.get(f"/planillas/{p.id}/detalle", headers=_auth(db, "admin1@g.test")).json()
    assert data["sugeridas_grupo"] == 2
    g = data["rows"][0]["grupo"]
    assert g["estado"] == "sugerido" and g["n_filas"] == 2
    assert [m["id"] for m in g["movimientos"]] == [mov.id]
    assert data["rows"][0]["mov_titular"] == "JUAN PEREZ"
    assert data["rows"][0]["coincidencia"] == "titular"
