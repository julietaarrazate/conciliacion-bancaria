"""Comparar el Excel "Mis Comprobantes" de ARCA con lo cargado en Cuadra.

Antes de importar, muestra qué falta, qué ya está (y si coincide el importe) y
qué está cargado en Cuadra pero ARCA no tiene. No se conecta a ARCA: recibe las
filas de `parsear_mis_comprobantes` (el Excel que se baja de la web).

Misma identidad de comprobante que el unique `uq_comprobante_iva_dedup`:
(dirección, tipo, punto de venta, número, CUIT de la contraparte), en la org.

`comparar` es read-only. `importar_filas` carga (la usan la importación de IVA y
la masiva de Procesos masivos).
"""

import re
import uuid
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.iva_liquidacion import ComprobanteIva
from app.services.iva_liquidacion_service import es_nota_credito

_DOS = Decimal("0.01")


def _solo_digitos(cuit: Optional[str]) -> str:
    return re.sub(r"\D", "", str(cuit or ""))


def clave_comprobante(tipo_codigo, punto_venta, numero, cuit) -> str:
    """Identidad del comprobante dentro de una dirección: "tipo-pv-número-cuit"."""
    return f"{int(tipo_codigo or 0)}-{int(punto_venta or 0)}-{int(numero or 0)}-{_solo_digitos(cuit)}"


def clave_de_fila(fila: Dict[str, Any]) -> str:
    return clave_comprobante(fila["tipo_codigo"], fila["punto_venta"], fila["numero"],
                             fila["cuit_contraparte"])


def _d(v) -> Decimal:
    return (v if isinstance(v, Decimal) else Decimal(str(v or 0))).quantize(_DOS)


def comparar(
    db: Session, org_id: int, direccion: str, periodo: str, filas: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Clasifica las filas del Excel contra los comprobantes del período en Cuadra.

    Returns:
        faltantes: filas del período que no están en Cuadra (con "clave").
        iva_faltante: IVA de los faltantes (las notas de crédito restan).
        ya_cargados: filas que ya están, con `comprobante_id`, `total_iva_cuadra`,
            `imp_total_cuadra` e `importe_distinto` (IVA o total no coinciden).
        solo_en_cuadra: ComprobanteIva del período que el Excel no trae.
        fuera_de_periodo: filas con fecha de otro mes (no se comparan).
    """
    en_cuadra = (
        db.query(ComprobanteIva)
        .filter(ComprobanteIva.organizacion_id == org_id,
                ComprobanteIva.direccion == direccion,
                ComprobanteIva.periodo == periodo)
        .order_by(ComprobanteIva.fecha, ComprobanteIva.id)
        .all()
    )
    por_clave = {
        clave_comprobante(c.tipo_codigo, c.punto_venta, c.numero, c.cuit_contraparte): c
        for c in en_cuadra
    }

    faltantes: List[Dict[str, Any]] = []
    ya_cargados: List[Dict[str, Any]] = []
    vistas = set()
    fuera = 0
    iva_faltante = Decimal("0")

    for fila in filas:
        fecha = fila["fecha"]
        if f"{fecha.year:04d}-{fecha.month:02d}" != periodo:
            fuera += 1
            continue
        clave = clave_de_fila(fila)
        if clave in vistas:
            continue  # el mismo comprobante dos veces en el Excel
        vistas.add(clave)
        item = {**fila, "clave": clave}
        comp = por_clave.get(clave)
        if comp is None:
            faltantes.append(item)
            signo = Decimal("-1") if es_nota_credito(fila["tipo_codigo"]) else Decimal("1")
            iva_faltante += signo * _d(fila["total_iva"])
            continue
        iva_c, total_c = _d(comp.total_iva), _d(comp.imp_total)
        item.update({
            "comprobante_id": comp.id,
            "total_iva_cuadra": iva_c,
            "imp_total_cuadra": total_c,
            "importe_distinto": iva_c != _d(fila["total_iva"]) or total_c != _d(fila["imp_total"]),
        })
        ya_cargados.append(item)

    solo_en_cuadra = [c for k, c in por_clave.items() if k not in vistas]

    return {
        "faltantes": faltantes,
        "iva_faltante": iva_faltante.quantize(_DOS),
        "ya_cargados": ya_cargados,
        "solo_en_cuadra": solo_en_cuadra,
        "fuera_de_periodo": fuera,
    }


def importar_filas(
    db: Session, org_id: int, direccion: str, periodo: str, filas: List[Dict[str, Any]],
    archivo: Optional[str], elegidas: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    """Carga las filas del período como ComprobanteIva en una tanda (`lote`).

    Dedup por el unique `uq_comprobante_iva_dedup` (las ya cargadas cuentan como
    duplicadas). Con `elegidas` (claves de `comparar`) se cargan solo esas. Cada
    fila se commitea sola: un duplicado no corta al resto.
    """
    elegidas = set(elegidas) if elegidas is not None else None
    lote = str(uuid.uuid4())
    importados = duplicados = fuera = no_elegidos = 0
    for row in filas:
        fecha = row["fecha"]
        if f"{fecha.year:04d}-{fecha.month:02d}" != periodo:
            fuera += 1
            continue
        if elegidas is not None and clave_de_fila(row) not in elegidas:
            no_elegidos += 1
            continue
        db.add(ComprobanteIva(
            organizacion_id=org_id, direccion=direccion, periodo=periodo, fecha=fecha,
            tipo_codigo=row["tipo_codigo"], tipo_desc=row["tipo_desc"],
            punto_venta=row["punto_venta"], numero=row["numero"],
            cuit_contraparte=row["cuit_contraparte"], denominacion=row["denominacion"],
            neto_gravado_total=row["neto_gravado_total"], total_iva=row["total_iva"],
            imp_total=row["imp_total"], detalle_alicuotas=row["detalle_alicuotas"],
            archivo_origen=archivo, lote_importacion=lote,
        ))
        try:
            db.commit()
            importados += 1
        except IntegrityError:
            db.rollback()
            duplicados += 1
    return {"importados": importados, "duplicados": duplicados, "fuera_de_periodo": fuera,
            "no_elegidos": no_elegidos, "periodo": periodo, "lote": lote if importados else None}
