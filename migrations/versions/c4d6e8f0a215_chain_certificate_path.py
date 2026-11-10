"""chain certificate path

Revision ID: c4d6e8f0a215
Revises: b2e4f6a9c103
Create Date: 2026-11-05 12:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4d6e8f0a215'
down_revision: Union[str, None] = 'b2e4f6a9c103'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('approval_chains', sa.Column('certificate_path', sa.String(length=1000), nullable=True))


def downgrade() -> None:
    op.drop_column('approval_chains', 'certificate_path')
