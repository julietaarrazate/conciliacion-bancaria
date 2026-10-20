"""Error de entrada del lector de extractos PDF."""

from __future__ import annotations


class ExtractoPdfError(Exception):
    """Problema irrecuperable con el archivo (no es PDF, está dañado, tiene
    contraseña, demasiadas páginas). `status` es el código HTTP sugerido.

    Todo lo demás (no se encontraron movimientos, la IA no está, la IA falló)
    NO lanza: se informa en `alertas` del resultado."""

    def __init__(self, mensaje: str, status: int = 400):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.status = status

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.mensaje
