"""Schemas del importador de extractos en PDF (`/extractos-pdf`).

Convención de la API: **los montos viajan como string** con punto decimal y dos
decimales (`"-1234.56"`), nunca como float, para no perder centavos en el JSON.
En la entrada (`ConfirmarExtractoPdfIn`) se aceptan string o número: los valida
el servicio fila por fila para poder responder un 422 con un mensaje claro
("Fila 3: …") en vez del detalle en forma de lista de Pydantic.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, List, Optional, Union

from pydantic import BaseModel, Field

Dinero = Optional[str]
DineroIn = Union[str, int, float, None]


# ── Salida ──────────────────────────────────────────────────────────

class MovimientoPdfOut(BaseModel):
    fecha: Optional[str] = None            # ISO "YYYY-MM-DD"
    descripcion: str = ""
    monto: Dinero = None                   # crédito +, débito −
    saldo: Dinero = None
    pagina: Optional[int] = None
    dudosa: bool = False
    motivos: List[str] = Field(default_factory=list)


class CuadreExtractoPdfOut(BaseModel):
    saldo_inicial: Dinero = None
    saldo_inicial_inferido: bool = False
    saldo_final: Dinero = None
    saldo_final_inferido: bool = False
    total_creditos: Dinero = "0.00"
    total_debitos: Dinero = "0.00"
    cantidad: int = 0
    saldo_final_calculado: Dinero = None
    diferencia: Dinero = None
    cierra: bool = False
    filas_con_salto: List[int] = Field(default_factory=list)


class AlertaExtractoPdf(BaseModel):
    nivel: str = "aviso"                   # info | aviso | error
    codigo: str = ""
    mensaje: str = ""


class DuplicadoExtractoPdf(BaseModel):
    tipo: str                              # mismo_archivo | mismos_movimientos | solapado
    extracto_id: int
    nombre: Optional[str] = None
    banco: Optional[str] = None
    coincidencias: int = 0
    nuevos: int = 0
    anteriores: int = 0                    # filas del PDF más viejas que el extracto que no están en él
    archivado: bool = False                # el extracto está archivado: no se le pueden agregar filas


class BorradorExtractoOut(BaseModel):
    id: int
    estado: str
    nombre_archivo: str
    creado_at: Optional[datetime] = None
    metodo: Optional[str] = None           # molde | automatico | ia
    banco: Optional[str] = None
    banco_clave: Optional[str] = None
    # Cómo se reconoció el banco: {banco_clave, nombre, confianza, motivo, origen,
    # conflicto, pedir_confirmacion} (ver services/banco_identificacion.py).
    banco_deteccion: Optional[dict] = None
    periodo_desde: Optional[date] = None
    periodo_hasta: Optional[date] = None
    saldo_inicial: Dinero = None
    saldo_final: Dinero = None
    orden: str = "asc"
    paginas: int = 0
    escaneado: bool = False
    movimientos: List[MovimientoPdfOut] = Field(default_factory=list)
    cuadre: CuadreExtractoPdfOut = Field(default_factory=CuadreExtractoPdfOut)
    alertas: List[AlertaExtractoPdf] = Field(default_factory=list)
    duplicado: Optional[DuplicadoExtractoPdf] = None
    extracto_id: Optional[int] = None
    ia_disponible: bool = False
    ia_usada: bool = False
    puede_aprender: bool = False
    error: Optional[str] = None


class BorradorExtractoResumen(BaseModel):
    id: int
    estado: str
    nombre_archivo: str
    creado_at: Optional[datetime] = None
    metodo: Optional[str] = None
    banco: Optional[str] = None
    periodo_desde: Optional[date] = None
    periodo_hasta: Optional[date] = None
    cantidad: int = 0
    cierra: bool = False
    extracto_id: Optional[int] = None
    error: Optional[str] = None


class BorradoresExtractoPdfOut(BaseModel):
    items: List[BorradorExtractoResumen]


class MoldeExtractoPdfOut(BaseModel):
    id: int
    banco: Optional[str] = None
    banco_clave: Optional[str] = None
    origen: Optional[str] = None           # automatico | ia
    confirmaciones: int = 0
    creado_at: Optional[datetime] = None
    ultimo_uso_at: Optional[datetime] = None


class MoldesExtractoPdfOut(BaseModel):
    items: List[MoldeExtractoPdfOut]


class OkOut(BaseModel):
    ok: bool = True


# ── Confirmación ────────────────────────────────────────────────────

class MovimientoConfirmarIn(BaseModel):
    fecha: Optional[str] = None
    descripcion: Optional[str] = None
    monto: DineroIn = None
    saldo: DineroIn = None


class ConfirmarExtractoPdfIn(BaseModel):
    # En el MISMO orden en que el borrador los mostró (ver `orden` del borrador).
    movimientos: List[MovimientoConfirmarIn] = Field(default_factory=list)
    saldo_inicial: DineroIn = None
    saldo_final: DineroIn = None
    banco: Optional[str] = None
    # Banco elegido en la pantalla de revisión (clave interna, p. ej. "galicia").
    banco_clave: Optional[str] = None
    nombre: Optional[str] = None
    destino: str = "nuevo"                 # nuevo | existente
    extracto_id: Optional[int] = None
    confirmar_sin_cuadre: bool = False


class ConfirmarExtractoPdfOut(BaseModel):
    extracto_id: int
    destino: str
    ya_existia: bool = False
    agregados: int = 0
    duplicados: int = 0
    no_agregados: int = 0                  # filas del PDF que el merge no agregó (anteriores al extracto)
    molde_aprendido: bool = False
    contabilidad_ok: bool = True
    mensaje: str = ""


__all__: List[Any] = [
    "MovimientoPdfOut", "CuadreExtractoPdfOut", "AlertaExtractoPdf", "DuplicadoExtractoPdf",
    "BorradorExtractoOut", "BorradorExtractoResumen", "BorradoresExtractoPdfOut",
    "MoldeExtractoPdfOut", "MoldesExtractoPdfOut", "OkOut",
    "MovimientoConfirmarIn", "ConfirmarExtractoPdfIn", "ConfirmarExtractoPdfOut",
]
