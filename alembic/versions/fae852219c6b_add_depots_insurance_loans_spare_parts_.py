"""add_depots_insurance_loans_spare_parts_mechanic_payments

Revision ID: fae852219c6b
Revises: 4e181943ee3f
Create Date: 2026-06-18 18:05:43.290487

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fae852219c6b'
down_revision: Union[str, None] = '4e181943ee3f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('depots',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('organisation_id', sa.String(length=32), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('depot_type', sa.String(length=20), nullable=False),
    sa.Column('address', sa.String(length=500), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['organisation_id'], ['organisations.id']),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organisation_id', 'name')
    )
    op.create_index(op.f('ix_depots_organisation_id'), 'depots', ['organisation_id'], unique=False)

    op.create_table('insurance',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('organisation_id', sa.String(length=32), nullable=False),
    sa.Column('taxi_id', sa.String(length=32), nullable=False),
    sa.Column('insurer', sa.String(length=255), nullable=False),
    sa.Column('policy_number', sa.String(length=255), nullable=True),
    sa.Column('monthly_premium_cents', sa.Integer(), nullable=False),
    sa.Column('start_date', sa.Date(), nullable=False),
    sa.Column('end_date', sa.Date(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['organisation_id'], ['organisations.id']),
    sa.ForeignKeyConstraint(['taxi_id'], ['taxis.id']),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_insurance_organisation_id'), 'insurance', ['organisation_id'], unique=False)

    op.create_table('mechanic_payments',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('organisation_id', sa.String(length=32), nullable=False),
    sa.Column('depot_id', sa.String(length=32), nullable=False),
    sa.Column('taxi_id', sa.String(length=32), nullable=True),
    sa.Column('mechanic_name', sa.String(length=255), nullable=False),
    sa.Column('description', sa.String(length=500), nullable=True),
    sa.Column('amount_cents', sa.Integer(), nullable=False),
    sa.Column('payment_date', sa.Date(), nullable=False),
    sa.Column('payment_method', sa.String(length=20), nullable=False),
    sa.Column('created_by', sa.String(length=32), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id']),
    sa.ForeignKeyConstraint(['depot_id'], ['depots.id']),
    sa.ForeignKeyConstraint(['organisation_id'], ['organisations.id']),
    sa.ForeignKeyConstraint(['taxi_id'], ['taxis.id']),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_mechanic_payments_org_depot_date', 'mechanic_payments', ['organisation_id', 'depot_id', 'payment_date'], unique=False)
    op.create_index(op.f('ix_mechanic_payments_organisation_id'), 'mechanic_payments', ['organisation_id'], unique=False)

    op.create_table('spare_part_purchases',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('organisation_id', sa.String(length=32), nullable=False),
    sa.Column('depot_id', sa.String(length=32), nullable=False),
    sa.Column('taxi_id', sa.String(length=32), nullable=True),
    sa.Column('description', sa.String(length=500), nullable=False),
    sa.Column('cost_total_cents', sa.Integer(), nullable=False),
    sa.Column('date', sa.Date(), nullable=False),
    sa.Column('created_by', sa.String(length=32), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id']),
    sa.ForeignKeyConstraint(['depot_id'], ['depots.id']),
    sa.ForeignKeyConstraint(['organisation_id'], ['organisations.id']),
    sa.ForeignKeyConstraint(['taxi_id'], ['taxis.id']),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_spare_part_purchases_organisation_id'), 'spare_part_purchases', ['organisation_id'], unique=False)
    op.create_index('ix_spare_parts_org_taxi_date', 'spare_part_purchases', ['organisation_id', 'taxi_id', 'date'], unique=False)

    op.create_table('taxi_loans',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('organisation_id', sa.String(length=32), nullable=False),
    sa.Column('taxi_id', sa.String(length=32), nullable=False),
    sa.Column('lender', sa.String(length=255), nullable=False),
    sa.Column('total_amount_cents', sa.Integer(), nullable=False),
    sa.Column('remaining_balance_cents', sa.Integer(), nullable=False),
    sa.Column('monthly_instalment_cents', sa.Integer(), nullable=False),
    sa.Column('start_date', sa.Date(), nullable=False),
    sa.Column('end_date', sa.Date(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['organisation_id'], ['organisations.id']),
    sa.ForeignKeyConstraint(['taxi_id'], ['taxis.id']),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_taxi_loans_organisation_id'), 'taxi_loans', ['organisation_id'], unique=False)

    op.create_table('loan_payments',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('organisation_id', sa.String(length=32), nullable=False),
    sa.Column('loan_id', sa.String(length=32), nullable=False),
    sa.Column('amount_cents', sa.Integer(), nullable=False),
    sa.Column('payment_date', sa.Date(), nullable=False),
    sa.Column('reference', sa.String(length=255), nullable=True),
    sa.Column('created_by', sa.String(length=32), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id']),
    sa.ForeignKeyConstraint(['loan_id'], ['taxi_loans.id']),
    sa.ForeignKeyConstraint(['organisation_id'], ['organisations.id']),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_loan_payments_org_loan_date', 'loan_payments', ['organisation_id', 'loan_id', 'payment_date'], unique=False)
    op.create_index(op.f('ix_loan_payments_organisation_id'), 'loan_payments', ['organisation_id'], unique=False)

    op.add_column('employees', sa.Column('depot_id', sa.String(length=32), nullable=True))
    op.add_column('remuneration_packages', sa.Column('payment_frequency', sa.String(length=20), server_default='monthly', nullable=False))


def downgrade() -> None:
    op.drop_column('remuneration_packages', 'payment_frequency')
    op.drop_column('employees', 'depot_id')
    op.drop_index(op.f('ix_loan_payments_organisation_id'), table_name='loan_payments')
    op.drop_index('ix_loan_payments_org_loan_date', table_name='loan_payments')
    op.drop_table('loan_payments')
    op.drop_index(op.f('ix_taxi_loans_organisation_id'), table_name='taxi_loans')
    op.drop_table('taxi_loans')
    op.drop_index('ix_spare_parts_org_taxi_date', table_name='spare_part_purchases')
    op.drop_index(op.f('ix_spare_part_purchases_organisation_id'), table_name='spare_part_purchases')
    op.drop_table('spare_part_purchases')
    op.drop_index(op.f('ix_mechanic_payments_organisation_id'), table_name='mechanic_payments')
    op.drop_index('ix_mechanic_payments_org_depot_date', table_name='mechanic_payments')
    op.drop_table('mechanic_payments')
    op.drop_index(op.f('ix_insurance_organisation_id'), table_name='insurance')
    op.drop_table('insurance')
    op.drop_index(op.f('ix_depots_organisation_id'), table_name='depots')
    op.drop_table('depots')
