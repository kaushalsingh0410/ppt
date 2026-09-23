"""initial schema

Revision ID: 0001
Revises: 
Create Date: 2026-09-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'thread',
        sa.Column('thread_id', sa.String(), nullable=False),
        sa.Column('topic', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('last_update', sa.String(), server_default='update', nullable=False),
        sa.Column('img_path', sa.String(), nullable=True),
        sa.Column('num_slide', sa.Integer(), server_default='5', nullable=False),
        sa.PrimaryKeyConstraint('thread_id'),
    )
    op.create_index(op.f('ix_thread_thread_id'), 'thread', ['thread_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_thread_thread_id'), table_name='thread')
    op.drop_table('thread')