"""Mide el efecto de un índice candidato con volumen de producción (SQLite como proxy).

    cd backend && python3 -m scripts.perf.indices

Para cada candidato: crea la tabla con N filas, corre la query típica que lo usa con y
sin el índice (mejor de 20 corridas) e imprime el plan de SQLite (SCAN = recorre la tabla
entera; SEARCH ... USING INDEX = usa el índice). En PostgreSQL la diferencia de un SCAN
sobre una tabla grande es del mismo orden o mayor (y además pesa en el chequeo de FK al
borrar la fila referenciada).
"""
from __future__ import annotations

import random
import sqlite3
import time

CANDIDATOS = [
    {
        "nombre": "planilla_rows.orden_movimiento_acreditado",
        "tabla": "CREATE TABLE planilla_rows (id INTEGER PRIMARY KEY, planilla_id INT, status TEXT, "
                 "monto NUMERIC, orden_movimiento_acreditado INT)",
        "filas": 60_000,  # ~2 años de 60 planillas/mes x 30 filas (una org mediana)
        "insert": "INSERT INTO planilla_rows (planilla_id, status, monto, orden_movimiento_acreditado) "
                  "VALUES (?, ?, ?, ?)",
        "fila": lambda i, r: (i // 30, "ok", r.randint(1, 10**6), i if r.random() < 0.7 else None),
        "indice": "CREATE INDEX ix_planilla_rows_orden_mov ON planilla_rows (orden_movimiento_acreditado)",
        # editar/borrar un movimiento y el filtro por movimiento del detalle de planilla
        "query": "SELECT id, planilla_id FROM planilla_rows WHERE orden_movimiento_acreditado = ?",
        "param": lambda r: (r.randint(0, 60_000),),
    },
    {
        "nombre": "egresos.arqueo_id",
        "tabla": "CREATE TABLE egresos (id INTEGER PRIMARY KEY, organizacion_id INT, monto NUMERIC, "
                 "arqueo_id INT, fecha TEXT)",
        "filas": 20_000,  # ~2-3 años de pagos de una org
        "insert": "INSERT INTO egresos (organizacion_id, monto, arqueo_id, fecha) VALUES (?, ?, ?, ?)",
        "fila": lambda i, r: (1, r.randint(1, 10**6), (i // 8) if r.random() < 0.4 else None, "2026-01-01"),
        "indice": "CREATE INDEX ix_egresos_arqueo_id ON egresos (arqueo_id)",
        # arqueo del día (lazy de a.egresos) y el historial (selectinload IN de 30 arqueos)
        "query": "SELECT id, monto FROM egresos WHERE arqueo_id IN (" + ",".join("?" * 30) + ")",
        "param": lambda r: tuple(range(s := r.randint(0, 2000), s + 30)),
    },
]


def _medir(con, query, params, n=20) -> float:
    mejor = float("inf")
    for p in params[:n]:
        t0 = time.perf_counter()
        con.execute(query, p).fetchall()
        mejor = min(mejor, (time.perf_counter() - t0) * 1000)
    return mejor


def main():
    for c in CANDIDATOS:
        r = random.Random(7)
        con = sqlite3.connect(":memory:")
        con.execute(c["tabla"])
        con.executemany(c["insert"], (c["fila"](i, r) for i in range(c["filas"])))
        con.commit()
        params = [c["param"](r) for _ in range(20)]
        plan_sin = con.execute("EXPLAIN QUERY PLAN " + c["query"], params[0]).fetchall()[-1][-1]
        sin = _medir(con, c["query"], params)
        con.execute(c["indice"])
        plan_con = con.execute("EXPLAIN QUERY PLAN " + c["query"], params[0]).fetchall()[-1][-1]
        con_ix = _medir(con, c["query"], params)
        print(f"{c['nombre']} ({c['filas']} filas)")
        print(f"   sin índice: {sin:8.3f} ms  [{plan_sin}]")
        print(f"   con índice: {con_ix:8.3f} ms  [{plan_con}]")


if __name__ == "__main__":
    main()
