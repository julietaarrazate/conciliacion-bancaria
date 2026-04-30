"""
Servicio para mergear Ultimos Movimientos (UM) con un extracto existente,
detectando duplicados por (fecha, mes, importe, saldo).
"""

from typing import List, Tuple
from datetime import date, datetime
from sqlalchemy.orm import Session
from app.models.extracto import MovimientoBanco


def _normalizar_fecha(v):
    """Convierte cualquier representacion de fecha a date para comparar"""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return v


def _clave_movimiento(mov_dict: dict) -> Tuple:
    """
    Clave unica de un movimiento para detectar duplicados.
    Usa: fecha + mes + importe + saldo (los 4 que pidio Julieta).
    """
    return (
        _normalizar_fecha(mov_dict.get("fecha")),
        str(mov_dict.get("mes") or "").strip().lower(),
        round(float(mov_dict.get("monto") or 0), 2),
        round(float(mov_dict.get("saldo") or 0), 2) if mov_dict.get("saldo") is not None else None
    )


def _clave_movimiento_db(mov: MovimientoBanco) -> Tuple:
    """Misma clave pero a partir de un MovimientoBanco de la BD"""
    return (
        _normalizar_fecha(mov.fecha),
        str(mov.mes or "").strip().lower(),
        round(float(mov.monto or 0), 2),
        round(float(mov.saldo or 0), 2) if mov.saldo is not None else None
    )


def mergear_movimientos(
    db: Session,
    extracto_id: int,
    movimientos_nuevos: List[dict]
) -> dict:
    """
    Mergea una lista de movimientos nuevos contra el extracto existente.
    Solo agrega los que no existen ya (por fecha+mes+importe+saldo).

    Retorna stats:
        - agregados: cuantos se sumaron
        - duplicados: cuantos se ignoraron por estar ya
        - total_recibido: total de filas en el archivo
    """
    # Cargar movimientos existentes y armar set de claves
    existentes = (
        db.query(MovimientoBanco)
        .filter(MovimientoBanco.extracto_id == extracto_id)
        .all()
    )
    claves_existentes = {_clave_movimiento_db(m) for m in existentes}

    agregados = 0
    duplicados = 0

    for mov_data in movimientos_nuevos:
        clave = _clave_movimiento(mov_data)
        if clave in claves_existentes:
            duplicados += 1
            continue

        nuevo = MovimientoBanco(
            extracto_id=extracto_id,
            orden=mov_data.get("orden"),
            fecha=_normalizar_fecha(mov_data.get("fecha")),
            mes=mov_data.get("mes"),
            titular=mov_data.get("titular"),
            monto=mov_data.get("monto"),
            saldo=mov_data.get("saldo")
        )
        db.add(nuevo)
        claves_existentes.add(clave)  # evita dup dentro del mismo archivo
        agregados += 1

    db.commit()

    return {
        "agregados": agregados,
        "duplicados": duplicados,
        "total_recibido": len(movimientos_nuevos)
    }
