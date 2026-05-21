"""initial schema

Revision ID: 001
Revises: 
Create Date: 2026-05-21

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # users
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('full_name', sa.String(150), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
    )
    op.create_index('ix_users_email', 'users', ['email'])

    # bank_accounts
    op.create_table(
        'bank_accounts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('account_number', sa.String(50), nullable=False),
        sa.Column('bank_name', sa.String(100), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False, server_default='ARS'),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # bank_statements
    op.create_table(
        'bank_statements',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('period_start', sa.Date(), nullable=False),
        sa.Column('period_end', sa.Date(), nullable=False),
        sa.Column('opening_balance', sa.Numeric(15, 2), nullable=False),
        sa.Column('closing_balance', sa.Numeric(15, 2), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='draft'),
        sa.Column('imported_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['account_id'], ['bank_accounts.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_bank_statements_account_id', 'bank_statements', ['account_id'])

    # bank_transactions
    op.create_table(
        'bank_transactions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('statement_id', sa.Integer(), nullable=False),
        sa.Column('transaction_date', sa.Date(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('amount', sa.Numeric(15, 2), nullable=False),
        sa.Column('reference', sa.String(100), nullable=True),
        sa.Column('is_reconciled', sa.Boolean(), nullable=False, server_default='false'),
        sa.ForeignKeyConstraint(['statement_id'], ['bank_statements.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_bank_transactions_statement_id', 'bank_transactions', ['statement_id'])
    op.create_index('ix_bank_transactions_date', 'bank_transactions', ['transaction_date'])

    # accounting_entries
    op.create_table(
        'accounting_entries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('entry_date', sa.Date(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('amount', sa.Numeric(15, 2), nullable=False),
        sa.Column('reference', sa.String(100), nullable=True),
        sa.Column('is_reconciled', sa.Boolean(), nullable=False, server_default='false'),
        sa.ForeignKeyConstraint(['account_id'], ['bank_accounts.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_accounting_entries_account_id', 'accounting_entries', ['account_id'])
    op.create_index('ix_accounting_entries_date', 'accounting_entries', ['entry_date'])

    # reconciliations
    op.create_table(
        'reconciliations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('statement_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='open'),
        sa.Column('difference', sa.Numeric(15, 2), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['statement_id'], ['bank_statements.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('statement_id'),
    )

    # reconciliation_items
    op.create_table(
        'reconciliation_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('reconciliation_id', sa.Integer(), nullable=False),
        sa.Column('bank_transaction_id', sa.Integer(), nullable=True),
        sa.Column('accounting_entry_id', sa.Integer(), nullable=True),
        sa.Column('match_type', sa.String(20), nullable=False, server_default='manual'),
        sa.Column('matched_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('matched_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['accounting_entry_id'], ['accounting_entries.id']),
        sa.ForeignKeyConstraint(['bank_transaction_id'], ['bank_transactions.id']),
        sa.ForeignKeyConstraint(['matched_by'], ['users.id']),
        sa.ForeignKeyConstraint(['reconciliation_id'], ['reconciliations.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_reconciliation_items_reconciliation_id', 'reconciliation_items', ['reconciliation_id'])


def downgrade() -> None:
    op.drop_table('reconciliation_items')
    op.drop_table('reconciliations')
    op.drop_table('accounting_entries')
    op.drop_table('bank_transactions')
    op.drop_table('bank_statements')
    op.drop_table('bank_accounts')
    op.drop_table('users')
