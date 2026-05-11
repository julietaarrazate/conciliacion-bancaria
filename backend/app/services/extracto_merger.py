"""
Mergea Ultimos Movimientos (UM) con el extracto existente.

Estrategia de corte:
  1. Buscar el punto de solapamiento usando (saldo, monto) — el saldo es un
     acumulado unico por movimiento, asi que (saldo, monto) es un fingerprint.
     Usa tolerancia de 0.01 para tolerar redondeos de floats.
  2. Fallback: deduplicar por (fecha, monto, titular_normalizado).
  3. Solo agregar movimientos que estan ANTES del corte (mas nuevos).
  4. Asignar numeros de orden progresivos continuando desde el maximo existente.
"""

import re
from typing import List, Optional
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


def _to_float(v):
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _match_existente(mov_data: dict, existentes_idx: list) -> bool:
    """
    True si el mov_data ya esta en existentes_idx.
    existentes_idx es lista de tuplas (monto, saldo, fecha_iso, titular_norm).
    Match por (saldo, monto) con tolerancia 0.01, fallback (fecha, monto, titular).
    """
    monto_n = _to_float(mov_data.get("monto"))
    saldo_n = _to_float(mov_data.get("saldo"))
    fecha = mov_data.get("fecha")
    fecha_iso = fecha.isoformat() if isinstance(fecha, date) else (str(fecha) if fecha else "")
    titular_norm = _normalizar_titular(mov_data.get("titular"))

    for (m_e, s_e, f_e, t_e) in existentes_idx:
        if (saldo_n is not None and s_e is not None
            and abs(saldo_n - s_e) < 0.01
            and monto_n is not None and m_e is not None
            and abs(monto_n - m_e) < 0.01):
            return True
        if (fecha_iso == f_e
            and monto_n is not None and m_e is not None
            and abs(monto_n - m_e) < 0.01
            and titular_norm == t_e):
            return True
    return False


def mergear_movimientos(db: Session, extracto_id: int, movimientos_nuevos: List[dict]) -> dict:
    existentes = (
        db.query(MovimientoBanco)
        .filter(MovimientoBanco.extracto_id == extracto_id)
        .all()
    )

    existentes_idx = []
    max_orden = 0
    for m in existentes:
        existentes_idx.append((
            _to_float(m.monto),
            _to_float(m.saldo),
            m.fecha.isoformat() if isinstance(m.fecha, date) else (str(m.fecha) if m.fecha else ""),
            _normalizar_titular(m.titular),
        ))
        if m.orden and m.orden > max_orden:
            max_orden = m.orden

    agregados = 0
    duplicados = 0
    corte_idx: Optional[int] = None

    # El UM viene ORDENADO del mas nuevo (arriba) al mas viejo (abajo).
    # Todo lo previo al primer match es nuevo; lo que sigue ya esta en el extracto.
    nuevos_a_agregar: List[dict] = []
    for i, mov_data in enumerate(movimientos_nuevos):
        if _match_existente(mov_data, existentes_idx):
            if corte_idx is None:
                corte_idx = i
            duplicados += 1
            continue
        if corte_idx is not None:
            duplicados += 1
            continue
        nuevos_a_agregar.append(mov_data)

    # Orden: el mas nuevo del UM = max_orden + n (mas alto); el mas viejo = max_orden + 1.
    n = len(nuevos_a_agregar)
    for idx, mov_data in enumerate(nuevos_a_agregar):
        orden_nuevo = max_orden + (n - idx)
        fecha = mov_data.get("fecha")
        if isinstance(fecha, datetime):
            fecha = fecha.date()
        mes = mov_data.get("mes")
        if not mes and fecha:
            mes = str(fecha.month)
        db.add(MovimientoBanco(
            extracto_id=extracto_id,
            orden=orden_nuevo,
            fecha=fecha,
            mes=mes,
            titular=mov_data.get("titular"),
            monto=mov_data.get("monto"),
            saldo=mov_data.get("saldo"),
            cliente_acreditado=mov_data.get("cliente_acreditado"),
            fecha_acred=mov_data.get("fecha_acred"),
            source='um',
        ))
        agregados += 1

    db.commit()
    return {
        "agregados": agregados,
        "duplicados": duplicados,
        "corte_en": corte_idx,
        "total_recibido": len(movimientos_nuevos),
    }
