"""employee settings columns

Revision ID: f1b8a0c3d7e2
Revises: a3c7d9e21f44
Create Date: 2026-11-04 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1b8a0c3d7e2'
down_revision: Union[str, None] = 'a3c7d9e21f44'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('employee_cache', sa.Column('theme_preference', sa.String(length=10), nullable=False, server_default='system'))
    op.add_column('employee_cache', sa.Column('notify_on_decision', sa.Boolean(), nullable=False, server_default='1'))


def downgrade() -> None:
    op.drop_column('employee_cache', 'notify_on_decision')
    op.drop_column('employee_cache', 'theme_preference')
