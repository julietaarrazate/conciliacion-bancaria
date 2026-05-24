from pydantic_settings import BaseSettings
from functools import lru_cache
import os


class Settings(BaseSettings):
    # Base de datos — SQLite local si no hay DATABASE_URL (dev), PostgreSQL en produccion
    database_url: str = "sqlite:///./conciliacion.db"

    # JWT
    secret_key: str = "dev-secret-key-CAMBIAR-en-produccion"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 480   # 8h = jornada laboral

    # App
    app_name: str = "Conciliacion Bancaria — Julieta Arrazate"
    debug: bool = False

    # Archivos
    max_file_size: int = 50 * 1024 * 1024   # 50 MB
    upload_dir: str = "/tmp/uploads"

    # Backup automatico diario por email
    # Si RESEND_API_KEY esta vacio, el scheduler no corre (modo dev / opt-in).
    resend_api_key: str = ""
    backup_email_to: str = "julietaarrazate@gmail.com"
    backup_email_from: str = "onboarding@resend.dev"  # default de Resend, no requiere DNS
    backup_hour_art: int = 3      # 03:00 ART (06:00 UTC)
    backup_minute: int = 0
    backup_enabled: bool = True   # apagable via env var sin tocar codigo

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        # Permite que variables de entorno del sistema anulen el .env
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
