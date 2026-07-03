"""
Smoke test E2E: prueba el flujo completo contra un backend corriendo.

Uso:
    1. En una terminal: uvicorn app.main:app --port 8000
    2. En otra:        python smoke_test.py

Hace:
    - Login admin
    - GET /me
    - POST /extractos/upload (con extracto real si existe)
    - POST /planillas/upload (con planilla real si existe)
    - POST /planillas/{id}/conciliar
    - GET /historial/planillas
    - GET /auditoria
"""

import os
import sys
import time
import requests
from pathlib import Path

BASE_URL = os.getenv("API_URL", "http://localhost:8000")

# Rutas a archivos reales para el smoke test (opcionales).
# Configurables con variables de entorno; por defecto usan la carpeta del usuario.
_DESKTOP = os.path.join(os.path.expanduser("~"), "Desktop")
EXTRACTO_PATH = Path(os.getenv("SMOKE_EXTRACTO", os.path.join(_DESKTOP, "Extracto Macro", "extracto macro abril.xlsx")))
PLANILLAS = [
    (os.getenv("SMOKE_PLANILLA_1", os.path.join(_DESKTOP, "INBOX", "procesados", "alojando.xlsx")), "Alojando"),
    (os.getenv("SMOKE_PLANILLA_2", os.path.join(_DESKTOP, "INBOX", "procesados", "Green 28.4.xlsx")), "Green"),
]


def fail(msg):
    print(f"\n[FAIL] {msg}")
    sys.exit(1)


def ok(msg):
    print(f"[OK] {msg}")


def wait_for_backend():
    print(f"Esperando backend en {BASE_URL} ...")
    for _ in range(20):
        try:
            r = requests.get(f"{BASE_URL}/health", timeout=2)
            if r.ok and r.json().get("status") == "healthy":
                ok("backend respondiendo")
                return
        except Exception:
            pass
        time.sleep(1)
    fail(f"backend no responde en {BASE_URL}")


def login(email, password):
    r = requests.post(
        f"{BASE_URL}/auth/login",
        json={"email": email, "password": password},
        timeout=10
    )
    if not r.ok:
        fail(f"login: {r.status_code} {r.text}")
    data = r.json()
    ok(f"login {email} -> role={data['user']['role']}")
    return data["access_token"]


def get_me(token):
    r = requests.get(
        f"{BASE_URL}/me",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10
    )
    if not r.ok:
        fail(f"GET /me: {r.status_code}")
    ok(f"/me -> {r.json()['full_name']}")


def upload_extracto(token, path):
    if not Path(path).exists():
        print(f"[skip] extracto no existe: {path}")
        return None

    with open(path, "rb") as f:
        r = requests.post(
            f"{BASE_URL}/extractos/upload",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": (Path(path).name, f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            timeout=60
        )
    if not r.ok:
        fail(f"upload extracto: {r.status_code} {r.text[:200]}")
    data = r.json()
    ok(f"extracto cargado -> id={data['id']} movimientos={len(data['movimientos'])}")
    return data["id"]


def upload_planilla(token, path, cliente, extracto_id):
    if not Path(path).exists():
        print(f"[skip] planilla {cliente} no existe")
        return None

    with open(path, "rb") as f:
        r = requests.post(
            f"{BASE_URL}/planillas/upload",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": (Path(path).name, f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            params={"cliente_nombre": cliente, "extracto_id": extracto_id},
            timeout=60
        )
    if not r.ok:
        fail(f"upload planilla {cliente}: {r.status_code} {r.text[:200]}")
    data = r.json()
    ok(f"planilla {cliente} cargada -> id={data['id']} filas={len(data['rows'])}")
    return data["id"]


def conciliar(token, planilla_id, cliente):
    r = requests.post(
        f"{BASE_URL}/planillas/{planilla_id}/conciliar",
        headers={"Authorization": f"Bearer {token}"},
        params={"fecha_acred": "hoy"},
        timeout=60
    )
    if not r.ok:
        fail(f"conciliar {cliente}: {r.status_code} {r.text[:200]}")
    data = r.json()
    print(f"     {cliente}: ok={data['acreditadas']} no_esta={data['no_encontradas']} dup={data['duplicadas']} sin_datos={data['sin_datos']} total={data['filas_procesadas']}")
    ok(f"conciliacion {cliente} completada")


def get_historial(token):
    r = requests.get(
        f"{BASE_URL}/historial/planillas",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10
    )
    if not r.ok:
        fail(f"historial: {r.status_code}")
    data = r.json()
    ok(f"historial -> {data['total']} planillas")


def get_auditoria(token):
    r = requests.get(
        f"{BASE_URL}/auditoria",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10
    )
    if not r.ok:
        fail(f"auditoria: {r.status_code} {r.text[:200]}")
    data = r.json()
    ok(f"auditoria -> {data['total']} logs")
    if data["items"]:
        print("   ultimos 3:")
        for log in data["items"][:3]:
            print(f"     - {log['accion']:10s} {log['tabla']:25s} #{log['registro_id']} por {log.get('usuario_nombre', '?')}")


def main():
    print("=" * 60)
    print(f"SMOKE TEST contra {BASE_URL}")
    print("=" * 60)

    wait_for_backend()

    token = login("admin@demo.com", "admin123")
    get_me(token)

    extracto_id = upload_extracto(token, EXTRACTO_PATH)

    if extracto_id:
        for path, cliente in PLANILLAS:
            planilla_id = upload_planilla(token, path, cliente, extracto_id)
            if planilla_id:
                conciliar(token, planilla_id, cliente)

    get_historial(token)
    get_auditoria(token)

    print()
    print("=" * 60)
    print("TODO OK")
    print("=" * 60)


if __name__ == "__main__":
    main()
