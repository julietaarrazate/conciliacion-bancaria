import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base

# Leer DATABASE_URL del entorno
# Railway/Render inyectan postgres://... → normalizar a postgresql://
_raw_url = os.getenv("DATABASE_URL", "sqlite:///./conciliacion.db")

# Normalizar esquema (Render/Heroku dan "postgres://" pero SQLAlchemy 2.x pide "postgresql://")
if _raw_url.startswith("postgres://"):
    _raw_url = _raw_url.replace("postgres://", "postgresql://", 1)

DATABASE_URL = _raw_url

# Configuracion segun driver
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    # PostgreSQL: pool de conexiones para produccion
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,      # Reconecta si la conexion cayo
        pool_recycle=300,         # Recicla conexiones cada 5 min
        pool_size=5,
        max_overflow=10,
    )

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
