"""
Smoke test extendido: prueba el merge de UM detectando duplicados.

Sube el extracto, despues sube el MISMO extracto como UM (esperando 100% duplicados),
despues lista movimientos con filtros tipo Excel.
"""
import os
import sys
import requests
from pathlib import Path

BASE_URL = os.getenv("API_URL", "http://localhost:8000")
_DESKTOP = os.path.join(os.path.expanduser("~"), "Desktop")
EXTRACTO = Path(os.getenv("SMOKE_EXTRACTO", os.path.join(_DESKTOP, "Extracto Macro", "extracto macro abril.xlsx")))


def fail(m):
    print(f"[FAIL] {m}")
    sys.exit(1)


def ok(m):
    print(f"[OK] {m}")


def main():
    print("=" * 60)
    print("SMOKE TEST UM + FILTROS")
    print("=" * 60)

    # login
    r = requests.post(f"{BASE_URL}/auth/login", json={"email": "admin@demo.com", "password": "admin123"})
    if not r.ok:
        fail(f"login: {r.text}")
    token = r.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    ok("login admin")

    # subir extracto
    if not EXTRACTO.exists():
        fail(f"no existe {EXTRACTO}")

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
    planilla_path = Path(os.getenv("SMOKE_PLANILLA_2", os.path.join(_DESKTOP, "INBOX", "procesados", "Green 28.4.xlsx")))
    if planilla_path.exists():
        with open(planilla_path, "rb") as f:
            r = requests.post(
                f"{BASE_URL}/planillas/upload",
                headers=h,
                files={"file": (planilla_path.name, f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                params={"cliente_nombre": "Green", "extracto_id": extracto_id},
                timeout=60
            )
        if not r.ok:
            fail(f"upload planilla Green: {r.text[:200]}")
        pid = r.json()["id"]
        ok(f"planilla Green subida id={pid}")

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
                     params={"cliente": "Green", "limit": 1000})
    if not r.ok:
        fail(f"filtro cliente: {r.text[:200]}")
    ok(f"cliente=Green: total={r.json()['total']}")

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
