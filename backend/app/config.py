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

    # URL del frontend en produccion — se usa para armar links en emails
    # (recuperacion de contraseña, etc). Se puede sobreescribir con FRONTEND_URL.
    frontend_url: str = "https://conciliacion-bancaria-ten.vercel.app"

    # Sentry — monitoreo de errores en producción (opt-in)
    # Setear SENTRY_DSN en Render para activar. Sin DSN, no se envía nada.
    sentry_dsn: str = ""

    # Observabilidad — umbral (ms) por encima del cual una request se loguea
    # como lenta (WARNING en los logs de Render + breadcrumb en Sentry).
    # Ajustable via env SLOW_REQUEST_MS sin tocar código.
    slow_request_ms: int = 1500

    # Web Push (VAPID) — generados via POST /push/setup
    # Si están vacíos, el push queda deshabilitado (opt-in).
    vapid_private_key: str = ""
    vapid_public_key: str = ""
    push_enabled: bool = True
    admin_email: str = "julietaarrazate@gmail.com"

    # Google OAuth (opt-in) — setear GOOGLE_CLIENT_ID y GOOGLE_CLIENT_SECRET en Render
    # Obtener en console.cloud.google.com → APIs & Services → Credentials
    # El flujo auth-code (redirect) intercambia el código en el backend con el secret.
    google_client_id: str = ""
    google_client_secret: str = ""

    # S3/R2 Storage — almacenamiento externo de fotos (opt-in)
    # Si S3_ENDPOINT está vacío, las fotos se guardan como base64 en DB (fallback).
    # Necesarias todas: S3_ENDPOINT, S3_BUCKET, S3_ACCESS_KEY, S3_SECRET_KEY, S3_PUBLIC_URL, S3_REGION
    s3_endpoint: str = ""

    # ARCA (ex-AFIP) — facturación electrónica, integración propia WSFEv1/WSAA (opt-in por org)
    # ARCA_ENCRYPTION_KEY cifra en reposo el certificado y la clave privada de cada organización
    # antes de guardarlos en la DB (Fernet/AES). Setear en Render — generar con:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # Sin esta key, el módulo ARCA no permite cargar certificados (falla explícito, no degrada).
    arca_encryption_key: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        # Permite que variables de entorno del sistema anulen el .env
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
