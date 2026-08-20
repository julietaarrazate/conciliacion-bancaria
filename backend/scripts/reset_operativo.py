#!/usr/bin/env python3
"""Reset de datos OPERATIVOS por organización — arrancar limpio sin perder maestros.

Vacía lo transaccional (extractos, movimientos, planillas, conciliaciones,
asientos ⇒ saldos de cuenta corriente en cero, cheques, egresos, arqueos,
liquidaciones, comprobantes/proyecciones impositivas, etc.) CONSERVANDO clientes,
usuarios, plan de cuentas + reglas, portadores, empleados y toda la config.

Reutiliza el MISMO service de producción (app/services/reset_operativo.py) para
que el borrado nunca se desincronice de las reglas del modelo de datos.

Uso:
    # Ver qué se borraría, sin tocar nada (recomendado primero):
    python backend/scripts/reset_operativo.py --org 1 2 --dry-run

    # Ejecutar de verdad (pide confirmación tipeando el texto exacto):
    python backend/scripts/reset_operativo.py --org 1 2

    # Sin prompt interactivo (para automatización) y sin borrar auditoría:
    python backend/scripts/reset_operativo.py --org 1 --no-auditoria --yes

IMPORTANTE: es destructivo e irreversible sobre la base apuntada por DATABASE_URL.
Hacé un backup antes (en Neon: crear un branch = snapshot restaurable).
"""
import argparse
import os
import sys

# Permitir importar app.* corriendo desde la raíz del repo o desde backend/.
_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _BACKEND)

from app.database import SessionLocal  # noqa: E402
from app.services.reset_operativo import reset_datos_operativos  # noqa: E402

_CONFIRM = "BORRAR OPERATIVO"


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset de datos operativos por organización.")
    parser.add_argument("--org", type=int, nargs="+", required=True,
                        help="ID(s) de organización a limpiar (ej: --org 1 2)")
    parser.add_argument("--no-auditoria", action="store_true",
                        help="Conservar el log de auditoría (por defecto se borra)")
    parser.add_argument("--dry-run", action="store_true",
                        help="No borra nada; sólo muestra cuántas filas caerían")
    parser.add_argument("--yes", action="store_true",
                        help="No pedir confirmación interactiva (para automatización)")
    args = parser.parse_args()

    incluir_auditoria = not args.no_auditoria
    orgs = args.org

    print(f"Base de datos: {os.getenv('DATABASE_URL', 'sqlite:///./conciliacion.db')[:60]}…")
    print(f"Organizaciones a limpiar: {orgs}")
    print(f"Incluir auditoría: {incluir_auditoria}")
    print(f"Modo: {'DRY-RUN (no borra)' if args.dry_run else 'EJECUCIÓN REAL'}\n")

    db = SessionLocal()
    try:
        if args.dry_run:
            resultado = reset_datos_operativos(
                db, orgs, incluir_auditoria=incluir_auditoria, dry_run=True)
            _print_report(resultado, "Filas que se borrarían")
            print("\nDry-run: no se modificó nada.")
            return 0

        if not args.yes:
            print(f"⚠️  Esto es IRREVERSIBLE. Escribí '{_CONFIRM}' para continuar:")
            if input("> ").strip() != _CONFIRM:
                print("Cancelado.")
                return 1

        resultado = reset_datos_operativos(
            db, orgs, incluir_auditoria=incluir_auditoria, dry_run=False)
        db.commit()
        _print_report(resultado, "Filas borradas")
        print("\n✅ Reset completado. Maestros y plan de cuentas conservados.")
        return 0
    except Exception as e:  # pragma: no cover - manejo defensivo de CLI
        db.rollback()
        print(f"\n❌ Error, se hizo rollback (no se borró nada): {e}")
        return 2
    finally:
        db.close()


def _print_report(resultado: dict, titulo: str) -> None:
    print(f"{titulo}:")
    if not resultado:
        print("  (nada — las tablas ya estaban vacías para esas organizaciones)")
        return
    total = 0
    for tabla, n in sorted(resultado.items(), key=lambda kv: -kv[1]):
        print(f"  {tabla:<32} {n:>8}")
        total += n
    print(f"  {'TOTAL':<32} {total:>8}")


if __name__ == "__main__":
    raise SystemExit(main())
