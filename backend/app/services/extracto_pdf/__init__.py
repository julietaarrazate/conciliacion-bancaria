"""Lector de extractos bancarios en PDF (puro, sin base de datos).

Uso:

    from app.services.extracto_pdf import leer_extracto_pdf, ExtractoPdfError, validar_saldos

    resultado = leer_extracto_pdf(contenido, moldes=moldes_de_la_org, usar_ia=False)

Contrato completo de entrada/salida en `lector.leer_extracto_pdf` y en la
documentación del módulo (`docs/business/` del feature). Resumen de la salida:
`metodo` ("molde" | "automatico" | "ia" | None), `molde_id`, `banco_clave`,
`paginas`, `escaneado`, `orden` ("asc" | "desc"), `periodo_desde/hasta`,
`saldo_inicial/final` (Decimal), `movimientos` (fecha, descripcion, monto con
signo, saldo, pagina, dudosa, motivos — en el orden del PDF), `cuadre` (salida de
`validar_saldos`), `alertas`, `aprendizaje` (candidato a molde), `ia_usada`,
`ia_disponible`, `banco_deteccion` (cómo se reconoció el banco: CBU, CUIT,
formato, confirmado antes o nombre — ver `services/banco_identificacion.py`).
`nombre_archivo` (opcional) se usa para buscar el CBU o el banco en el nombre.
"""

from .errores import ExtractoPdfError
from .ia import ia_disponible
from .lector import leer_extracto_pdf
from .saldos import formatear_pesos, marcar_dudosas, validar_saldos
from .texto import MAX_PAGINAS

__all__ = [
    "ExtractoPdfError",
    "MAX_PAGINAS",
    "formatear_pesos",
    "ia_disponible",
    "leer_extracto_pdf",
    "marcar_dudosas",
    "validar_saldos",
]
