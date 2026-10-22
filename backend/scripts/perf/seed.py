"""Seed de volumen realista para medir performance (statements SQL + ms por request).

Arma, sobre una sesión SQLAlchemy ya creada (normalmente SQLite en memoria), dos
organizaciones con datos operativos:

- Org principal (id=1): ``extractos`` extractos con ``movs_por_extracto`` movimientos
  cada uno, ``clientes`` clientes (con cuenta corriente contable), ``planillas``
  planillas de ``filas_por_planilla`` filas conciliadas con el motor real
  (``conciliar_planilla`` → asientos por cliente), ``cheques`` cheques
  (con asiento), ``pagos`` egresos (con asiento), arqueos de caja y auditoría.
- Org secundaria (id=2): lo mismo a escala reducida, para que el aislamiento
  multi-tenant se mida con datos ajenos presentes.

Se usa desde ``scripts/perf/bench.py`` (tabla antes/después) y desde
``tests/test_perf_queries.py`` (regresión de cantidad de queries, a escala chica).
"""
from __future__ import annotations

import random
from datetime import date, datetime, timedelta
from decimal import Decimal

from app.models.auditoria import AuditoriaLog
from app.models.caja import ArqueoDiario
from app.models.cheque import Cheque
from app.models.cliente import Cliente
from app.models.egreso import Egreso
from app.models.extracto import ExtractoBancario, MovimientoBanco
from app.models.organizacion import Organizacion
from app.models.planilla import Planilla, PlanillaRow
from app.models.portador import Portador
from app.models.user import User
from app.services.auth import get_password_hash
from app.services.conciliacion import conciliar_planilla
from app.services.motor_contable import (
    _get_o_crear_cuenta_cliente,
    registrar_cheque,
    registrar_egreso,
)
from app.services.tz import hoy_art
from app.services.seed_contable import seed_categorias_egreso_org, seed_contabilidad_org

# Escala "realista" pedida para el harness de performance.
ESCALA_COMPLETA = dict(
    extractos=3, movs_por_extracto=1000, clientes=40, planillas=60,
    filas_por_planilla=30, cheques=300, pagos=500, arqueos=60, auditoria=2000,
    foto_kb=150,
)

# Escala chica para los tests de regresión (rápida, misma forma de datos).
ESCALA_CHICA = dict(
    extractos=2, movs_por_extracto=60, clientes=6, planillas=6,
    filas_por_planilla=8, cheques=20, pagos=30, arqueos=5, auditoria=50,
    foto_kb=2,
)

_NOMBRES = ["PEREZ", "GOMEZ", "RODRIGUEZ", "FERNANDEZ", "LOPEZ", "MARTINEZ", "GARCIA",
            "SANCHEZ", "ROMERO", "DIAZ", "TORRES", "ALVAREZ", "RUIZ", "SOSA", "BENITEZ"]
_PILA = ["JUAN", "MARIA", "CARLOS", "ANA", "LUIS", "LAURA", "JORGE", "SOFIA", "PABLO", "LUCIA"]


def _cuit(rng: random.Random) -> str:
    return f"20{rng.randint(10_000_000, 99_999_999)}{rng.randint(0, 9)}"


def _monto(rng: random.Random) -> Decimal:
    return Decimal(rng.randint(5_000, 900_000)) + Decimal(rng.randint(0, 99)) / 100


