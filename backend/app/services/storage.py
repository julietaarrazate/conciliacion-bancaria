"""
Storage de archivos (fotos de comprobantes).

Si las env vars S3_* están configuradas, sube a S3/R2 y devuelve la URL pública.
Si no, devuelve el data URL base64 tal cual (fallback transparente).

Variables de entorno necesarias para activar S3/R2:
    S3_ENDPOINT      — ej: https://<accountid>.r2.cloudflarestorage.com
    S3_BUCKET        — nombre del bucket
    S3_ACCESS_KEY    — access key id
    S3_SECRET_KEY    — secret access key
    S3_PUBLIC_URL    — URL pública base (ej: https://pub-xxx.r2.dev o tu dominio custom)
    S3_REGION        — opcional, default "auto" (R2 usa "auto")
"""
import base64
import logging
import os
import re
import uuid
from typing import Optional

logger = logging.getLogger(__name__)


def _is_configured() -> bool:
    return all(os.getenv(v) for v in ("S3_ENDPOINT", "S3_BUCKET", "S3_ACCESS_KEY", "S3_SECRET_KEY", "S3_PUBLIC_URL"))


def _client():
    import boto3
    from botocore.config import Config
    return boto3.client(
        "s3",
        endpoint_url=os.getenv("S3_ENDPOINT"),
        aws_access_key_id=os.getenv("S3_ACCESS_KEY"),
        aws_secret_access_key=os.getenv("S3_SECRET_KEY"),
        region_name=os.getenv("S3_REGION", "auto"),
        config=Config(signature_version="s3v4"),
    )


def _parse_data_url(data_url: str) -> Optional[tuple[bytes, str]]:
    """Extrae bytes y content-type de un data URL. None si no es data URL."""
    m = re.match(r"^data:([\w/\-+.]+);base64,(.+)$", data_url, re.DOTALL)
    if not m:
        return None
    content_type = m.group(1)
    try:
        return base64.b64decode(m.group(2)), content_type
    except Exception:
        return None


def is_url(value: Optional[str]) -> bool:
    return bool(value) and value.startswith(("http://", "https://"))


def upload_comprobante(data: Optional[str], prefix: str = "op") -> Optional[str]:
    """
    Sube una foto de comprobante.
    - data: data URL base64 (formato 'data:image/...;base64,...') o ya una URL http(s).
    - prefix: prefijo del nombre del archivo (ej "op", "cheque").

    Devuelve:
    - URL pública si S3/R2 configurado y subida exitosa.
    - El data URL original si no hay S3 configurado (fallback).
    - None si data es None/vacío.
    - El input tal cual si ya era una URL.
    """
    if not data:
        return None
    if is_url(data):
        return data
    if not _is_configured():
        return data

    parsed = _parse_data_url(data)
    if not parsed:
        logger.warning("upload_comprobante: data no es data URL válido, devolviendo tal cual")
        return data
    raw, content_type = parsed
    ext = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}.get(content_type, "bin")
    key = f"{prefix}/{uuid.uuid4().hex}.{ext}"

    try:
        _client().put_object(
            Bucket=os.getenv("S3_BUCKET"),
            Key=key,
            Body=raw,
            ContentType=content_type,
            CacheControl="public, max-age=31536000, immutable",
        )
    except Exception as ex:
        logger.exception("Error subiendo a S3/R2, fallback a base64: %s", ex)
        return data

    base = os.getenv("S3_PUBLIC_URL", "").rstrip("/")
    return f"{base}/{key}"
