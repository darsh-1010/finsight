"""change audit_logs entity_id to string

Revision ID: c683546cb6d2
Revises: a855713e88bf
Create Date: 2026-04-24 11:28:08.436798

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c683546cb6d2"
down_revision: str | Sequence[str] | None = "a855713e88bf"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Alter entity_id to String with explicit cast
    op.alter_column(
        "audit_logs",
        "entity_id",
        existing_type=sa.BIGINT(),
        type_=sa.String(),
        existing_nullable=True,
        postgresql_using="entity_id::varchar",
    )


def downgrade() -> None:
    # Attempt to cast back to BIGINT
    op.alter_column(
        "audit_logs",
        "entity_id",
        existing_type=sa.String(),
        type_=sa.BIGINT(),
        existing_nullable=True,
        postgresql_using="entity_id::bigint",
    )
