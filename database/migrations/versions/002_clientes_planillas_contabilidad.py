"""clientes, planillas, contabilidad, cheques, pagos, gastos + estados de conciliacion

Revision ID: 002
Revises: 001
Create Date: 2026-05-21

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # clientes
    op.create_table(
        'clientes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nombre', sa.String(200), nullable=False),
        sa.Column('cuit', sa.String(20), nullable=True),
        sa.Column('titular', sa.String(200), nullable=True),
        sa.Column('cuenta', sa.String(100), nullable=True),
        sa.Column('comision', sa.Numeric(5, 2), nullable=False, server_default='0'),
        sa.Column('forma_pago', sa.String(30), nullable=True),
        sa.Column('activo', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_clientes_nombre', 'clientes', ['nombre'])
    op.create_index('ix_clientes_cuit', 'clientes', ['cuit'])

    # planillas_cliente
    op.create_table(
        'planillas_cliente',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('cliente_id', sa.Integer(), nullable=False),
        sa.Column('nombre', sa.String(200), nullable=False),
        sa.Column('periodo', sa.String(20), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['cliente_id'], ['clientes.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_planillas_cliente_cliente_id', 'planillas_cliente', ['cliente_id'])

    # movimientos_planilla
    op.create_table(
        'movimientos_planilla',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('planilla_id', sa.Integer(), nullable=False),
        sa.Column('fecha', sa.Date(), nullable=False),
        sa.Column('descripcion', sa.Text(), nullable=False),
        sa.Column('monto', sa.Numeric(15, 2), nullable=False),
        sa.Column('referencia', sa.String(100), nullable=True),
        sa.Column('estado', sa.String(20), nullable=False, server_default='pendiente'),
        sa.Column('fecha_acreditacion', sa.Date(), nullable=True),
        sa.Column('datos_faltantes', sa.Text(), nullable=True),
        sa.Column('observacion', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['planilla_id'], ['planillas_cliente.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_movimientos_planilla_planilla_id', 'movimientos_planilla', ['planilla_id'])
    op.create_index('ix_movimientos_planilla_estado', 'movimientos_planilla', ['estado'])

    # cuentas_contables (catálogo)
    op.create_table(
        'cuentas_contables',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('codigo', sa.String(20), nullable=False),
        sa.Column('nombre', sa.String(100), nullable=False),
        sa.Column('tipo', sa.String(20), nullable=False),
        sa.Column('naturaleza', sa.String(10), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('codigo'),
        sa.UniqueConstraint('nombre'),
    )

    # asientos_contables
    op.create_table(
        'asientos_contables',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('fecha', sa.Date(), nullable=False),
        sa.Column('descripcion', sa.Text(), nullable=False),
        sa.Column('origen', sa.String(30), nullable=False),
        sa.Column('origen_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_asientos_contables_fecha', 'asientos_contables', ['fecha'])
    op.create_index('ix_asientos_contables_origen', 'asientos_contables', ['origen'])
    op.create_index('ix_asientos_contables_origen_id', 'asientos_contables', ['origen_id'])

    # lineas_asiento
    op.create_table(
        'lineas_asiento',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('asiento_id', sa.Integer(), nullable=False),
        sa.Column('cuenta_id', sa.Integer(), nullable=False),
        sa.Column('debe', sa.Numeric(15, 2), nullable=False, server_default='0'),
        sa.Column('haber', sa.Numeric(15, 2), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['asiento_id'], ['asientos_contables.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['cuenta_id'], ['cuentas_contables.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_lineas_asiento_asiento_id', 'lineas_asiento', ['asiento_id'])
    op.create_index('ix_lineas_asiento_cuenta_id', 'lineas_asiento', ['cuenta_id'])

    # cheques
    op.create_table(
        'cheques',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('cliente_id', sa.Integer(), nullable=False),
        sa.Column('numero', sa.String(50), nullable=False),
        sa.Column('banco_emisor', sa.String(100), nullable=True),
        sa.Column('fecha_emision', sa.Date(), nullable=False),
        sa.Column('fecha_cobro', sa.Date(), nullable=False),
        sa.Column('monto', sa.Numeric(15, 2), nullable=False),
        sa.Column('comision', sa.Numeric(15, 2), nullable=False, server_default='0'),
        sa.Column('estado', sa.String(20), nullable=False, server_default='cargado'),
        sa.Column('fecha_acreditacion', sa.Date(), nullable=True),
        sa.Column('motivo_rechazo', sa.String(200), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['cliente_id'], ['clientes.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_cheques_cliente_id', 'cheques', ['cliente_id'])
    op.create_index('ix_cheques_numero', 'cheques', ['numero'])
    op.create_index('ix_cheques_estado', 'cheques', ['estado'])

    # pagos
    op.create_table(
        'pagos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('cliente_id', sa.Integer(), nullable=False),
        sa.Column('fecha', sa.Date(), nullable=False),
        sa.Column('monto', sa.Numeric(15, 2), nullable=False),
        sa.Column('medio', sa.String(20), nullable=False),
        sa.Column('referencia', sa.String(100), nullable=True),
        sa.Column('observacion', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['cliente_id'], ['clientes.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_pagos_cliente_id', 'pagos', ['cliente_id'])
    op.create_index('ix_pagos_fecha', 'pagos', ['fecha'])

    # gastos
    op.create_table(
        'gastos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('fecha', sa.Date(), nullable=False),
        sa.Column('concepto', sa.String(200), nullable=False),
        sa.Column('monto', sa.Numeric(15, 2), nullable=False),
        sa.Column('medio', sa.String(20), nullable=False),
        sa.Column('cuenta_gasto_id', sa.Integer(), nullable=True),
        sa.Column('observacion', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['cuenta_gasto_id'], ['cuentas_contables.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_gastos_fecha', 'gastos', ['fecha'])

    # === Extensiones a bank_transactions ===
    op.add_column('bank_transactions', sa.Column('cliente_id', sa.Integer(), nullable=True))
    op.add_column('bank_transactions', sa.Column('planilla_movimiento_id', sa.Integer(), nullable=True))
    op.add_column('bank_transactions', sa.Column('estado', sa.String(20), nullable=False, server_default='pendiente'))
    op.add_column('bank_transactions', sa.Column('fecha_acreditacion_original', sa.Date(), nullable=True))
    op.add_column('bank_transactions', sa.Column('es_manual', sa.Boolean(), nullable=False, server_default='false'))
    op.create_foreign_key(
        'fk_bank_tx_cliente', 'bank_transactions', 'clientes',
        ['cliente_id'], ['id'], ondelete='SET NULL'
    )
    op.create_foreign_key(
        'fk_bank_tx_mov_planilla', 'bank_transactions', 'movimientos_planilla',
        ['planilla_movimiento_id'], ['id'], ondelete='SET NULL'
    )
    op.create_index('ix_bank_transactions_cliente_id', 'bank_transactions', ['cliente_id'])
    op.create_index('ix_bank_transactions_planilla_movimiento_id', 'bank_transactions', ['planilla_movimiento_id'])
    op.create_index('ix_bank_transactions_estado', 'bank_transactions', ['estado'])

    # === Extensiones a reconciliation_items ===
    op.add_column('reconciliation_items', sa.Column('planilla_movimiento_id', sa.Integer(), nullable=True))
    op.add_column('reconciliation_items', sa.Column('estado', sa.String(20), nullable=False, server_default='acreditado'))
    op.add_column('reconciliation_items', sa.Column('observacion', sa.Text(), nullable=True))
    op.create_foreign_key(
        'fk_recon_item_mov_planilla', 'reconciliation_items', 'movimientos_planilla',
        ['planilla_movimiento_id'], ['id'], ondelete='SET NULL'
    )
    op.create_index('ix_reconciliation_items_estado', 'reconciliation_items', ['estado'])

    # Seed inicial del plan de cuentas (mapa del contador)
    cuentas = sa.table(
        'cuentas_contables',
        sa.column('codigo', sa.String),
        sa.column('nombre', sa.String),
        sa.column('tipo', sa.String),
        sa.column('naturaleza', sa.String),
    )
    op.bulk_insert(cuentas, [
        {'codigo': '1.1.01', 'nombre': 'Banco',            'tipo': 'activo',   'naturaleza': 'deudora'},
        {'codigo': '1.1.02', 'nombre': 'Efectivo',         'tipo': 'activo',   'naturaleza': 'deudora'},
        {'codigo': '1.2.01', 'nombre': 'Credito',          'tipo': 'activo',   'naturaleza': 'deudora'},
        {'codigo': '2.1.01', 'nombre': 'Pasivo Corriente', 'tipo': 'pasivo',   'naturaleza': 'acreedora'},
        {'codigo': '2.1.02', 'nombre': 'Pasivo Cliente',   'tipo': 'pasivo',   'naturaleza': 'acreedora'},
        {'codigo': '4.1.01', 'nombre': 'Comisiones',       'tipo': 'ingreso',  'naturaleza': 'acreedora'},
        {'codigo': '5.1.01', 'nombre': 'Gasto',            'tipo': 'egreso',   'naturaleza': 'deudora'},
    ])


def downgrade() -> None:
    op.drop_index('ix_reconciliation_items_estado', table_name='reconciliation_items')
    op.drop_constraint('fk_recon_item_mov_planilla', 'reconciliation_items', type_='foreignkey')
    op.drop_column('reconciliation_items', 'observacion')
    op.drop_column('reconciliation_items', 'estado')
    op.drop_column('reconciliation_items', 'planilla_movimiento_id')

    op.drop_index('ix_bank_transactions_estado', table_name='bank_transactions')
    op.drop_index('ix_bank_transactions_planilla_movimiento_id', table_name='bank_transactions')
    op.drop_index('ix_bank_transactions_cliente_id', table_name='bank_transactions')
    op.drop_constraint('fk_bank_tx_mov_planilla', 'bank_transactions', type_='foreignkey')
    op.drop_constraint('fk_bank_tx_cliente', 'bank_transactions', type_='foreignkey')
    op.drop_column('bank_transactions', 'es_manual')
    op.drop_column('bank_transactions', 'fecha_acreditacion_original')
    op.drop_column('bank_transactions', 'estado')
    op.drop_column('bank_transactions', 'planilla_movimiento_id')
    op.drop_column('bank_transactions', 'cliente_id')

    op.drop_table('gastos')
    op.drop_table('pagos')
    op.drop_table('cheques')
    op.drop_table('lineas_asiento')
    op.drop_table('asientos_contables')
    op.drop_table('cuentas_contables')
    op.drop_table('movimientos_planilla')
    op.drop_table('planillas_cliente')
    op.drop_table('clientes')