def _foto(kb: int) -> str:
    """Foto de comprobante como la guarda la app sin R2: data-URL base64 en la DB."""
    return "data:image/jpeg;base64," + ("/9j/4AAQSkZJRgABAQ" * (kb * 1024 // 18 + 1))[: kb * 1024]


def _seed_org(db, org_id: int, nombre: str, esc: dict, rng: random.Random) -> dict:
    foto = _foto(esc.get("foto_kb", 0))
    db.add(Organizacion(id=org_id, nombre=nombre, plan="pro"))
    db.commit()
    seed_contabilidad_org(db, org_id)
    seed_categorias_egreso_org(db, org_id)

    admin = User(
        email=f"admin{org_id}@perf.test", full_name=f"Admin {org_id}",
        hashed_password=get_password_hash("pw"), organizacion_id=org_id,
        is_active=True, role="admin", is_superadmin=False,
    )
    db.add(admin)
    db.commit()

    # ── Clientes con cuenta corriente contable ───────────────────────────────
    clientes = []
    for i in range(esc["clientes"]):
        c = Cliente(nombre=f"Cliente {org_id}-{i:03d}", cuit=_cuit(rng), organizacion_id=org_id)
        db.add(c)
        clientes.append(c)
    db.commit()
    for c in clientes:
        cta = _get_o_crear_cuenta_cliente(db, c.id, org_id)
        if cta is not None:
            c.cuenta_contable_id = cta.id
    db.commit()

    # ── Extractos + movimientos ──────────────────────────────────────────────
    base = date(2026, 7, 1)
    extractos, movs_por_ext = [], {}
    for e in range(esc["extractos"]):
        ext = ExtractoBancario(
            nombre_archivo=f"extracto_{org_id}_{e}.xlsx", creado_por=admin.id,
            fecha_extracto=base + timedelta(days=30 * e), fingerprint=f"fp{org_id}-{e}",
            banco="Banco Macro", organizacion_id=org_id,
        )
        db.add(ext)
        db.flush()
        movs = []
        saldo = Decimal("1000000")
        for k in range(esc["movs_por_extracto"]):
            cuit = _cuit(rng)
            titular = f"TRANSF. DE {cuit} {rng.choice(_PILA)} {rng.choice(_NOMBRES)}"
            monto = _monto(rng)
            if rng.random() < 0.15:  # débitos
                monto = -monto
            saldo += monto
            f = base + timedelta(days=30 * e + rng.randint(0, 29))
            movs.append(MovimientoBanco(
                extracto_id=ext.id, orden=k + 1, fecha=f, mes=str(f.month), titular=titular,
                monto=monto, saldo=saldo, source="um" if rng.random() < 0.2 else "extracto",
                organizacion_id=org_id,
            ))
        db.add_all(movs)
        extractos.append(ext)
        movs_por_ext[ext.id] = movs
    db.commit()

    # ── Planillas conciliadas con el motor real (genera asientos por cliente) ──
    planillas = []
    for p in range(esc["planillas"]):
        cli = clientes[p % len(clientes)]
        ext = extractos[p % len(extractos)]
        movs = movs_por_ext[ext.id]
        pl = Planilla(
            cliente_id=cli.id, extracto_id=ext.id, usuario_id=admin.id, organizacion_id=org_id,
            nombre_archivo=f"planilla_{org_id}_{p}.xlsx",
            fecha_carga=datetime(2026, 7, 1) + timedelta(days=p),
        )
        db.add(pl)
        db.flush()
        rows = []
        for _ in range(esc["filas_por_planilla"]):
            if rng.random() < 0.7:  # fila que matchea un movimiento (monto + CUIT del titular)
                m = rng.choice(movs)
                cuit = m.titular.split()[2]
                rows.append(PlanillaRow(planilla_id=pl.id, organizacion_id=org_id, monto=abs(m.monto),
                                        cuit=cuit, titular=" ".join(m.titular.split()[3:]),
                                        fecha=m.fecha, status="pendiente"))
            else:
                rows.append(PlanillaRow(planilla_id=pl.id, organizacion_id=org_id, monto=_monto(rng),
                                        cuit=_cuit(rng), titular=rng.choice(_NOMBRES),
                                        fecha=base, status="pendiente"))
        db.add_all(rows)
        db.flush()
        conciliar_planilla(db, rows, movs, cli.nombre, "2026-08-01", org_id=org_id, cliente_id=cli.id)
        planillas.append(pl)
    db.commit()

    # ── Cheques ──────────────────────────────────────────────────────────────
    portador = Portador(organizacion_id=org_id, nombre="Portador perf")
    db.add(portador)
    db.flush()
    estados = ["registrado", "depositado", "acreditado", "rechazado"]
    cheques = []
    for i in range(esc["cheques"]):
        cli = clientes[i % len(clientes)]
        monto = _monto(rng)
        ch = Cheque(
            organizacion_id=org_id, cliente_id=cli.id, portador_id=portador.id if i % 3 == 0 else None,
            numero=str(10_000_000 + i), banco_origen="Banco Nación", librador=f"{rng.choice(_NOMBRES)} SA",
            monto=monto, comision=(monto * Decimal("0.01")).quantize(Decimal("0.01")),
            fecha_emision=base + timedelta(days=i % 90), fecha_deposito=base + timedelta(days=i % 90 + 5),
            estado=estados[i % len(estados)], usuario_id=admin.id,
            foto_comprobante=foto if i % 3 == 0 else None,
        )
        if i % 10 == 1:  # en cartera y por vencer en la semana (dashboard / alertas)
            ch.estado = "registrado"
            ch.fecha_deposito = hoy_art() + timedelta(days=i % 7)
        db.add(ch)
        cheques.append(ch)
    db.commit()
    for ch in cheques:
        registrar_cheque(db, ch.id, org_id, admin.id, ch.librador, ch.monto, ch.comision, ch.fecha_emision)

    # ── Arqueos de caja ──────────────────────────────────────────────────────
    arqueos = []
    for d in range(esc["arqueos"]):
        a = ArqueoDiario(organizacion_id=org_id, fecha=base + timedelta(days=d), saldo_inicial=Decimal("50000"),
                         ingresos=Decimal("1000"), creado_por=admin.id, cerrado=d < esc["arqueos"] - 1,
                         denominaciones={"1000": 10, "500": 4})
        db.add(a)
        arqueos.append(a)
    db.commit()

    # ── Pagos (egresos) ──────────────────────────────────────────────────────
    tipos = ["proveedor", "gasto", "pago_cliente"]
    egresos = []
    for i in range(esc["pagos"]):
        tipo = tipos[i % 3]
        forma = "efectivo" if i % 4 == 0 else "banco"
        cli = clientes[i % len(clientes)] if tipo == "pago_cliente" else None
        arq = arqueos[i % len(arqueos)] if forma == "efectivo" else None
        eg = Egreso(
            organizacion_id=org_id, tipo=tipo, categoria="Otros", forma_pago=forma, monto=_monto(rng),
            fecha=base + timedelta(days=i % 90), beneficiario=f"Prov {i % 25}",
            cliente_id=cli.id if cli else None, concepto=f"Pago {i}",
            arqueo_id=arq.id if arq else None, usuario_id=admin.id,
            foto_comprobante=foto if i % 5 < 2 else None,
        )
        db.add(eg)
        egresos.append((eg, cli))
    db.commit()
    for eg, cli in egresos:
        registrar_egreso(db, eg.id, org_id, admin.id, eg.tipo, eg.forma_pago, eg.monto, eg.fecha,
                         beneficiario=eg.beneficiario, concepto=eg.concepto,
                         cliente_id=cli.id if cli else None, cliente_nombre=cli.nombre if cli else "")

    # ── Módulos impositivos activados (Monotributo, IIBB, Sueldos) ───────────
    from app.models.iibb import IIBBConfig, JurisdiccionIIBB
    from app.models.monotributo import MonotributoConfig
    from app.models.sueldos import CategoriaConvenio, ConfigSueldos, ConvenioColectivo, Empleado
    from app.services.iibb_service import seed_iibb_jurisdiccion
    from app.services.monotributo_service import seed_monotributo_categorias
    from app.services.sueldos_service import seed_config_sueldos

    seed_monotributo_categorias(db, org_id)
    seed_iibb_jurisdiccion(db, org_id)
    seed_config_sueldos(db, org_id)
    db.add(MonotributoConfig(organizacion_id=org_id, categoria_actual="D", activo=True))
    jur = db.query(JurisdiccionIIBB).filter(JurisdiccionIIBB.organizacion_id == org_id).first()
    db.add(IIBBConfig(organizacion_id=org_id, activo=True, modo="simple",
                      jurisdiccion_unica_id=jur.id if jur else None))
    cfg = db.query(ConfigSueldos).filter(ConfigSueldos.organizacion_id == org_id).first()
    cfg.activo = True
    conv = ConvenioColectivo(organizacion_id=org_id, nombre="Comercio")
    db.add(conv)
    db.flush()
    cat = CategoriaConvenio(convenio_id=conv.id, nombre="Administrativo A", sueldo_basico=Decimal("950000"))
    db.add(cat)
    db.flush()
    db.add_all([
        Empleado(organizacion_id=org_id, nombre=f"Empleado {i}", cuil=f"2{i:010d}", convenio_id=conv.id,
                 categoria_id=cat.id, fecha_ingreso=date(2024, 1, 1))
        for i in range(max(2, esc["clientes"] // 4))
    ])
    db.commit()

    # ── Auditoría ────────────────────────────────────────────────────────────
    acciones = ["INSERT", "UPDATE", "DELETE", "LOGIN"]
    db.add_all([
        AuditoriaLog(usuario_id=admin.id, tabla=rng.choice(["planillas", "cheques", "egresos"]),
                     registro_id=i, accion=acciones[i % 4], cambios={"i": i},
                     timestamp=datetime(2026, 7, 1) + timedelta(minutes=37 * i))
        for i in range(esc["auditoria"])
    ])
    db.commit()

    return {
        "org_id": org_id,
        "admin": {"id": admin.id, "email": admin.email, "role": admin.role},
        "extractos": [e.id for e in extractos],
        "planillas": [p.id for p in planillas], "clientes": [c.id for c in clientes],
        "cheques": [c.id for c in cheques],
    }


def seed_perf(db, escala: dict | None = None, seed: int = 42) -> dict:
    """Siembra org 1 (escala dada) + org 2 (un tercio). Devuelve ids útiles por org."""
    esc = dict(escala or ESCALA_COMPLETA)
    rng = random.Random(seed)
    principal = _seed_org(db, 1, "Org Perf", esc, rng)
    chica = {k: max(1, v // 3) for k, v in esc.items()}
    chica["foto_kb"] = esc.get("foto_kb", 0)
    otra = _seed_org(db, 2, "Otra Org", chica, rng)
    return {"principal": principal, "otra": otra}
