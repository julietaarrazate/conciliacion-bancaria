from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CuentaContable(Base):
    """Catálogo de cuentas contables (plan de cuentas).
    Tipos: activo, pasivo, patrimonio, ingreso, egreso.
    """
    __tablename__ = "cuentas_contables"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    nombre: Mapped[str] = mapped_column(String(100), unique=True)
    tipo: Mapped[str] = mapped_column(String(20))  # activo|pasivo|patrimonio|ingreso|egreso
    # naturaleza: deudora|acreedora
    naturaleza: Mapped[str] = mapped_column(String(10))
