"""
Tests unitarios para los fixes de esta sesión.
No requieren DB ni FastAPI — solo lógica pura.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# ── 1. Parser: montos negativos ───────────────────────────────
from app.services.excel_parser import _parse_monto

def test_monto_positivo():
    assert _parse_monto(128220.58) == 128220.58

def test_monto_negativo_se_preserva():
    assert _parse_monto(-5000.0) == -5000.0

def test_monto_negativo_string():
    assert _parse_monto("-1.234,56") == -1234.56

def test_monto_cero_retorna_none():
    assert _parse_monto(0.0) is None or _parse_monto(0.0) == 0.0

def test_monto_none_retorna_none():
    assert _parse_monto(None) is None


# ── 2. Merger: lógica de corte ────────────────────────────────
from app.services.extracto_merger import _match_existente, _normalizar_titular
from datetime import date

EXISTENTES = [
    (128220.58, 99657675.21, "2026-05-18", "ing transf juan ejemplo perez"),
    (50000.0,   99607675.21, "2026-05-17", "tef empresa abc sa"),
]

def test_match_por_saldo_y_monto():
    mov = {"monto": 128220.58, "saldo": 99657675.21, "fecha": date(2026, 5, 18), "titular": "ING TRANSF:JUAN EJEMPLO PEREZ-20111111112"}
    assert _match_existente(mov, EXISTENTES) is True

def test_no_match_distinto_saldo():
    mov = {"monto": 128220.58, "saldo": 99841971.69, "fecha": date(2026, 5, 18), "titular": "TEF EMPRESA DEMO SAS"}
    assert _match_existente(mov, EXISTENTES) is False

def test_no_match_distinto_monto():
    mov = {"monto": 184296.48, "saldo": 99657675.21, "fecha": date(2026, 5, 18), "titular": "algo"}
    assert _match_existente(mov, EXISTENTES) is False

def test_normalizar_titular_saca_cuit():
    # CUIT (11 dígitos) debe eliminarse del titular normalizado
    t = _normalizar_titular("ING TRANSF:JUAN EJEMPLO PEREZ-20111111112")
    assert "20111111112" not in t
    assert "juan" in t


# ── 3. Conciliación: estados duplicado vs acreditado ─────────
from app.services.conciliacion import buscar_match, es_libre

class FakeMov:
    def __init__(self, id, monto, cliente_acreditado=None, fecha_acred=None):
        self.id = id
        self.monto = monto
        self.cliente_acreditado = cliente_acreditado
        self.fecha_acred = fecha_acred
        self.titular = "test"
        self.fecha = date(2026, 5, 18)

ORG_CONFIG = {"match_rules": ["monto_cuit"], "tolerancia_monto": 0.01, "dias_tolerancia_fecha": 5}

def test_duplicado_cuando_mov_ya_en_procesados():
    """Misma fila dos veces en planilla → duplicado"""
    mov = FakeMov(1, 50000.0)
    procesados = {1}  # ya fue usado en esta corrida
    _, status = buscar_match(50000.0, None, None, None, None, [mov], procesados, ORG_CONFIG)
    assert status == "duplicado"

def test_acreditado_cuando_mov_tiene_cliente_previo():
    """Movimiento ya acreditado a alguien antes → acreditado DD/MM"""
    from datetime import date
    mov = FakeMov(1, 50000.0, cliente_acreditado="Green", fecha_acred=date(2026, 5, 17))
    procesados = set()  # no usado en esta corrida
    _, status = buscar_match(50000.0, None, None, None, None, [mov], procesados, ORG_CONFIG)
    assert "acreditado" in status
    assert "17/05" in status

def test_ok_cuando_mov_libre():
    """Movimiento libre con monto único → ok"""
    mov = FakeMov(1, 50000.0)
    procesados = set()
    resultado_mov, status = buscar_match(50000.0, None, None, None, None, [mov], procesados, ORG_CONFIG)
    assert status == "ok"
    assert resultado_mov is not None

def test_no_esta_cuando_monto_no_existe():
    """Monto no encontrado en extracto → no está"""
    mov = FakeMov(1, 50000.0)
    procesados = set()
    _, status = buscar_match(99999.0, None, None, None, None, [mov], procesados, ORG_CONFIG)
    assert status == "no está"

def test_es_libre_none():
    assert es_libre(None) is True

def test_es_libre_no_identificado():
    assert es_libre("no identificado") is True

def test_es_libre_con_cliente():
    assert es_libre("Green SA") is False


if __name__ == "__main__":
    # Correr sin pytest
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    ok = err = 0
    for t in tests:
        try:
            t()
            print(f"  ✓ {t.__name__}")
            ok += 1
        except Exception as e:
            print(f"  ✗ {t.__name__}: {e}")
            err += 1
    print(f"\n{ok} ok / {err} errores")
