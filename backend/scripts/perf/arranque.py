"""Mide el arranque: statements SQL y tiempo de `_init_db` en un 2º boot (DB ya poblada).

    cd backend && python3 -m scripts.perf.arranque [--orgs 10]

Usa un SQLite en archivo temporal (no hay PostgreSQL local): algunas sentencias
específicas de Postgres fallan rápido y se cuentan igual. Lo que importa es cuántas
sentencias corre cada boot y cuáles escalan con la cantidad de orgs / extractos, porque
en Neon cada una es un round-trip de red.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import tempfile
import time
from collections import Counter

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp.name}"

from sqlalchemy import event  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
import app.main as main  # noqa: E402

from scripts.perf.seed import ESCALA_CHICA, _seed_org  # noqa: E402


def main_(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--orgs", type=int, default=10)
    args = ap.parse_args(argv)
    logging.disable(logging.WARNING)

    Base.metadata.create_all(bind=engine)
    import random
    rng = random.Random(1)
    db = SessionLocal()
    for oid in range(1, args.orgs + 1):
        _seed_org(db, oid, f"Org {oid}", ESCALA_CHICA, rng)
    db.close()

    sentencias: list[str] = []

    @event.listens_for(engine, "before_cursor_execute")
    def _cnt(conn, cursor, statement, parameters, context, executemany):
        sentencias.append(" ".join(statement.split())[:70])

    for boot in (1, 2):
        sentencias.clear()
        t0 = time.perf_counter()
        main._init_db()
        ms = (time.perf_counter() - t0) * 1000
        print(f"boot {boot}: {len(sentencias)} statements, {ms:.0f} ms ({args.orgs} orgs)")
    print("\npor tipo en el boot 2:")
    for k, n in Counter(" ".join(x.split()[:3]) for x in sentencias).most_common(12):
        print(f"{n:5}  {k}")
    print("\nmás repetidas en el boot 2:")
    for st, n in Counter(sentencias).most_common(15):
        print(f"{n:5}  {st}")
    os.unlink(_tmp.name)


if __name__ == "__main__":
    sys.exit(main_())
