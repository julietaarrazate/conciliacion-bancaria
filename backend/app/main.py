from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import get_settings
from app.database import engine, Base
from app.routers import auth, extractos, planillas, me, admin, auditoria, historial
from app.models import User, Cliente, ExtractoBancario, MovimientoBanco, Planilla, PlanillaRow, AuditoriaLog

# Crear tablas de forma no-fatal (no crashea si la BD no está disponible)
try:
    Base.metadata.create_all(bind=engine)
    print("[startup] Tablas OK")
except Exception as e:
    print(f"[startup] Warning: no se pudieron crear tablas: {e}")

# Migraciones manuales de columnas nuevas (idempotentes)
def _run_migrations():
    try:
        migrations = [
            "ALTER TABLE extractos_bancarios ADD COLUMN fingerprint VARCHAR",
        ]
        with engine.connect() as conn:
            for sql in migrations:
                try:
                    conn.execute(text(sql))
                    conn.commit()
                except Exception:
                    pass  # columna ya existe
        _backfill_fingerprints()
    except Exception as e:
        print(f"[startup] Warning migrations: {e}")

def _backfill_fingerprints():
    """Calcula fingerprint para extractos existentes que tienen fingerprint NULL"""
    import hashlib
    from app.database import SessionLocal
    from app.models.extracto import ExtractoBancario, MovimientoBanco

    db = SessionLocal()
    try:
        extractos_sin_fp = db.query(ExtractoBancario).filter(
            ExtractoBancario.fingerprint.is_(None)
        ).all()

        for e in extractos_sin_fp:
            movs = sorted(e.movimientos, key=lambda m: m.id)
            total = len(movs)
            if total == 0:
                e.fingerprint = "empty"
                continue
            primer_orden = movs[0].orden or 0
            ultimo_orden = movs[-1].orden or 0
            suma = round(sum(m.monto for m in movs), 2)
            raw = f"{total}|{primer_orden}|{ultimo_orden}|{suma}"
            e.fingerprint = hashlib.sha256(raw.encode()).hexdigest()[:16]

        if extractos_sin_fp:
            db.commit()
            print(f"[init] fingerprint calculado para {len(extractos_sin_fp)} extracto(s) existente(s)")
    except Exception as ex:
        db.rollback()
        print(f"[init] backfill fingerprint fallo: {ex}")
    finally:
        db.close()

_run_migrations()

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    debug=settings.debug
)

# CORS abierto para desarrollo (web local + celular en LAN + Expo Go)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router)
app.include_router(me.router)
app.include_router(extractos.router)
app.include_router(planillas.router)
app.include_router(historial.router)
app.include_router(auditoria.router)
app.include_router(admin.router)


@app.get("/")
def read_root():
    return {"status": "ok", "app": settings.app_name}


@app.get("/health")
def health_check():
    """Health check simple — siempre 200 para que Render no mate el servicio.
    El estado real de la BD se puede ver en /health/db"""
    return {"status": "ok", "app": settings.app_name}


@app.get("/health/db")
def health_db():
    """Verifica conexion a la base de datos"""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "healthy", "db": "connected"}
    except Exception as e:
        return {"status": "degraded", "db": str(e)[:100]}
