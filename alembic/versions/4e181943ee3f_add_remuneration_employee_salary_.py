"""add_remuneration_employee_salary_payments

Revision ID: 4e181943ee3f
Revises: d5e6f7a8b9c0
Create Date: 2026-06-18 16:49:38.434649

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4e181943ee3f'
down_revision: Union[str, None] = 'd5e6f7a8b9c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('remuneration_packages',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('organisation_id', sa.String(length=32), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('base_salary_cents', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['organisation_id'], ['organisations.id']),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organisation_id', 'name')
    )
    op.create_index(op.f('ix_remuneration_packages_organisation_id'), 'remuneration_packages', ['organisation_id'], unique=False)

    op.create_table('employees',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('organisation_id', sa.String(length=32), nullable=False),
    sa.Column('driver_id', sa.String(length=32), nullable=False),
    sa.Column('remuneration_package_id', sa.String(length=32), nullable=True),
    sa.Column('employment_status', sa.String(length=20), nullable=False),
    sa.Column('hire_date', sa.Date(), nullable=False),
    sa.Column('termination_date', sa.Date(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['driver_id'], ['drivers.id']),
    sa.ForeignKeyConstraint(['organisation_id'], ['organisations.id']),
    sa.ForeignKeyConstraint(['remuneration_package_id'], ['remuneration_packages.id']),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organisation_id', 'driver_id')
    )
    op.create_index(op.f('ix_employees_organisation_id'), 'employees', ['organisation_id'], unique=False)

    op.create_table('salary_payments',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('organisation_id', sa.String(length=32), nullable=False),
    sa.Column('employee_id', sa.String(length=32), nullable=False),
    sa.Column('amount_cents', sa.Integer(), nullable=False),
    sa.Column('payment_date', sa.Date(), nullable=False),
    sa.Column('payment_method', sa.String(length=20), nullable=False),
    sa.Column('reference', sa.String(length=255), nullable=True),
    sa.Column('notes', sa.String(length=500), nullable=True),
    sa.Column('created_by', sa.String(length=32), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id']),
    sa.ForeignKeyConstraint(['employee_id'], ['employees.id']),
    sa.ForeignKeyConstraint(['organisation_id'], ['organisations.id']),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_salary_payments_org_employee_date', 'salary_payments', ['organisation_id', 'employee_id', 'payment_date'], unique=False)
    op.create_index(op.f('ix_salary_payments_organisation_id'), 'salary_payments', ['organisation_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_salary_payments_organisation_id'), table_name='salary_payments')
    op.drop_index('ix_salary_payments_org_employee_date', table_name='salary_payments')
    op.drop_table('salary_payments')
    op.drop_index(op.f('ix_employees_organisation_id'), table_name='employees')
    op.drop_table('employees')
    op.drop_index(op.f('ix_remuneration_packages_organisation_id'), table_name='remuneration_packages')
    op.drop_table('remuneration_packages')
