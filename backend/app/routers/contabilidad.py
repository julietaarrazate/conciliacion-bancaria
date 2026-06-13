"""Router contabilidad — agregador delgado.

Importa los 4 sub-módulos y los incluye bajo el prefijo /contabilidad.
main.py no necesita cambios: sigue haciendo `app.include_router(contabilidad.router)`.

Sub-módulos:
  ctb_plan.py            — /stats, /plan-cuentas, /reglas
  ctb_libro.py           — /asientos/*, /libro-mayor, /sumas-saldo, /balance,
                           /export-config, /asiento-manual, /fix-fechas-utc,
                           /reset-y-rebuild
  ctb_clientes.py        — /clientes-cuentas, /clientes/{id}/cuenta,
                           /clientes/cuentas/crear-faltantes,
                           /recuperar-clientes-borrados
  ctb_ctas_corrientes.py — /cuentas-corrientes, /cuenta-corriente,
                           /cuenta-corriente/exportar-pdf,
                           /backfill-cuentas-corrientes

Helpers compartidos: ctb_common.py (_org_id, _norm_nombre, _cuenta_parent_cliente,
                                    _MODULO_TIPO, _tipo_de_modulo, _STATUS_CONCILIADO)
"""
from fastapi import APIRouter

from .ctb_plan import router as _plan_router
from .ctb_libro import router as _libro_router
from .ctb_clientes import router as _clientes_router
from .ctb_ctas_corrientes import router as _ctas_router

router = APIRouter(prefix="/contabilidad", tags=["contabilidad"])

router.include_router(_plan_router)
router.include_router(_libro_router)
router.include_router(_clientes_router)
router.include_router(_ctas_router)

# Re-exportar helpers para compatibilidad con main.py y otros módulos
# que pudieran importarlos directamente desde contabilidad.
from .ctb_common import _org_id, _norm_nombre, _cuenta_parent_cliente  # noqa: F401
