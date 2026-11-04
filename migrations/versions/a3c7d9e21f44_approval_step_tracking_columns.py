"""approval step tracking columns

Revision ID: a3c7d9e21f44
Revises: 5f84659214f9
Create Date: 2026-11-04 10:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3c7d9e21f44'
down_revision: Union[str, None] = '5f84659214f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('approval_steps', sa.Column('last_viewed_at', sa.DateTime(), nullable=True))
    op.add_column('approval_steps', sa.Column('view_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('approval_steps', sa.Column('approved_at', sa.DateTime(), nullable=True))
    op.add_column('approval_steps', sa.Column('rejected_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('approval_steps', 'rejected_at')
    op.drop_column('approval_steps', 'approved_at')
    op.drop_column('approval_steps', 'view_count')
    op.drop_column('approval_steps', 'last_viewed_at')
