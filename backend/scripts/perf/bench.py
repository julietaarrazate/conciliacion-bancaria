"""Harness de performance: cantidad de statements SQL + ms por endpoint GET.

Cómo correrlo (desde ``backend/``)::

    python3 -m scripts.perf.bench                 # escala completa, tabla en stdout
    python3 -m scripts.perf.bench --chica         # escala de tests (rápido)
    python3 -m scripts.perf.bench --json out.json # además guarda los números
    python3 -m scripts.perf.bench --solo /contabilidad  # filtra endpoints por prefijo
    python3 -m scripts.perf.bench --sql /analisis/dashboard  # imprime los SQL de un endpoint

Usa SQLite en memoria (no hay PostgreSQL local): los ms sirven para comparar antes/después,
no son los de Neon (donde cada statement suma además ~1-5 ms de red, así que la cantidad de
statements es el número que más pesa en producción).
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from contextlib import contextmanager

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.services.auth import create_access_token  # noqa: E402

from scripts.perf.seed import ESCALA_CHICA, ESCALA_COMPLETA, seed_perf  # noqa: E402


class StatementCounter:
    """Cuenta (y guarda) los statements que pasan por un engine."""

    def __init__(self, engine):
        self.engine = engine
        self.count = 0
        self.statements: list[str] = []
        self.activo = False
        event.listen(engine, "before_cursor_execute", self._on_exec)

    def _on_exec(self, conn, cursor, statement, parameters, context, executemany):
        if self.activo:
            self.count += 1
            self.statements.append(statement)

    @contextmanager
    def medir(self):
        self.count = 0
        self.statements = []
        self.activo = True
        try:
            yield self
        finally:
            self.activo = False


def armar_entorno(escala: dict):
    logging.disable(logging.WARNING)  # el seed loguea mucho (cuentas creadas, etc.)
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = Session()
    ids = seed_perf(db, escala)
    db.close()

    def _override_db():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override_db
    client = TestClient(app, raise_server_exceptions=False)
    return engine, Session, client, ids


def token_para(user) -> dict:
    tok = create_access_token({"sub": user["email"], "user_id": user["id"], "role": user["role"]})
    return {"Authorization": f"Bearer {tok}"}


def endpoints(Session, ids) -> list[str]:
    from app.models.contabilidad import PlanCuenta
    p = ids["principal"]
    ext = p["extractos"][0]
    pl = p["planillas"][0]
    cli = p["clientes"][0]
    s = Session()
    banco = s.query(PlanCuenta).filter(PlanCuenta.organizacion_id == 1, PlanCuenta.codigo == "1-1-1-3-1").first()
    s.close()
    return [
        "/health",
        "/me",
        "/analisis/dashboard",
        "/analisis/alertas",
        "/analisis/clientes-aging",
        f"/analisis/cliente/{cli}/estado-cuenta",
        "/analisis/evolucion",
        "/analisis/flujo-caja",
        "/extractos",
        f"/extractos/{ext}",
        f"/extractos/{ext}/movimientos",
        f"/extractos/{ext}/resumen",
        "/conciliaciones",
        f"/planillas/{pl}",
        f"/planillas/{pl}/detalle",
        f"/planillas/{pl}/revision",
        "/historial/planillas",
        "/historial/extractos",
        "/clientes/archivos",
        "/clientes/estructura",
        "/cheques",
        "/cheques/portadores",
        "/pagos",
        "/pagos/categorias",
        "/caja/arqueo/hoy",
        "/caja/arqueo/historial",
        "/contabilidad/stats",
        "/contabilidad/plan-cuentas",
        "/contabilidad/asientos",
        "/contabilidad/asientos/gaps",
        f"/contabilidad/libro-mayor?cuenta_id={banco.id if banco else 1}",
        "/contabilidad/sumas-saldo",
        "/contabilidad/balance",
        "/contabilidad/cuentas-corrientes",
        f"/contabilidad/cuenta-corriente?cliente_id={cli}",
        "/contabilidad/clientes-cuentas",
        "/auditoria",
        "/auditoria/insights",
        "/search?q=PEREZ",
        "/iva/proyeccion?periodo=2026-08",
        "/iva/liquidacion?periodo=2026-08",
        "/iibb/proyeccion?periodo=2026-08",
        "/monotributo/control?periodo=2026-S2",
        "/sueldos/liquidacion?periodo=2026-08",
        "/liquidaciones",
        "/tarjetas",
        "/vencimientos/grilla?mes=2026-08",
        "/contabilidad/reglas",
        "/contabilidad/asientos/1",
        "/cheques/deposito",
        "/proveedores",
        "/comprobantes-compra",
        "/auditoria/patrones",
        "/iva/historial",
        "/extractos-pdf/borradores",
    ]


def limpiar_caches():
    """Vacía los caches en memoria de los routers para medir el costo real (cache frío)."""
    from app.routers import analisis, ctb_ctas_corrientes, ctb_libro
    analisis._cache.clear()
    ctb_ctas_corrientes._cartera_cache.clear()
    ctb_libro._reportes_cache.clear()


def correr(escala: dict, solo: str | None = None, sql_de: str | None = None, repeticiones: int = 3):
    engine, Session, client, ids = armar_entorno(escala)
    counter = StatementCounter(engine)
    headers = token_para(ids["principal"]["admin"])
    filas = []
    for path in endpoints(Session, ids):
        if solo and not path.startswith(solo):
            continue
        client.get(path, headers=headers)  # calentamiento (caches de import / compilación)
        tiempos = []
        for _ in range(repeticiones):
            limpiar_caches()
            with counter.medir():
                t0 = time.perf_counter()
                r = client.get(path, headers=headers)
                tiempos.append((time.perf_counter() - t0) * 1000)
        n = counter.count
        filas.append({"path": path, "status": r.status_code, "sql": n, "ms": round(min(tiempos), 1),
                      "kb": round(len(r.content) / 1024, 1)})
        if sql_de and path.startswith(sql_de):
            for st in counter.statements:
                print("   ", " ".join(st.split())[:220])
    app.dependency_overrides.pop(get_db, None)
    return filas


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--chica", action="store_true")
    ap.add_argument("--json")
    ap.add_argument("--solo")
    ap.add_argument("--sql")
    args = ap.parse_args(argv)
    escala = ESCALA_CHICA if args.chica else ESCALA_COMPLETA
    t0 = time.perf_counter()
    filas = correr(escala, args.solo, args.sql)
    print(f"# seed+bench en {time.perf_counter() - t0:.1f}s · escala={'chica' if args.chica else 'completa'}")
    print(f"{'endpoint':60} {'st':>4} {'sql':>6} {'ms':>8} {'kb':>8}")
    for f in filas:
        print(f"{f['path'][:60]:60} {f['status']:>4} {f['sql']:>6} {f['ms']:>8} {f['kb']:>8}")
    if args.json:
        with open(args.json, "w") as fh:
            json.dump(filas, fh, indent=1)


if __name__ == "__main__":
    sys.exit(main())
