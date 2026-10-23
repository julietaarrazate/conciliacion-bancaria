"""Persistencia compartida de extractos bancarios (Excel y PDF).

Antes esto vivía adentro de `routers/extractos.py`. Se movió acá —sin cambiar
el comportamiento— para que el importador de PDF (`extracto_pdf_service`) guarde
los extractos exactamente igual que el upload de Excel: mismo nombre de banco,
misma huella (fingerprint), misma numeración de `orden` y mismo asiento de UM.

- `resolver_banco` / `_BANCO_NOMBRE`: clave interna del parser → nombre visible.
- `fingerprint`: huella del extracto (dedup contra el índice `uq_extracto_fp_org`).
- `crear_extracto_con_movimientos`: alta de un extracto nuevo con sus movimientos.
- `registrar_asiento_um`: asiento contable de un lote UM recién agregado.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models.extracto import ExtractoBancario, MovimientoBanco

logger = logging.getLogger(__name__)

# Mapeo de clave interna del parser → nombre de banco legible
_BANCO_NOMBRE = {
    "macro":     "Banco Macro",
    "bbva":      "BBVA",
    "santander": "Santander",
    "galicia":   "Galicia",
    "icbc":      "ICBC",
    "nacion":    "Banco Nación",
    "provincia": "Bapro",
    "ciudad":    "Banco Ciudad",
    "hsbc":      "HSBC",
}


def nombre_banco(banco_clave: Optional[str]) -> Optional[str]:
    """Nombre visible de una clave de banco del parser (None si es genérico/desconocido)."""
    if not banco_clave or banco_clave == "generico":
        return None
    return _BANCO_NOMBRE.get(banco_clave, banco_clave.capitalize())


def resolver_banco(banco_param: str, banco_detectado: str) -> str:
    """
    Usa el banco detectado por el parser cuando es más específico que el default.
    Si el usuario pasó un banco explícito distinto del default, se respeta siempre.
    """
    if banco_detectado != "generico":
        nombre_detectado = _BANCO_NOMBRE.get(banco_detectado, banco_detectado.capitalize())
        # Usar detectado si el parámetro es el default ("Banco Macro") o coincide
        if banco_param == "Banco Macro" or banco_param == nombre_detectado:
            return nombre_detectado
    return banco_param


def fingerprint(movimientos: list) -> str:
    """Huella digital del extracto: hash de total+ordenes+suma_montos"""
    total = len(movimientos)
    if total == 0:
        return "empty"
    primer_orden = movimientos[0].get("orden") or 0
    ultimo_orden = movimientos[-1].get("orden") or 0
    suma = round(sum(m.get("monto", 0) for m in movimientos), 2)
    raw = f"{total}|{primer_orden}|{ultimo_orden}|{suma}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def crear_extracto_con_movimientos(
    db: Session,
    *,
    movs: list,
    nombre_archivo: str,
    banco: str,
    huella: str,
    org_id: int,
    usuario_id: int,
    commit: bool = True,
) -> ExtractoBancario:
    """Crea un extracto nuevo con sus movimientos (mismo código que el upload de Excel).

    `movs` viene con la forma del parser (`{"orden", "fecha", "mes", "titular", "monto",
    "saldo", "cliente_acreditado", "fecha_acred"}`) y **del más reciente al más antiguo**
    (orden Banco Macro): el índice 0 recibe el `orden` más alto.

    `huella` es el resultado de `fingerprint(movs)` (se guarda en `fingerprint`).
    Con `commit=False` solo hace `flush` (el que llama confirma todo junto, p. ej. el
    importador de PDF marca el borrador como confirmado en la misma transacción).
    No genera el asiento contable: lo hace el que llama, después del commit, con
    `motor_contable.registrar_asientos_extracto` (upload de Excel y PDF nuevo).
    """
    extracto = ExtractoBancario(nombre_archivo=nombre_archivo, creado_por=usuario_id, fingerprint=huella,
                                banco=banco, organizacion_id=org_id)
    db.add(extracto)
    db.flush()
    # Orden: contador secuencial POR EXTRACTO — NO usar valores del banco.
    # Cada extracto arranca su propia numeración desde 1 (un extracto recién
    # creado no tiene movimientos → max 0 → el más antiguo recibe 1, el más
    # reciente N). Mismo criterio que el append de UM (extracto_merger), y evita
    # que un extracto de otra empresa/banco continúe la numeración de otro.
    from sqlalchemy import func as _func
    max_global = (
        db.query(_func.max(MovimientoBanco.orden))
        .filter(MovimientoBanco.extracto_id == extracto.id)
        .scalar() or 0
    )
    n_movs = len(movs)
    for i, m in enumerate(movs):
        # i=0 es el más reciente → orden más alto
        orden_asignado = max_global + (n_movs - i)
        db.add(MovimientoBanco(
            extracto_id=extracto.id, orden=orden_asignado,
            fecha=m.get("fecha"), mes=m.get("mes"),
            titular=m.get("titular"), monto=m.get("monto"), saldo=m.get("saldo"),
            cliente_acreditado=m.get("cliente_acreditado"),
            fecha_acred=m.get("fecha_acred"),
            organizacion_id=org_id,
        ))
    if commit:
        db.commit()
        db.refresh(extracto)
    else:
        db.flush()
    return extracto


def registrar_asiento_um(
    db: Session,
    *,
    extracto: ExtractoBancario,
    nuevo_lote: int,
    usuario_id: int,
    modo_asiento: Optional[str] = None,
) -> bool:
    """Asiento contable automático de los movimientos de un lote UM recién agregado.

    Tolerante a fallos: los movimientos ya se guardaron, un fallo acá no debe
    bloquear la importación, pero se reporta (devuelve False) para que no quede
    silencioso. `modo_asiento` ("individual" | "agrupado") pisa la config de la org.
    """
    extracto_id = None
    try:
        from app.services.motor_contable import registrar_um_import
        from app.models.organizacion import Organizacion as _Org
        extracto_id = extracto.id
        _org_id = extracto.organizacion_id or 1
        movs_nuevos = db.query(MovimientoBanco).filter(
            MovimientoBanco.extracto_id == extracto_id,
            MovimientoBanco.um_lote == nuevo_lote,
        ).all()
        _org = db.query(_Org).filter(_Org.id == _org_id).first()
        _modo_config = ((_org.configuracion or {}).get("modo_asiento_um", "agrupado")) if _org else "agrupado"
        _modo = modo_asiento if modo_asiento in ("individual", "agrupado") else _modo_config
        registrar_um_import(
            db=db,
            extracto_id=extracto_id,
            org_id=_org_id,
            usuario_id=usuario_id,
            movimientos_nuevos=movs_nuevos,
            modo=_modo,
        )
        return True
    except Exception as _mc_ex:
        # Sin tocar `extracto.id`: si la sesión quedó rota, leer un atributo vencido relanza.
        logger.error("motor_contable UM falló (extracto %s, lote %s): %s", extracto_id, nuevo_lote, _mc_ex)
        return False
