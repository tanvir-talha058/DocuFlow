"""employee password hash

Revision ID: b2e4f6a9c103
Revises: f1b8a0c3d7e2
Create Date: 2026-11-04 14:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2e4f6a9c103'
down_revision: Union[str, None] = 'f1b8a0c3d7e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('employee_cache', sa.Column('password_hash', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('employee_cache', 'password_hash')
