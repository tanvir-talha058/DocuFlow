"""notifications table

Revision ID: d5e7f9a1b326
Revises: c4d6e8f0a215
Create Date: 2026-11-05 12:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd5e7f9a1b326'
down_revision: Union[str, None] = 'c4d6e8f0a215'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'notifications',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('employee_id', sa.String(length=36), nullable=False),
        sa.Column('chain_id', sa.String(length=36), nullable=True),
        sa.Column('type', sa.String(length=30), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('body', sa.String(length=500), nullable=True),
        sa.Column('link', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('read_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['employee_id'], ['employee_cache.id']),
        sa.ForeignKeyConstraint(['chain_id'], ['approval_chains.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_notifications_employee_id', 'notifications', ['employee_id'])
    op.create_index('ix_notifications_created_at', 'notifications', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_notifications_created_at', table_name='notifications')
    op.drop_index('ix_notifications_employee_id', table_name='notifications')
    op.drop_table('notifications')
