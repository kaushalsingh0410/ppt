"""rename last_upate to last_update

Revision ID: 0199c179ca1a
Revises: db6644dbe44a
Create Date: 2026-02-09 13:58:57.362003

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0199c179ca1a'
down_revision: Union[str, Sequence[str], None] = 'db6644dbe44a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        'thread',
        'last_upate',
        new_column_name='last_update',
        existing_type=sa.String(),
        nullable=False,
        existing_server_default='update'
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        'thread',
        'last_update',
        new_column_name='last_upate',
        existing_type=sa.String(),
        nullable=False,
        existing_server_default='update'
    )
