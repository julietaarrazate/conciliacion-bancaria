"""Tests del helper de timezone Argentina (ART, UTC-3).

El bug que corrige: el servidor corre en UTC; date.today() devolvía la fecha de
ayer entre la medianoche y las 3 AM hora argentina, dejando pagos/cheques/asientos
con la fecha equivocada en el Libro Diario.
"""
from datetime import date, datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from app.services.tz import hoy_art, now_art, ARG_TZ


def test_hoy_art_devuelve_date():
    assert isinstance(hoy_art(), date)


def test_now_art_es_timezone_aware():
    n = now_art()
    assert n.tzinfo is not None


def test_hoy_art_coincide_con_fecha_argentina():
    esperado = datetime.now(ZoneInfo("America/Argentina/Buenos_Aires")).date()
    assert hoy_art() == esperado


def test_art_es_utc_menos_3():
    # A las 01:00 UTC, en Argentina son las 22:00 del día ANTERIOR.
    utc_1am = datetime(2026, 6, 2, 1, 0, tzinfo=timezone.utc)
    art = utc_1am.astimezone(ARG_TZ)
    assert art.date() == date(2026, 6, 1)
    assert art.hour == 22
