"""
Mergea Ultimos Movimientos (UM) con el extracto existente.

Estrategia de corte (en orden de prioridad):
  1. corte_saldo manual: si se pasa, buscar ese saldo exacto en el UM.
  2. Ancla en el ultimo movimiento del extracto (max orden): buscar su
     (saldo, monto) en el UM — es el punto de overlap mas preciso.
  3. Fallback: primer match generico contra cualquier movimiento existente.

Una vez encontrado el corte_idx, se agregan SOLO los movimientos que aparecen
ANTES (indices menores) en el UM, deduplicando contra existentes como safety net.
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


def mergear_movimientos(
    db: Session,
    extracto_id: int,
    movimientos_nuevos: List[dict],
    corte_saldo: Optional[float] = None,
) -> dict:
    existentes = (
        db.query(MovimientoBanco)
        .filter(MovimientoBanco.extracto_id == extracto_id)
        .all()
    )

    existentes_idx = []
    max_orden = 0
    ancla_saldo: Optional[float] = None
    ancla_monto: Optional[float] = None

    for m in existentes:
        existentes_idx.append((
            _to_float(m.monto),
            _to_float(m.saldo),
            m.fecha.isoformat() if isinstance(m.fecha, date) else (str(m.fecha) if m.fecha else ""),
            _normalizar_titular(m.titular),
        ))
        orden = m.orden or 0
        if orden > max_orden:
            max_orden = orden
            ancla_saldo = _to_float(m.saldo)
            ancla_monto = _to_float(m.monto)

    corte_idx: Optional[int] = None
    corte_metodo = "ninguno"

    # 1. Override manual: buscar el saldo indicado en el UM
    if corte_saldo is not None:
        for i, mov_data in enumerate(movimientos_nuevos):
            s = _to_float(mov_data.get("saldo"))
            if s is not None and abs(s - corte_saldo) < 0.01:
                corte_idx = i
                corte_metodo = "manual"
                break

    # 2. Ancla en el ultimo movimiento del extracto (max orden)
    if corte_idx is None and ancla_saldo is not None:
        for i, mov_data in enumerate(movimientos_nuevos):
            s = _to_float(mov_data.get("saldo"))
            m = _to_float(mov_data.get("monto"))
            if (s is not None and abs(s - ancla_saldo) < 0.01
                    and m is not None and ancla_monto is not None
                    and abs(m - ancla_monto) < 0.01):
                corte_idx = i
                corte_metodo = "ancla"
                break

    # 3. Fallback: primer match generico
    if corte_idx is None:
        for i, mov_data in enumerate(movimientos_nuevos):
            if _match_existente(mov_data, existentes_idx):
                corte_idx = i
                corte_metodo = "fallback"
                break

    # Candidatos: todo lo que esta ANTES del corte (o todo si no hay corte)
    candidatos = movimientos_nuevos[:corte_idx] if corte_idx is not None else movimientos_nuevos

    # Safety net: descartar los que ya existen (deduplicacion)
    nuevos_a_agregar = [m for m in candidatos if not _match_existente(m, existentes_idx)]

    agregados = 0
    duplicados = len(movimientos_nuevos) - len(nuevos_a_agregar)

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

    corte_saldo_detectado = None
    if corte_idx is not None and corte_idx < len(movimientos_nuevos):
        corte_saldo_detectado = _to_float(movimientos_nuevos[corte_idx].get("saldo"))

    return {
        "agregados": agregados,
        "duplicados": duplicados,
        "corte_en": corte_idx,
        "corte_metodo": corte_metodo,
        "corte_saldo_detectado": corte_saldo_detectado,
        "total_recibido": len(movimientos_nuevos),
    }
