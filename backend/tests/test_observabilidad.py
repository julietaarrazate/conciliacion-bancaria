"""Observabilidad: el middleware mide cada request y expone X-Process-Time,
y loguea como WARNING las que superan settings.slow_request_ms. Esto es lo que
permite ver qué endpoints están lentos en los logs de Render con datos reales."""
import logging

from fastapi.testclient import TestClient

from app.main import app
from app.config import get_settings

settings = get_settings()  # singleton (lru_cache) — la misma instancia que usa main.py


def test_respuesta_incluye_header_x_process_time():
    c = TestClient(app)
    r = c.get("/health")
    assert r.status_code == 200
    assert "X-Process-Time" in r.headers
    assert r.headers["X-Process-Time"].endswith("ms")


def test_request_lenta_se_loguea_como_warning(caplog, monkeypatch):
    # Umbral en 0ms → cualquier request cuenta como lenta y debe loguearse.
    monkeypatch.setattr(settings, "slow_request_ms", 0)
    c = TestClient(app)
    with caplog.at_level(logging.WARNING):
        c.get("/health")
    assert any("SLOW" in rec.message and "/health" in rec.getMessage() for rec in caplog.records)
