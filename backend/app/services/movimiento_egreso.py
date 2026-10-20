"""Vínculo egreso ↔ movimiento del extracto ("resolver un pendiente").

Desde un débito del extracto que no tiene explicación se crea (o se elige) el
pago/gasto que lo explica, sin salir de la pantalla de Movimientos. El vínculo
vive en `Egreso.movimiento_banco_id`.

Reglas del vínculo:
- Solo débitos (monto < 0) y egresos con forma_pago=banco.
- Mismo importe: |monto del movimiento| == monto del egreso (Decimal, al centavo).
- Un movimiento se explica con un solo egreso.
- Misma organización, extracto no borrado, período no cerrado.

No toca asientos: el egreso se contabiliza igual que si se cargara a mano en
Pagos (`motor_contable.registrar_egreso`). No usa `cliente_acreditado`, que es
el vínculo con clientes (créditos) y alimenta reportes y cuentas corrientes.
"""

from datetime import timedelta
from decimal import Decimal, InvalidOperation
from typing import Dict, Iterable, List, Optional

from sqlalchemy.orm import Session

from app.models.egreso import Egreso
from app.models.extracto import ExtractoBancario, MovimientoBanco


class VinculoInvalido(ValueError):
    """El movimiento no se puede vincular al egreso (mensaje apto para el usuario)."""


def _centavos(valor) -> Decimal:
    try:
        return Decimal(str(valor)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError):
        raise VinculoInvalido("Importe inválido")


def validar_vinculo(
    db: Session,
    movimiento_id,
    org_id: int,
    monto,
    forma_pago: str,
    egreso_id: Optional[int] = None,
) -> MovimientoBanco:
    """Devuelve el movimiento si el egreso (nuevo o `egreso_id`) lo puede explicar.

    Lanza VinculoInvalido con el motivo si no.
    """
    try:
        int(movimiento_id)
    except (TypeError, ValueError):
        raise VinculoInvalido("movimiento_banco_id inválido")

    mov = buscar_movimiento(db, movimiento_id, org_id)
    if not mov:
        raise VinculoInvalido("Movimiento del extracto no encontrado")

    importe_mov = _centavos(mov.monto)
    if importe_mov >= 0:
        raise VinculoInvalido(
            "Solo un débito del extracto se explica con un pago; un crédito se acredita a un cliente"
        )
    if forma_pago != "banco":
        raise VinculoInvalido("Un movimiento del extracto solo se explica con un pago por banco")
    if _centavos(monto) != -importe_mov:
        raise VinculoInvalido(
            f"El pago tiene que ser por el mismo importe que el movimiento ({-importe_mov})"
        )

    from app.services.cierre_periodo import periodo_esta_cerrado
    if periodo_esta_cerrado(db, org_id, mov.fecha_acred or mov.fecha):
        raise VinculoInvalido("El período del movimiento ya está cerrado")

    otro = db.query(Egreso.id).filter(Egreso.movimiento_banco_id == mov.id)
    if egreso_id is not None:
        otro = otro.filter(Egreso.id != egreso_id)
    otro_id = otro.scalar()
    if otro_id is not None:
        raise VinculoInvalido(f"El movimiento ya está explicado por el pago #{otro_id}")

    return mov


# Ventana de fechas para sugerir un pago ya cargado: el pago se registra el día
# que se hace y el banco lo debita (o el extracto lo muestra) unos días después.
DIAS_CANDIDATOS = 10


def buscar_movimiento(db: Session, movimiento_id, org_id: int) -> Optional[MovimientoBanco]:
    """Movimiento de la org en un extracto no borrado, o None."""
    try:
        mov_id = int(movimiento_id)
    except (TypeError, ValueError):
        return None
    return (
        db.query(MovimientoBanco)
        .join(ExtractoBancario, ExtractoBancario.id == MovimientoBanco.extracto_id)
        .filter(
            MovimientoBanco.id == mov_id,
            ExtractoBancario.organizacion_id == org_id,
            ExtractoBancario.deleted_at.is_(None),
        )
        .first()
    )


def candidatos_para_movimiento(
    db: Session, mov: MovimientoBanco, org_id: int, dias: int = DIAS_CANDIDATOS,
) -> List[Egreso]:
    """Pagos ya cargados que podrían explicar el débito `mov`.

    Mismo importe, forma de pago banco, sin vincular, de la org y con fecha a
    ±`dias` del movimiento. Ordenados por cercanía de fecha. Vacío si `mov` no es
    un débito.
    """
    try:
        importe = -_centavos(mov.monto)
    except VinculoInvalido:
        return []
    if importe <= 0:
        return []
    q = db.query(Egreso).filter(
        Egreso.organizacion_id == org_id,
        Egreso.forma_pago == "banco",
        Egreso.movimiento_banco_id.is_(None),
        Egreso.monto == importe,
    )
    if mov.fecha:
        q = q.filter(Egreso.fecha >= mov.fecha - timedelta(days=dias),
                     Egreso.fecha <= mov.fecha + timedelta(days=dias))
    egresos = q.all()
    if mov.fecha:
        egresos.sort(key=lambda e: (abs((e.fecha - mov.fecha).days) if e.fecha else dias + 1, e.id))
    return egresos


def egresos_por_movimiento(db: Session, movimiento_ids: Iterable[int]) -> Dict[int, int]:
    """{movimiento_id: egreso_id} para los movimientos que ya tienen su egreso."""
    ids = [i for i in movimiento_ids if i is not None]
    if not ids:
        return {}
    filas = (
        db.query(Egreso.movimiento_banco_id, Egreso.id)
        .filter(Egreso.movimiento_banco_id.in_(ids))
        .all()
    )
    return {mov_id: eg_id for mov_id, eg_id in filas}
