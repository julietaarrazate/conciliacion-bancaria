"""
Smoke test extendido: prueba el merge de UM detectando duplicados.

Sube el extracto, despues sube el MISMO extracto como UM (esperando 100% duplicados),
despues lista movimientos con filtros tipo Excel.

Variables de entorno:
    API_URL           URL del backend (default http://localhost:8000)
    SMOKE_EMAIL       usuario de prueba (obligatoria)
    SMOKE_PASSWORD    contraseña del usuario de prueba (obligatoria)
    SMOKE_EXTRACTO    ruta a un extracto .xlsx (obligatoria)
    SMOKE_PLANILLA_2  ruta a una planilla de cliente (opcional)
    SMOKE_CLIENTE_2   nombre del cliente de esa planilla (default "Cliente Norte")
"""
import os
import sys
import requests
from pathlib import Path

BASE_URL = os.getenv("API_URL", "http://localhost:8000")
SMOKE_EMAIL = os.getenv("SMOKE_EMAIL", "")
SMOKE_PASSWORD = os.getenv("SMOKE_PASSWORD", "")
EXTRACTO = Path(os.getenv("SMOKE_EXTRACTO", "")) if os.getenv("SMOKE_EXTRACTO") else None
PLANILLA = Path(os.getenv("SMOKE_PLANILLA_2", "")) if os.getenv("SMOKE_PLANILLA_2") else None
CLIENTE = os.getenv("SMOKE_CLIENTE_2", "Cliente Norte")


def fail(m):
    print(f"[FAIL] {m}")
    sys.exit(1)


def ok(m):
    print(f"[OK] {m}")


def main():
    print("=" * 60)
    print("SMOKE TEST UM + FILTROS")
    print("=" * 60)

    if not SMOKE_EMAIL or not SMOKE_PASSWORD:
        fail("definí SMOKE_EMAIL y SMOKE_PASSWORD (usuario de prueba)")

    # login
    r = requests.post(f"{BASE_URL}/auth/login", json={"email": SMOKE_EMAIL, "password": SMOKE_PASSWORD})
    if not r.ok:
        fail(f"login: {r.text}")
    token = r.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    ok("login admin")

    # subir extracto
    if EXTRACTO is None or not EXTRACTO.is_file():
        fail(f"definí SMOKE_EXTRACTO con la ruta a un extracto .xlsx existente (actual: {EXTRACTO})")

    with open(EXTRACTO, "rb") as f:
        r = requests.post(
            f"{BASE_URL}/extractos/upload",
            headers=h,
            files={"file": (EXTRACTO.name, f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            timeout=60
        )
    if not r.ok:
        fail(f"upload: {r.text[:200]}")
    extracto_id = r.json()["id"]
    total_inicial = len(r.json()["movimientos"])
    ok(f"extracto subido id={extracto_id} con {total_inicial} movimientos")

    # subir el MISMO archivo como UM (deberian ser todos duplicados)
    with open(EXTRACTO, "rb") as f:
        r = requests.post(
            f"{BASE_URL}/extractos/{extracto_id}/agregar-um",
            headers=h,
            files={"file": (EXTRACTO.name, f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            timeout=60
        )
    if not r.ok:
        fail(f"agregar-um: {r.text[:200]}")
    s = r.json()
    print(f"     UM: agregados={s['agregados']} duplicados={s['duplicados']} total_recibido={s['total_recibido']}")
    if s["agregados"] != 0:
        fail(f"se esperaban 0 agregados (todos duplicados), agrego {s['agregados']}")
    if s["duplicados"] != total_inicial:
        fail(f"se esperaban {total_inicial} duplicados, hubo {s['duplicados']}")
    ok(f"UM detecto correctamente {s['duplicados']} duplicados (no agrego nada)")

    # subir planilla y conciliar para tener cliente_acreditado
    planilla_path = PLANILLA
    if planilla_path is not None and planilla_path.is_file():
        with open(planilla_path, "rb") as f:
            r = requests.post(
                f"{BASE_URL}/planillas/upload",
                headers=h,
                files={"file": (planilla_path.name, f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                params={"cliente_nombre": CLIENTE, "extracto_id": extracto_id},
                timeout=60
            )
        if not r.ok:
            fail(f"upload planilla {CLIENTE}: {r.text[:200]}")
        pid = r.json()["id"]
        ok(f"planilla {CLIENTE} subida id={pid}")

        r = requests.post(f"{BASE_URL}/planillas/{pid}/conciliar", headers=h, params={"fecha_acred": "hoy"})
        if not r.ok:
            fail(f"conciliar: {r.text[:200]}")
        ok(f"conciliacion OK: {r.json()}")

    # filtros
    print()
    print("--- Filtros ---")

    r = requests.get(f"{BASE_URL}/extractos/{extracto_id}/movimientos", headers=h, params={"limit": 1000})
    if not r.ok:
        fail(f"movimientos sin filtro: {r.text[:200]}")
    ok(f"sin filtros: total={r.json()['total']}")

    r = requests.get(f"{BASE_URL}/extractos/{extracto_id}/movimientos", headers=h,
                     params={"cliente": CLIENTE, "limit": 1000})
    if not r.ok:
        fail(f"filtro cliente: {r.text[:200]}")
    ok(f"cliente={CLIENTE}: total={r.json()['total']}")

    r = requests.get(f"{BASE_URL}/extractos/{extracto_id}/movimientos", headers=h,
                     params={"sin_acreditar": "true", "limit": 1000})
    if not r.ok:
        fail(f"sin_acreditar: {r.text[:200]}")
    ok(f"sin_acreditar=true: total={r.json()['total']}")

    r = requests.get(f"{BASE_URL}/extractos/{extracto_id}/movimientos", headers=h,
                     params={"sin_acreditar": "false", "limit": 1000})
    ok(f"sin_acreditar=false (acreditados): total={r.json()['total']}")

    # listar extractos
    r = requests.get(f"{BASE_URL}/extractos", headers=h)
    if not r.ok:
        fail(f"list extractos: {r.text[:200]}")
    ok(f"lista extractos: {r.json()['total']}")

    print()
    print("=" * 60)
    print("TODO OK")
    print("=" * 60)


if __name__ == "__main__":
    main()
