"""add organisation_settings for reporting

Revision ID: 8dce51640df6
Revises: fae852219c6b
Create Date: 2026-06-18 23:00:13.788499

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8dce51640df6'
down_revision: Union[str, None] = 'fae852219c6b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('organisation_settings',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('organisation_id', sa.String(length=32), nullable=False),
    sa.Column('vat_registered', sa.Boolean(), nullable=False),
    sa.Column('vat_number', sa.String(length=50), nullable=True),
    sa.Column('financial_year_end', sa.Date(), nullable=False),
    sa.Column('default_currency', sa.String(length=3), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['organisation_id'], ['organisations.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organisation_id')
    )


def downgrade() -> None:
    op.drop_table('organisation_settings')
