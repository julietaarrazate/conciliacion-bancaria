from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    """Application configuration from environment variables"""

    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/conciliacion_db"

    # JWT
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # App
    app_name: str = "Sistema Conciliación Bancaria"
    debug: bool = False

    # Upload
    max_file_size: int = 50 * 1024 * 1024  # 50MB
    upload_dir: str = "/tmp/uploads"

    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()
