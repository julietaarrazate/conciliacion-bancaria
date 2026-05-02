from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    """Application configuration from environment variables"""

    # Database
    database_url: str = "sqlite:///./test.db"

    # JWT
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 480  # 8 horas - una jornada laboral completa

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
