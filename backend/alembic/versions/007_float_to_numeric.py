"""007_float_to_numeric — migra columnas financieras de FLOAT a NUMERIC

Convierte todas las columnas monetarias de DOUBLE PRECISION (Float SQLAlchemy)
a NUMERIC con precision especifica:
  - NUMERIC(12,2) para montos (hasta $9,999,999,999.99)
  - NUMERIC(5,4)  para porcentajes (ej: 0.0350 = 3.50%)

Revision ID: 007
Revises: 006
Create Date: 2026-05-26
"""

from alembic import op

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # liquidaciones
    op.execute("""
        ALTER TABLE liquidaciones
            ALTER COLUMN total_conciliado TYPE NUMERIC(12,2) USING total_conciliado::numeric,
            ALTER COLUMN total_comision   TYPE NUMERIC(12,2) USING total_comision::numeric,
            ALTER COLUMN total_neto       TYPE NUMERIC(12,2) USING total_neto::numeric
    """)

    # liquidacion_detalles
    op.execute("""
        ALTER TABLE liquidacion_detalles
            ALTER COLUMN monto_conciliado    TYPE NUMERIC(12,2) USING monto_conciliado::numeric,
            ALTER COLUMN porcentaje_comision TYPE NUMERIC(5,4)  USING porcentaje_comision::numeric,
            ALTER COLUMN monto_comision      TYPE NUMERIC(12,2) USING monto_comision::numeric,
            ALTER COLUMN monto_neto          TYPE NUMERIC(12,2) USING monto_neto::numeric
    """)

    # cheques
    op.execute("""
        ALTER TABLE cheques
            ALTER COLUMN monto    TYPE NUMERIC(12,2) USING monto::numeric,
            ALTER COLUMN comision TYPE NUMERIC(12,2) USING comision::numeric
    """)

    # arqueos_diarios
    op.execute("""
        ALTER TABLE arqueos_diarios
            ALTER COLUMN saldo_inicial   TYPE NUMERIC(12,2) USING saldo_inicial::numeric,
            ALTER COLUMN pesos_agregados TYPE NUMERIC(12,2) USING pesos_agregados::numeric,
            ALTER COLUMN ingresos        TYPE NUMERIC(12,2) USING ingresos::numeric
    """)

    # ordenes_de_pago
    op.execute("""
        ALTER TABLE ordenes_de_pago
            ALTER COLUMN importe TYPE NUMERIC(12,2) USING importe::numeric
    """)

    # pagos
    op.execute("""
        ALTER TABLE pagos
            ALTER COLUMN monto TYPE NUMERIC(12,2) USING monto::numeric
    """)

    # gastos
    op.execute("""
        ALTER TABLE gastos
            ALTER COLUMN monto TYPE NUMERIC(12,2) USING monto::numeric
    """)

    # planilla_rows
    op.execute("""
        ALTER TABLE planilla_rows
            ALTER COLUMN monto           TYPE NUMERIC(12,2) USING monto::numeric,
            ALTER COLUMN monto_acreditado TYPE NUMERIC(12,2) USING monto_acreditado::numeric
    """)

    # patrones_aprendidos
    op.execute("""
        ALTER TABLE patrones_aprendidos
            ALTER COLUMN monto_tipico TYPE NUMERIC(12,2) USING monto_tipico::numeric
    """)

    # movimientos_banco
    op.execute("""
        ALTER TABLE movimientos_banco
            ALTER COLUMN monto TYPE NUMERIC(12,2) USING monto::numeric,
            ALTER COLUMN saldo TYPE NUMERIC(12,2) USING saldo::numeric
    """)

    # asiento_detalle
    op.execute("""
        ALTER TABLE asiento_detalle
            ALTER COLUMN debe  TYPE NUMERIC(12,2) USING debe::numeric,
            ALTER COLUMN haber TYPE NUMERIC(12,2) USING haber::numeric
    """)


def downgrade() -> None:
    # asiento_detalle
    op.execute("""
        ALTER TABLE asiento_detalle
            ALTER COLUMN debe  TYPE DOUBLE PRECISION USING debe::double precision,
            ALTER COLUMN haber TYPE DOUBLE PRECISION USING haber::double precision
    """)

    # movimientos_banco
    op.execute("""
        ALTER TABLE movimientos_banco
            ALTER COLUMN monto TYPE DOUBLE PRECISION USING monto::double precision,
            ALTER COLUMN saldo TYPE DOUBLE PRECISION USING saldo::double precision
    """)

    # patrones_aprendidos
    op.execute("""
        ALTER TABLE patrones_aprendidos
            ALTER COLUMN monto_tipico TYPE DOUBLE PRECISION USING monto_tipico::double precision
    """)

    # planilla_rows
    op.execute("""
        ALTER TABLE planilla_rows
            ALTER COLUMN monto            TYPE DOUBLE PRECISION USING monto::double precision,
            ALTER COLUMN monto_acreditado TYPE DOUBLE PRECISION USING monto_acreditado::double precision
    """)

    # gastos
    op.execute("""
        ALTER TABLE gastos
            ALTER COLUMN monto TYPE DOUBLE PRECISION USING monto::double precision
    """)

    # pagos
    op.execute("""
        ALTER TABLE pagos
            ALTER COLUMN monto TYPE DOUBLE PRECISION USING monto::double precision
    """)

    # ordenes_de_pago
    op.execute("""
        ALTER TABLE ordenes_de_pago
            ALTER COLUMN importe TYPE DOUBLE PRECISION USING importe::double precision
    """)

    # arqueos_diarios
    op.execute("""
        ALTER TABLE arqueos_diarios
            ALTER COLUMN saldo_inicial   TYPE DOUBLE PRECISION USING saldo_inicial::double precision,
            ALTER COLUMN pesos_agregados TYPE DOUBLE PRECISION USING pesos_agregados::double precision,
            ALTER COLUMN ingresos        TYPE DOUBLE PRECISION USING ingresos::double precision
    """)

    # cheques
    op.execute("""
        ALTER TABLE cheques
            ALTER COLUMN monto    TYPE DOUBLE PRECISION USING monto::double precision,
            ALTER COLUMN comision TYPE DOUBLE PRECISION USING comision::double precision
    """)

    # liquidacion_detalles
    op.execute("""
        ALTER TABLE liquidacion_detalles
            ALTER COLUMN monto_conciliado    TYPE DOUBLE PRECISION USING monto_conciliado::double precision,
            ALTER COLUMN porcentaje_comision TYPE DOUBLE PRECISION USING porcentaje_comision::double precision,
            ALTER COLUMN monto_comision      TYPE DOUBLE PRECISION USING monto_comision::double precision,
            ALTER COLUMN monto_neto          TYPE DOUBLE PRECISION USING monto_neto::double precision
    """)

    # liquidaciones
    op.execute("""
        ALTER TABLE liquidaciones
            ALTER COLUMN total_conciliado TYPE DOUBLE PRECISION USING total_conciliado::double precision,
            ALTER COLUMN total_comision   TYPE DOUBLE PRECISION USING total_comision::double precision,
            ALTER COLUMN total_neto       TYPE DOUBLE PRECISION USING total_neto::double precision
    """)
