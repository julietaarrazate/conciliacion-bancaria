import os
import sys
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# Agregar el directorio backend al path para importar app.*
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.database import Base, DATABASE_URL

# Importar todos los modelos para que Base.metadata los conozca
from app.models.user import User
from app.models.organizacion import Organizacion
from app.models.cliente import Cliente
from app.models.extracto import ExtractoBancario, MovimientoBanco
from app.models.planilla import Planilla, PlanillaRow
from app.models.auditoria import AuditoriaLog
from app.models.patron_aprendido import PatronAprendido
from app.models.liquidacion import Liquidacion, LiquidacionDetalle, CierrePeriodo
from app.models.caja import ArqueoDiario, OrdenDePago
from app.models.cheque import Cheque
from app.models.pago import Pago, Gasto
from app.models.contabilidad import PlanCuenta, ReglaContable, Asiento, AsientoDetalle

config = context.config

# Inyectar DATABASE_URL desde el entorno (Render lo provee)
config.set_main_option("sqlalchemy.url", DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
