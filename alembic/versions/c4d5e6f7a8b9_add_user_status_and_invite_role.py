"""add_user_status_and_invite_role

Revision ID: c4d5e6f7a8b9
Revises: a0b0bc4bc7d4
Create Date: 2026-06-18 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4d5e6f7a8b9'
down_revision: Union[str, None] = 'a0b0bc4bc7d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('status', sa.String(length=10), nullable=False, server_default='active'))
    op.add_column('invite_tokens', sa.Column('role', sa.String(length=15), nullable=False, server_default='manager'))


def downgrade() -> None:
    op.drop_column('invite_tokens', 'role')
    op.drop_column('users', 'status')
