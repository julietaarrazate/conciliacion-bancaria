"""
Mergea Ultimos Movimientos (UM) con el extracto existente.

Estrategia de corte:
  1. Buscar el punto de solapamiento usando (saldo, monto) — el saldo es un
     acumulado unico por movimiento, asi que la combinacion (saldo, monto) es
     practicamente un fingerprint.
  2. Fallback: deduplicar por (fecha, monto, titular_normalizado).
  3. Solo agregar movimientos que estan ANTES del corte (mas nuevos).
  4. Asignar numeros de orden progresivos continuando desde el maximo existente.
"""

import re
from typing import List, Tuple, Optional, Set
from datetime import date, datetime
from sqlalchemy.orm import Session
from app.models.extracto import MovimientoBanco


def _normalizar_titular(titular: Optional[str]) -> str:
    if not titular:
        return ""
    t = re.sub(r'\d{10,11}', '', str(titular))
    t = re.sub(r'\s+', ' ', t).strip().lower()
    palabras = [p for p in t.split() if len(p) > 2][:3]
    return ' '.join(palabras)


def _clave_saldo(monto, saldo) -> Optional[Tuple]:
    if saldo is None:
        return None
    return (round(float(monto or 0), 2), round(float(saldo), 2))


def _clave_texto(fecha, monto, titular) -> Tuple:
    return (
        fecha.isoformat() if isinstance(fecha, date) else str(fecha),
        round(float(monto or 0), 2),
        _normalizar_titular(titular)
    )


def mergear_movimientos(db: Session, extracto_id: int, movimientos_nuevos: List[dict]) -> dict:
    existentes = (
        db.query(MovimientoBanco)
        .filter(MovimientoBanco.extracto_id == extracto_id)
        .all()
    )

    claves_saldo: Set[Tuple] = set()
    claves_texto: Set[Tuple] = set()
    max_orden = 0

    for m in existentes:
        cs = _clave_saldo(m.monto, m.saldo)
        if cs:
            claves_saldo.add(cs)
        claves_texto.add(_clave_texto(m.fecha, m.monto, m.titular))
        if m.orden and m.orden > max_orden:
            max_orden = m.orden

    agregados = 0
    duplicados = 0
    corte_idx = None

    for i, mov_data in enumerate(movimientos_nuevos):
        cs = _clave_saldo(mov_data.get("monto"), mov_data.get("saldo"))
        ct = _clave_texto(mov_data.get("fecha"), mov_data.get("monto"), mov_data.get("titular"))

        if (cs and cs in claves_saldo) or ct in claves_texto:
            duplicados += 1
            if corte_idx is None:
                corte_idx = i
            continue

        if corte_idx is not None:
            duplicados += 1
            continue

        max_orden += 1
        fecha = mov_data.get("fecha")
        if isinstance(fecha, datetime):
            fecha = fecha.date()

        mes = mov_data.get("mes")
        if not mes and fecha:
            mes = str(fecha.month)

        db.add(MovimientoBanco(
            extracto_id=extracto_id,
            orden=max_orden,
            fecha=fecha,
            mes=mes,
            titular=mov_data.get("titular"),
            monto=mov_data.get("monto"),
            saldo=mov_data.get("saldo"),
            source='um'
        ))

        cs_new = _clave_saldo(mov_data.get("monto"), mov_data.get("saldo"))
        if cs_new:
            claves_saldo.add(cs_new)
        claves_texto.add(ct)
        agregados += 1

    db.commit()
    return {
        "agregados": agregados,
        "duplicados": duplicados,
        "corte_en": corte_idx,
        "total_recibido": len(movimientos_nuevos)
    }
