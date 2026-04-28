from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import get_settings
from app.database import engine, Base
from app.routers import auth, extractos, planillas
from app.models import User, Cliente, ExtractoBancario, MovimientoBanco, Planilla, PlanillaRow, AuditoriaLog

# Crear todas las tablas
Base.metadata.create_all(bind=engine)

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    debug=settings.debug
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Cambiar en producción
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluir routers
app.include_router(auth.router)
app.include_router(extractos.router)
app.include_router(planillas.router)

@app.get("/")
def read_root():
    """Health check"""
    return {
        "status": "ok",
        "app": settings.app_name
    }

@app.get("/health")
def health_check():
    """Verifica que la BD está disponible"""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "healthy"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}, 503
