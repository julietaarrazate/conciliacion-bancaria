"""Merge de últimos movimientos con deduplicación por (fecha, monto, titular)."""

import re
from typing import List, Tuple, Optional
from datetime import date, datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
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
    monto_r = round(float(monto or 0), 2)
    return ("fec", _normalizar_fecha(fecha), monto_r, _normalizar_titular(titular))


def _clave_db(mov: MovimientoBanco) -> Tuple:
    return _clave(mov.orden, mov.monto, mov.fecha, mov.titular or "")


def _clave_dict(mov_data: dict) -> Tuple:
    return _clave(
        mov_data.get("orden"),
        mov_data.get("monto"),
        mov_data.get("fecha"),
        mov_data.get("titular") or mov_data.get("referencia") or ""
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

    max_orden_actual = db.query(func.max(MovimientoBanco.orden)).filter(
        MovimientoBanco.extracto_id == extracto_id
    ).scalar() or 0

    agregados = 0
    duplicados = 0
    solapados = 0

    for mov_data in movimientos_nuevos:
        clave = _clave_dict(mov_data)
        if clave in claves_existentes:
            duplicados += 1
            solapados += 1
            continue

        max_orden_actual += 1
        db.add(MovimientoBanco(
            extracto_id=extracto_id,
            orden=max_orden_actual,
            fecha=_normalizar_fecha(mov_data.get("fecha")),
            mes=mov_data.get("mes"),
            titular=mov_data.get("titular") or mov_data.get("referencia") or "",
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
        "solapados": solapados,
        "total_recibido": len(movimientos_nuevos)
    }
