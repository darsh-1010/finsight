"""Update legacy published statuses

Revision ID: 39dd9a9c7cb3
Revises: 2338ea580fe6
Create Date: 2026-06-02 18:21:23.077871

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '39dd9a9c7cb3'
down_revision: Union[str, Sequence[str], None] = '17ce2c824ffd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE insightstatus ADD VALUE IF NOT EXISTS 'rejected'")
    op.execute("UPDATE insights SET status = 'rejected' WHERE status = 'published'")


def downgrade() -> None:
    """Downgrade schema."""
    pass
