"""Configuration for pytest"""

import sys
from pathlib import Path

import pytest

# Agregar el directorio del backend al path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))


@pytest.fixture(autouse=True)
def _pbkdf2_rapido(monkeypatch):
    """Los tests crean usuarios en cada fixture: con las 600.000 iteraciones de
    producción la suite tarda casi el triple. Acá se hashea con pocas iteraciones
    (el formato y la verificación son los mismos). `test_seguridad_auth.py`
    redefine este fixture para probar el costo real."""
    import app.services.auth as auth_service
    monkeypatch.setattr(auth_service, "PBKDF2_ITERATIONS", 1_000)
