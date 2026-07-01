"""add_license_disk_fields_to_taxi

Revision ID: 9522b1ecf6a2
Revises: 12727c40ba86
Create Date: 2026-07-01 08:30:00.044684

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9522b1ecf6a2'
down_revision: Union[str, None] = '12727c40ba86'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('taxis', sa.Column('license_disk_number', sa.String(length=100), nullable=True))
    op.add_column('taxis', sa.Column('license_disk_expiry', sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column('taxis', 'license_disk_expiry')
    op.drop_column('taxis', 'license_disk_number')
