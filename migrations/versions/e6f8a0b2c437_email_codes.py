"""email verification codes (signup OTP + password reset)

Revision ID: e6f8a0b2c437
Revises: d5e7f9a1b326
Create Date: 2026-11-10 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e6f8a0b2c437'
down_revision: Union[str, None] = 'd5e7f9a1b326'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'email_codes',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('purpose', sa.String(length=10), nullable=False),
        sa.Column('code_hash', sa.String(length=64), nullable=False),
        sa.Column('payload_json', sa.Text(), nullable=True),
        sa.Column('attempts', sa.Integer(), server_default='0', nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('consumed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_email_codes_email', 'email_codes', ['email'])


def downgrade() -> None:
    op.drop_index('ix_email_codes_email', table_name='email_codes')
    op.drop_table('email_codes')
