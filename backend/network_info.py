"""Imprime la URL del backend para usar desde el celular en la misma WiFi"""

import socket


def get_local_ip() -> str:
    """Detecta IP local en la red WiFi/LAN"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


if __name__ == "__main__":
    ip = get_local_ip()
    print()
    print("=" * 50)
    print("  URLs del backend")
    print("=" * 50)
    print(f"  Web local (esta PC):    http://localhost:8000")
    print(f"  Celular (misma WiFi):   http://{ip}:8000")
    print(f"  Swagger:                http://{ip}:8000/docs")
    print("=" * 50)
    print()
    print(f"En la app movil, ir a Ajustes y poner: http://{ip}:8000")
    print()
