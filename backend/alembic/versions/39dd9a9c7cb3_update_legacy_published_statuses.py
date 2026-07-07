"""Update legacy published statuses

Revision ID: 39dd9a9c7cb3
Revises: 2338ea580fe6
Create Date: 2026-06-02 18:21:23.077871

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "39dd9a9c7cb3"
down_revision: str | Sequence[str] | None = "17ce2c824ffd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE insightstatus ADD VALUE IF NOT EXISTS 'rejected'")
    op.execute("UPDATE insights SET status = 'rejected' WHERE status = 'published'")


def downgrade() -> None:
    """Downgrade schema."""
    pass
