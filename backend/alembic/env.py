import os
import sys
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# Agregar el directorio backend al path para importar app.*
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.database import Base, DATABASE_URL

# Importar TODOS los módulos de modelo para poblar Base.metadata (autogenerate y
# metadata completa). Importar el módulo basta para registrar sus tablas; hacerlo por
# módulo (no por clase) evita que un renombre/unificación de clases rompa este import
# — que corre en CADA comando de alembic, incl. `upgrade`. Ojo: hasta jul 2026 esto
# importaba clases inexistentes (OrdenDePago/Pago/Gasto, unificadas en Egreso), lo que
# hacía fallar `alembic upgrade` en silencio (el esquema lo sostenían los safety-nets).
from app.models import (  # noqa: F401
    organizacion, user, cliente, extracto, planilla, auditoria, patron_aprendido,
    liquidacion, caja, egreso, contabilidad, cheque, portador, liquidacion_tarjeta,
    proyeccion_iva, password_reset, arca, iibb, monotributo, sueldos,
    login_approval, twofa_code, push_subscription, revoked_token,
)

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
