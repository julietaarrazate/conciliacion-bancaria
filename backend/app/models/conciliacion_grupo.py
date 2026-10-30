"""Grupos de conciliación: N filas de planilla ↔ M movimientos del banco.

El caso 1:1 (una fila ↔ un movimiento del mismo monto) sigue viviendo en
`PlanillaRow.orden_movimiento_acreditado`, sin cambios. Un grupo cubre los dos
casos que el 1:1 no puede:

- A: un movimiento ↔ varias filas (el cliente pagó varias filas con una sola
  transferencia).
- B: varios movimientos ↔ una fila (pagó una fila en dos o más transferencias).

Modelo: `ConciliacionGrupo` (cabecera) + `ConciliacionGrupoItem` (una fila o un
movimiento por item, con el monto de ese momento). Las filas de un grupo NO
usan `orden_movimiento_acreditado` (queda en NULL): así los cálculos que suman
`mov.monto` por fila (liquidaciones) o filas "ok" con movimiento (asientos de
reclasificación, "Empezar limpio") no cuentan dos veces el mismo movimiento. Los
grupos se suman aparte por el monto de sus movimientos (ver
`services/conciliacion_grupos.py`).

Estados:
- `sugerido`: lo encontró el motor después de la pasada 1:1; las filas quedan en
  "SUGERIDO_GRUPO" y el movimiento todavía no se acredita. Se recalcula en cada
  conciliación.
- `confirmado`: lo confirmó una persona (o el motor, si la org lo habilita y la
  identidad es fuerte y la combinación es única). Filas en "ok" (o
  "CONCILIADO_CON_DIFERENCIA") y movimientos acreditados al cliente.
- `descartado`: sugerencia descartada o grupo deshecho. Se conserva para que el
  motor no vuelva a sugerir la misma combinación y para trazabilidad.
"""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship

from app.database import Base

GRUPO_SUGERIDO = "sugerido"
GRUPO_CONFIRMADO = "confirmado"
GRUPO_DESCARTADO = "descartado"
ESTADOS_GRUPO_ACTIVOS = (GRUPO_SUGERIDO, GRUPO_CONFIRMADO)


class ConciliacionGrupo(Base):
    __tablename__ = "conciliacion_grupos"

    id = Column(Integer, primary_key=True, index=True)
    organizacion_id = Column(Integer, ForeignKey("organizaciones.id"), nullable=False, index=True)
    planilla_id = Column(Integer, ForeignKey("planillas.id", ondelete="CASCADE"), nullable=False, index=True)
    estado = Column(String(20), nullable=False, default=GRUPO_SUGERIDO)
    # "auto" (lo encontró el motor) | "manual" (lo armó una persona)
    origen = Column(String(10), nullable=False, default="auto")
    total_filas = Column(Numeric(14, 2), nullable=False)
    total_movimientos = Column(Numeric(14, 2), nullable=False)
    # total_movimientos - total_filas (0 si cuadra)
    diferencia = Column(Numeric(14, 2), nullable=False, default=0)
    # True si el motor encontró más de una combinación posible
    ambiguo = Column(Boolean, nullable=False, default=False)
    creado_por = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    confirmado_at = Column(DateTime, nullable=True)

    items = relationship("ConciliacionGrupoItem", back_populates="grupo", cascade="all, delete-orphan")


class ConciliacionGrupoItem(Base):
    __tablename__ = "conciliacion_grupo_items"

    id = Column(Integer, primary_key=True, index=True)
    grupo_id = Column(Integer, ForeignKey("conciliacion_grupos.id", ondelete="CASCADE"), nullable=False, index=True)
    organizacion_id = Column(Integer, ForeignKey("organizaciones.id"), nullable=False)
    # Exactamente uno de los dos: una fila de la planilla o un movimiento del banco.
    planilla_row_id = Column(Integer, ForeignKey("planilla_rows.id", ondelete="CASCADE"), nullable=True, index=True)
    movimiento_id = Column(Integer, ForeignKey("movimientos_banco.id", ondelete="CASCADE"), nullable=True, index=True)
    monto = Column(Numeric(12, 2), nullable=False)

    grupo = relationship("ConciliacionGrupo", back_populates="items")
