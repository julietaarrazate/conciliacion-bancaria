"""Guard de la segunda fuente de esquema (safety-net DDL).

Las sentencias de `app/db_safety.py` corren en CADA arranque (ver
`main.py::_run_alembic`), también contra una DB ya migrada. Si una no es
idempotente, el segundo boot —o el primero sobre una DB que ya tiene el esquema—
crashea. Este test bloquea esa clase de bug en CI.

No valida la semántica del esquema (eso lo cubren Alembic + los tests de cada
módulo); valida el invariante operativo: **toda sentencia es segura de re-ejecutar**.
"""
import re

from app.db_safety import SAFETY_NET_DDL


def _norm(sql: str) -> str:
    return " ".join(sql.split()).upper()


def test_hay_sentencias():
    assert SAFETY_NET_DDL, "la lista de safety-net no puede estar vacía"


def test_todas_las_sentencias_son_idempotentes():
    """Cada statement debe ser seguro de re-ejecutar en cada boot."""
    fallos = []
    for sql in SAFETY_NET_DDL:
        s = _norm(sql)
        ok = (
            ("CREATE TABLE" in s and "IF NOT EXISTS" in s)
            or ("CREATE INDEX" in s and "IF NOT EXISTS" in s)
            or ("CREATE UNIQUE INDEX" in s and "IF NOT EXISTS" in s)
            or ("ADD COLUMN" in s and "IF NOT EXISTS" in s)
            or ("DROP INDEX" in s and "IF EXISTS" in s)
            # UPDATE ... WHERE es naturalmente idempotente (setea sólo lo que falta)
            or s.startswith("UPDATE ")
        )
        if not ok:
            fallos.append(sql[:90])
    assert not fallos, (
        "Sentencias NO idempotentes en SAFETY_NET_DDL (crashean el 2º boot). "
        "Usá IF NOT EXISTS / IF EXISTS:\n  - " + "\n  - ".join(fallos)
    )


def test_no_hay_indices_duplicados():
    """Dos CREATE INDEX con el mismo nombre = descuido al copiar/pegar."""
    nombres = []
    for sql in SAFETY_NET_DDL:
        m = re.search(r"CREATE\s+(?:UNIQUE\s+)?INDEX\s+IF\s+NOT\s+EXISTS\s+(\w+)", sql, re.I)
        if m:
            nombres.append(m.group(1).lower())
    dups = {n for n in nombres if nombres.count(n) > 1}
    assert not dups, f"índices duplicados en SAFETY_NET_DDL: {sorted(dups)}"


def test_todas_son_strings_no_vacios():
    for i, sql in enumerate(SAFETY_NET_DDL):
        assert isinstance(sql, str) and sql.strip(), f"item {i} vacío o no-string"
