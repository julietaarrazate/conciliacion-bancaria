"""Utilidades de fecha/hora en horario de Argentina (ART, UTC-3).

El servidor corre en UTC (Render). `date.today()` y `datetime.now()` devuelven
la fecha/hora UTC, lo que entre la medianoche y las 3 AM hora argentina genera la
fecha de AYER. Para todas las fechas de NEGOCIO (egresos, cheques, arqueos,
asientos contables) hay que usar estos helpers para que reflejen el día real en
Argentina.

Las marcas de tiempo internas/auditoría (created_at, expiraciones de tokens)
pueden seguir en UTC — eso es correcto y consistente.
"""
from datetime import date, datetime
from zoneinfo import ZoneInfo

ARG_TZ = ZoneInfo("America/Argentina/Buenos_Aires")


def now_art() -> datetime:
    """Fecha y hora actual en Argentina (timezone-aware)."""
    return datetime.now(ARG_TZ)


def hoy_art() -> date:
    """Fecha de hoy en Argentina (no UTC). Usar como default de fechas de negocio."""
    return datetime.now(ARG_TZ).date()
