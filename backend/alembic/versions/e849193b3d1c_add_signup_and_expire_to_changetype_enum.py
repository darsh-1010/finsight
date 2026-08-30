"""add signup and expire to changetype enum

Revision ID: e849193b3d1c
Revises: b5647e783930
Create Date: 2026-01-05 14:23:33.785130

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e849193b3d1c"
down_revision: str | Sequence[str] | None = "b5647e783930"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Use autocommit block for PostgreSQL enum ALTER TYPE
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE changetype ADD VALUE 'signup'")
        op.execute("ALTER TYPE changetype ADD VALUE 'expire'")


def downgrade() -> None:
    """Downgrade schema."""
    # Enums are hard to downgrade in Postgres without recreating the type.
    # We will leave as is for now as it's safe to have extra values.
    pass
