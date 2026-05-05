"""
Mergea Ultimos Movimientos (UM) con el extracto existente.

Clave de deduplicacion (por prioridad):
  1. Si el movimiento tiene `orden` -> usar (orden, monto_redondeado)
     El banco asigna numeros unicos por cuenta — muy confiable.
  2. Si no tiene `orden` -> usar (fecha, monto_redondeado, titular_normalizado)
     Mas robusto que solo (fecha, monto): distingue pagos iguales del mismo dia.
"""

import re
from typing import List, Tuple, Optional
from datetime import date, datetime
from sqlalchemy.orm import Session
from app.models.extracto import MovimientoBanco


def _normalizar_fecha(v) -> Optional[date]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return v


def _normalizar_titular(titular: Optional[str]) -> str:
    """Normaliza el titular para comparacion: minusculas, sin espacios extra, sin caracteres raros."""
    if not titular:
        return ""
    # Quitar cuits embebidos (10-11 digitos) para comparar solo el nombre
    t = re.sub(r'\d{10,11}', '', str(titular))
    t = re.sub(r'\s+', ' ', t).strip().lower()
    # Primeras 3 palabras significativas (>2 chars)
    palabras = [p for p in t.split() if len(p) > 2][:3]
    return ' '.join(palabras)


def _clave(orden, monto, fecha, titular) -> Tuple:
    """
    Si tiene numero de orden -> (orden, monto_redondeado).
    Si no tiene orden        -> (fecha, monto_redondeado, titular_normalizado).
    """
    monto_r = round(float(monto or 0), 2)
    if orden is not None:
        try:
            return ("ord", int(orden), monto_r)
        except (TypeError, ValueError):
            pass
    return ("fec", _normalizar_fecha(fecha), monto_r, _normalizar_titular(titular))


def _clave_db(mov: MovimientoBanco) -> Tuple:
    return _clave(mov.orden, mov.monto, mov.fecha, mov.titular)


def _clave_dict(mov_data: dict) -> Tuple:
    return _clave(
        mov_data.get("orden"),
        mov_data.get("monto"),
        mov_data.get("fecha"),
        mov_data.get("titular")
    )


def mergear_movimientos(db: Session, extracto_id: int, movimientos_nuevos: List[dict]) -> dict:
    """
    Agrega solo los movimientos que no existan ya en el extracto.
    Retorna: {agregados, duplicados, total_recibido}
    """
    existentes = (
        db.query(MovimientoBanco)
        .filter(MovimientoBanco.extracto_id == extracto_id)
        .all()
    )
    claves_existentes = {_clave_db(m) for m in existentes}

    # Detectar rango de ordenes del extracto para informar solapamiento
    ordenes_existentes = {m.orden for m in existentes if m.orden is not None}

    agregados = 0
    duplicados = 0
    solapados = 0  # movimientos del UM que ya estaban en el extracto original

    for mov_data in movimientos_nuevos:
        clave = _clave_dict(mov_data)
        if clave in claves_existentes:
            duplicados += 1
            orden = mov_data.get("orden")
            if orden and orden in ordenes_existentes:
                solapados += 1
            continue

        db.add(MovimientoBanco(
            extracto_id=extracto_id,
            orden=mov_data.get("orden"),
            fecha=_normalizar_fecha(mov_data.get("fecha")),
            mes=mov_data.get("mes"),
            titular=mov_data.get("titular"),
            monto=mov_data.get("monto"),
            saldo=mov_data.get("saldo"),
            source='um'
        ))
        claves_existentes.add(clave)
        agregados += 1

    db.commit()
    return {
        "agregados": agregados,
        "duplicados": duplicados,
        "solapados": solapados,  # cuantos estaban en el extracto original (archivo viejo)
        "total_recibido": len(movimientos_nuevos)
    }
