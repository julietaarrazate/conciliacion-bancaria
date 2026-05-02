"""
Mergea Ultimos Movimientos (UM) con el extracto existente.

Clave de deduplicacion (por prioridad):
  1. Si el movimiento tiene `orden` (numero secuencial del banco) -> usar (orden, monto)
     Esto es lo mas confiable: el banco asigna numeros unicos por cuenta.
  2. Si no tiene `orden` -> usar (fecha, importe) como fallback.

Esto evita duplicados aunque el saldo calculado difiera por redondeo.
"""

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


def _clave(orden, monto, fecha) -> Tuple:
    """
    Si tiene numero de orden del banco -> (orden, monto_redondeado).
    Si no tiene orden               -> (None, fecha, monto_redondeado).
    """
    monto_r = round(float(monto or 0), 2)
    if orden is not None:
        try:
            return ("ord", int(orden), monto_r)
        except (TypeError, ValueError):
            pass
    return ("fec", _normalizar_fecha(fecha), monto_r)


def _clave_db(mov: MovimientoBanco) -> Tuple:
    return _clave(mov.orden, mov.monto, mov.fecha)


def _clave_dict(mov_data: dict) -> Tuple:
    return _clave(mov_data.get("orden"), mov_data.get("monto"), mov_data.get("fecha"))


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

    agregados = 0
    duplicados = 0

    for mov_data in movimientos_nuevos:
        clave = _clave_dict(mov_data)
        if clave in claves_existentes:
            duplicados += 1
            continue

        db.add(MovimientoBanco(
            extracto_id=extracto_id,
            orden=mov_data.get("orden"),
            fecha=_normalizar_fecha(mov_data.get("fecha")),
            mes=mov_data.get("mes"),
            titular=mov_data.get("titular"),
            monto=mov_data.get("monto"),
            saldo=mov_data.get("saldo"),
            source='um'  # marcado como Últimos Movimientos
        ))
        claves_existentes.add(clave)
        agregados += 1

    db.commit()
    return {"agregados": agregados, "duplicados": duplicados, "total_recibido": len(movimientos_nuevos)}
