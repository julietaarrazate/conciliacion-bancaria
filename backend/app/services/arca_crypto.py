"""Cifrado en reposo del certificado y la clave privada ARCA de cada organización.

Cada org sube su propio certificado X.509 y clave privada (par emitido por ARCA
para facturar bajo su CUIT). Son el material más sensible que maneja Cuadra hasta
ahora — nunca se guardan en claro en la DB ni se loguean. Se cifran con Fernet
(AES-128-CBC + HMAC) usando `ARCA_ENCRYPTION_KEY` (env var de Render, igual patrón
que VAPID_PRIVATE_KEY/GEMINI_API_KEY: nunca en el repo).

Sin la key seteada, el módulo ARCA rechaza explícitamente cargar certificados
(no hay fallback en claro — a diferencia de otros módulos opt-in, acá degradar
silenciosamente significaría guardar una clave privada sin cifrar).
"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


class ArcaCryptoError(Exception):
    """Falta o es inválida la ARCA_ENCRYPTION_KEY, o el valor cifrado es ilegible."""


def _fernet() -> Fernet:
    key = get_settings().arca_encryption_key.strip()
    if not key:
        raise ArcaCryptoError(
            "ARCA_ENCRYPTION_KEY no está configurada — no se puede cifrar/descifrar "
            "el certificado ARCA. Generarla y setearla en Render antes de cargar certificados."
        )
    try:
        return Fernet(key.encode())
    except Exception as ex:
        raise ArcaCryptoError(f"ARCA_ENCRYPTION_KEY inválida: {ex}")


def encriptar(texto_plano: str) -> str:
    """Cifra un string (PEM de certificado o clave privada) → string base64 cifrado."""
    if not texto_plano:
        return ""
    return _fernet().encrypt(texto_plano.encode()).decode()


def desencriptar(texto_cifrado: str) -> str:
    """Descifra un valor previamente cifrado con `encriptar`. Lanza ArcaCryptoError si no se puede."""
    if not texto_cifrado:
        return ""
    try:
        return _fernet().decrypt(texto_cifrado.encode()).decode()
    except InvalidToken:
        raise ArcaCryptoError("No se pudo descifrar el certificado/clave ARCA (token inválido).")
