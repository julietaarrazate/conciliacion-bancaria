"""
Smoke test E2E: prueba el flujo completo contra un backend corriendo.

Uso:
    1. En una terminal: uvicorn app.main:app --port 8000
    2. En otra:        python smoke_test.py

Variables de entorno:
    API_URL            URL del backend (default http://localhost:8000)
    SMOKE_EMAIL        usuario de prueba (obligatoria)
    SMOKE_PASSWORD     contraseña del usuario de prueba (obligatoria)
    SMOKE_EXTRACTO     ruta a un extracto .xlsx (opcional; sin ella se saltea la carga)
    SMOKE_PLANILLA_1   ruta a una planilla de cliente (opcional)
    SMOKE_PLANILLA_2   ruta a otra planilla de cliente (opcional)
    SMOKE_CLIENTE_1 / SMOKE_CLIENTE_2   nombre del cliente de cada planilla

Hace:
    - Login admin
    - GET /me
    - POST /extractos/upload (si SMOKE_EXTRACTO apunta a un archivo)
    - POST /planillas/upload (si SMOKE_PLANILLA_n apunta a un archivo)
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

SMOKE_EMAIL = os.getenv("SMOKE_EMAIL", "")
SMOKE_PASSWORD = os.getenv("SMOKE_PASSWORD", "")

# Archivos para el smoke test (opcionales), configurables con variables de entorno.
EXTRACTO_PATH = os.getenv("SMOKE_EXTRACTO", "")
PLANILLAS = [
    (os.getenv("SMOKE_PLANILLA_1", ""), os.getenv("SMOKE_CLIENTE_1", "Cliente Este")),
    (os.getenv("SMOKE_PLANILLA_2", ""), os.getenv("SMOKE_CLIENTE_2", "Cliente Norte")),
]


def _archivo_existe(path) -> bool:
    return bool(path) and Path(path).is_file()


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
    if not _archivo_existe(path):
        print(f"[skip] extracto no configurado o inexistente: {path or '(SMOKE_EXTRACTO vacia)'}")
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
    if not _archivo_existe(path):
        print(f"[skip] planilla {cliente} no configurada o inexistente")
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

    if not SMOKE_EMAIL or not SMOKE_PASSWORD:
        fail("definí SMOKE_EMAIL y SMOKE_PASSWORD (usuario de prueba) antes de correr el smoke test")

    wait_for_backend()

    token = login(SMOKE_EMAIL, SMOKE_PASSWORD)
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
