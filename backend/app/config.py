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
    app_name: str = "Conciliacion Bancaria - Caneland SA"
    debug: bool = False

    # Archivos
    max_file_size: int = 50 * 1024 * 1024   # 50 MB
    upload_dir: str = "/tmp/uploads"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        # Permite que variables de entorno del sistema anulen el .env
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
