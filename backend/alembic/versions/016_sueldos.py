"""Módulo Liquidador de Sueldos y F931

Crea las 6 tablas del módulo:
  - convenios_colectivos        : convenios por org, unique (organizacion_id, nombre).
  - categorias_convenio         : categorías por convenio, unique (convenio_id, nombre).
  - empleados                   : empleados por org, con soft delete (deleted_at).
  - config_sueldos              : 1 config por org (unique organizacion_id), opt-in.
  - liquidaciones_sueldo        : snapshot por período, unique (organizacion_id, periodo).
  - detalles_liquidacion_sueldo : una fila por empleado liquidado.

Tolerante a reintentos: IF NOT EXISTS donde aplica.

Revision ID: 016
Revises: 015
Create Date: 2026-06-24
"""
from alembic import op

revision = '016'
down_revision = '015'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS convenios_colectivos (
            id SERIAL PRIMARY KEY,
            organizacion_id INTEGER NOT NULL REFERENCES organizaciones(id),
            nombre VARCHAR(120) NOT NULL,
            descripcion VARCHAR(255),
            activo BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            CONSTRAINT uq_convenio_org_nombre UNIQUE (organizacion_id, nombre)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_convenio_org ON convenios_colectivos (organizacion_id)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS categorias_convenio (
            id SERIAL PRIMARY KEY,
            convenio_id INTEGER NOT NULL REFERENCES convenios_colectivos(id),
            nombre VARCHAR(120) NOT NULL,
            sueldo_basico NUMERIC(12,2) NOT NULL DEFAULT 0,
            orden INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            CONSTRAINT uq_categoria_convenio_nombre UNIQUE (convenio_id, nombre)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_categoria_convenio ON categorias_convenio (convenio_id)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS empleados (
            id SERIAL PRIMARY KEY,
            organizacion_id INTEGER NOT NULL REFERENCES organizaciones(id),
            nombre VARCHAR(160) NOT NULL,
            cuil VARCHAR(13),
            convenio_id INTEGER REFERENCES convenios_colectivos(id),
            categoria_id INTEGER REFERENCES categorias_convenio(id),
            fecha_ingreso DATE,
            sueldo_basico NUMERIC(12,2),
            cargas_familia INTEGER NOT NULL DEFAULT 0,
            activo BOOLEAN NOT NULL DEFAULT TRUE,
            deleted_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_empleado_org ON empleados (organizacion_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_empleado_deleted ON empleados (deleted_at)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS config_sueldos (
            id SERIAL PRIMARY KEY,
            organizacion_id INTEGER NOT NULL UNIQUE REFERENCES organizaciones(id),
            activo BOOLEAN NOT NULL DEFAULT FALSE,
            aporte_jubilacion NUMERIC(5,4) NOT NULL DEFAULT 0,
            aporte_inssjp NUMERIC(5,4) NOT NULL DEFAULT 0,
            aporte_obra_social NUMERIC(5,4) NOT NULL DEFAULT 0,
            contrib_jubilacion NUMERIC(5,4) NOT NULL DEFAULT 0,
            contrib_inssjp NUMERIC(5,4) NOT NULL DEFAULT 0,
            contrib_obra_social NUMERIC(5,4) NOT NULL DEFAULT 0,
            contrib_asig_fam NUMERIC(5,4) NOT NULL DEFAULT 0,
            contrib_fondo_desempleo NUMERIC(5,4) NOT NULL DEFAULT 0,
            alicuota_art NUMERIC(5,4) NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS liquidaciones_sueldo (
            id SERIAL PRIMARY KEY,
            organizacion_id INTEGER NOT NULL REFERENCES organizaciones(id),
            periodo VARCHAR(7) NOT NULL,
            estado VARCHAR(20) NOT NULL DEFAULT 'borrador',
            total_bruto NUMERIC(12,2) NOT NULL DEFAULT 0,
            total_aportes NUMERIC(12,2) NOT NULL DEFAULT 0,
            total_contribuciones NUMERIC(12,2) NOT NULL DEFAULT 0,
            total_neto NUMERIC(12,2) NOT NULL DEFAULT 0,
            fecha_aprobacion TIMESTAMP,
            fecha_presentacion TIMESTAMP,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            CONSTRAINT uq_liquidacion_sueldo_org_periodo UNIQUE (organizacion_id, periodo)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_liquidacion_sueldo_org ON liquidaciones_sueldo (organizacion_id)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS detalles_liquidacion_sueldo (
            id SERIAL PRIMARY KEY,
            liquidacion_periodo_id INTEGER NOT NULL REFERENCES liquidaciones_sueldo(id),
            empleado_id INTEGER REFERENCES empleados(id),
            sueldo_bruto NUMERIC(12,2) NOT NULL DEFAULT 0,
            sac_proporcional NUMERIC(12,2) NOT NULL DEFAULT 0,
            total_aportes NUMERIC(12,2) NOT NULL DEFAULT 0,
            total_contribuciones NUMERIC(12,2) NOT NULL DEFAULT 0,
            sueldo_neto NUMERIC(12,2) NOT NULL DEFAULT 0,
            detalle_json JSONB,
            created_at TIMESTAMP DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_detalle_liq_sueldo ON detalles_liquidacion_sueldo (liquidacion_periodo_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_detalle_liq_sueldo")
    op.execute("DROP TABLE IF EXISTS detalles_liquidacion_sueldo")
    op.execute("DROP INDEX IF EXISTS ix_liquidacion_sueldo_org")
    op.execute("DROP TABLE IF EXISTS liquidaciones_sueldo")
    op.execute("DROP TABLE IF EXISTS config_sueldos")
    op.execute("DROP INDEX IF EXISTS ix_empleado_deleted")
    op.execute("DROP INDEX IF EXISTS ix_empleado_org")
    op.execute("DROP TABLE IF EXISTS empleados")
    op.execute("DROP INDEX IF EXISTS ix_categoria_convenio")
    op.execute("DROP TABLE IF EXISTS categorias_convenio")
    op.execute("DROP INDEX IF EXISTS ix_convenio_org")
    op.execute("DROP TABLE IF EXISTS convenios_colectivos")
