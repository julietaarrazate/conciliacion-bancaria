import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import get_settings
from app.database import engine, Base
from app.routers import auth, extractos, planillas, me, admin, auditoria, historial, clientes_dir
from app.models import User, Cliente, ExtractoBancario, MovimientoBanco, Planilla, PlanillaRow, AuditoriaLog

settings = get_settings()


def _init_db():
    """Crea tablas, migraciones y seed en background — no bloquea el arranque."""
    import hashlib
    from app.database import SessionLocal
    from app.models.extracto import ExtractoBancario as Extracto

    # 1. Crear tablas
    try:
        Base.metadata.create_all(bind=engine)
        print("[db] Tablas OK")
    except Exception as e:
        print(f"[db] Warning tablas: {e}")
        return

    # 2. Migraciones de columnas nuevas
    for migration_sql in [
        "ALTER TABLE extractos_bancarios ADD COLUMN fingerprint VARCHAR",
        "ALTER TABLE movimientos_banco ADD COLUMN source VARCHAR DEFAULT 'extracto'",
    ]:
        try:
            with engine.connect() as conn:
                conn.execute(text(migration_sql))
                conn.commit()
        except Exception:
            pass  # columna ya existe

    # 3. Backfill fingerprints
    try:
        db = SessionLocal()
        sin_fp = db.query(Extracto).filter(Extracto.fingerprint.is_(None)).all()
        for e in sin_fp:
            movs = sorted(e.movimientos, key=lambda m: m.id)
            total = len(movs)
            if total == 0:
                e.fingerprint = "empty"
                continue
            raw = f"{total}|{movs[0].orden or 0}|{movs[-1].orden or 0}|{round(sum(m.monto for m in movs),2)}"
            e.fingerprint = hashlib.sha256(raw.encode()).hexdigest()[:16]
        if sin_fp:
            db.commit()
            print(f"[db] fingerprint calculado para {len(sin_fp)} extracto(s)")
        db.close()
    except Exception as ex:
        print(f"[db] Warning fingerprint: {ex}")

    # 4. Seed usuarios iniciales
    try:
        from app.database import SessionLocal as SL
        from app.models.user import User as U, RoleEnum
        from app.services.auth import get_password_hash
        db = SL()
        seeds = [
            ("admin@caneland.com", "admin123", "Administrador", RoleEnum.ADMIN),
            ("operador@caneland.com", "operador123", "Operador", RoleEnum.OPERADOR),
        ]
        created = 0
        for email, pwd, name, role in seeds:
            if not db.query(U).filter(U.email == email).first():
                db.add(U(email=email, full_name=name,
                          hashed_password=get_password_hash(pwd),
                          role=role.value, is_active=True))
                created += 1
        if created:
            db.commit()
            print(f"[db] {created} usuario(s) creado(s)")
        db.close()
    except Exception as ex:
        print(f"[db] Warning seed: {ex}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicializar BD en un hilo background — uvicorn arranca INMEDIATAMENTE
    t = threading.Thread(target=_init_db, daemon=True)
    t.start()
    yield
    # shutdown (nada que limpiar)


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    debug=settings.debug,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(me.router)
app.include_router(extractos.router)
app.include_router(planillas.router)
app.include_router(historial.router)
app.include_router(auditoria.router)
app.include_router(admin.router)
app.include_router(clientes_dir.router)


@app.get("/")
def read_root():
    return {"status": "ok", "app": settings.app_name}


@app.get("/health")
def health_check():
    """Siempre 200 — Render usa esto para el health check."""
    return {"status": "ok"}


@app.get("/health/db")
def health_db():
    """Verifica la conexion a la BD."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "healthy", "db": "connected"}
    except Exception as e:
        return {"status": "degraded", "db": str(e)[:100]}
