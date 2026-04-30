import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Default: SQLite local (sin docker). Override con env var DATABASE_URL para Postgres.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")

# Render/Heroku dan URL "postgres://..." pero SQLAlchemy 2.x quiere "postgresql://"
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# SQLite necesita check_same_thread=False; Postgres no
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

Base = declarative_base()


def get_db():
    """Dependency para inyectar sesión de BD"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
