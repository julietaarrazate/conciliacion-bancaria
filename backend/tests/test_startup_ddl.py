"""Tests del runner de DDL de arranque (`_exec_startup_ddl` en app.main).

El fix del deadlock en deploy en caliente (ver BUGS.md) hace que cada sentencia DDL
de arranque se commitee por separado y con lock_timeout, de modo que una sentencia
que falla NO aborta las siguientes y el lock de cada tabla se libera al toque.

Estos tests usan sqlite en memoria (no Postgres), así que verifican la propiedad de
aislamiento de errores / commit-por-sentencia; `SET LOCAL lock_timeout` se saltea
solo cuando el dialecto es Postgres, por lo que en sqlite no interfiere.
"""
from sqlalchemy import create_engine, text

from app.main import _exec_startup_ddl


def _mem_conn():
    engine = create_engine("sqlite:///:memory:")
    return engine.connect()


def test_ddl_valida_aplica_y_devuelve_none():
    conn = _mem_conn()
    try:
        err = _exec_startup_ddl(conn, "CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
        assert err is None
        conn.execute(text("INSERT INTO t (v) VALUES ('x')"))
        conn.commit()
        assert conn.execute(text("SELECT COUNT(*) FROM t")).scalar() == 1
    finally:
        conn.close()


def test_ddl_invalida_devuelve_excepcion_sin_romper():
    conn = _mem_conn()
    try:
        err = _exec_startup_ddl(conn, "ALTER TABLE no_existe ADD COLUMN x INT")
        assert err is not None  # devuelve la excepción, no la propaga
    finally:
        conn.close()


def test_una_sentencia_que_falla_no_aborta_las_siguientes():
    """La propiedad central del fix: aislamiento de errores por sentencia."""
    conn = _mem_conn()
    try:
        assert _exec_startup_ddl(conn, "CREATE TABLE a (id INTEGER PRIMARY KEY)") is None
        # Sentencia intermedia que falla (tabla inexistente)
        assert _exec_startup_ddl(conn, "ALTER TABLE fantasma ADD COLUMN z INT") is not None
        # La siguiente válida DEBE aplicarse igual, en la misma conexión
        assert _exec_startup_ddl(conn, "CREATE TABLE b (id INTEGER PRIMARY KEY)") is None
        # Ambas tablas válidas existen
        tablas = {
            r[0] for r in conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            ).fetchall()
        }
        assert {"a", "b"} <= tablas
    finally:
        conn.close()


def test_no_emite_set_lock_timeout_en_sqlite():
    """SET LOCAL lock_timeout es solo Postgres; en sqlite no debe intentarse
    (rompería). Que una DDL válida aplique OK ya lo demuestra indirectamente."""
    conn = _mem_conn()
    try:
        assert conn.dialect.name == "sqlite"
        assert _exec_startup_ddl(conn, "CREATE TABLE ok (id INTEGER PRIMARY KEY)") is None
    finally:
        conn.close()
