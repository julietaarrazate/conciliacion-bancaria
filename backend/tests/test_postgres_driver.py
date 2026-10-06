"""Guard: la URL de producción (postgresql://) debe resolver a un driver instalado.

Los tests corren contra SQLite, así que un cambio de driver por defecto en
SQLAlchemy (2.1 pasó de psycopg2 a psycopg 3) pasaba el CI y rompía el
arranque en Render con "No module named 'psycopg'". create_engine importa el
driver sin conectarse, así que esto lo detecta sin necesitar una base real.
"""
from sqlalchemy import create_engine


def test_postgresql_url_resuelve_driver_instalado():
    engine = create_engine("postgresql://u:p@localhost:5432/db")
    assert engine.dialect.driver == "psycopg2"
    engine.dispose()
