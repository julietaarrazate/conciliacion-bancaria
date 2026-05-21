from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CuentaContable(Base):
    """Plan de cuentas jerárquico (4 niveles, código X-X-X-X).

    Niveles:
      1 = Rubro mayor (Activo, Pasivo, Resultado)
      2 = Rubro      (Activo Corriente, Pasivo Corriente, Ingresos, Gastos)
      3 = Sub-rubro  (Disponibilidades, Créditos, Cliente, Comisiones)
      4 = Imputable  (Banco, Caja chica, Green, Tucu, ...) — únicas que reciben asientos

    Tipos: activo | pasivo | patrimonio | resultado_positivo | resultado_negativo
    Naturaleza: deudora | acreedora
    """
    __tablename__ = "cuentas_contables"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    nombre: Mapped[str] = mapped_column(String(100))
    tipo: Mapped[str] = mapped_column(String(30))
    naturaleza: Mapped[str] = mapped_column(String(10))
    nivel: Mapped[int] = mapped_column(Integer, default=1)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("cuentas_contables.id"), index=True)
    # Solo las cuentas imputables (hojas) pueden recibir movimientos
    imputable: Mapped[bool] = mapped_column(Boolean, default=False)
    # Si la cuenta es la sub-cuenta de un cliente específico
    cliente_id: Mapped[int | None] = mapped_column(ForeignKey("clientes.id"), index=True)

    parent: Mapped["CuentaContable | None"] = relationship(
        "CuentaContable", remote_side="CuentaContable.id", backref="hijas"
    )
