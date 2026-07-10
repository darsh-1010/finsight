"""create_notification_tables

Revision ID: 17ce2c824ffd
Revises: de68ecd1cb6c
Create Date: 2026-06-01 17:13:11.657135

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "17ce2c824ffd"
down_revision: str | Sequence[str] | None = "de68ecd1cb6c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create tables
    op.create_table(
        "notifications",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("notification_type", sa.String(), nullable=False),
        sa.Column("entity_type", sa.String(), nullable=True),
        sa.Column("entity_id", sa.String(), nullable=True),
        sa.Column(
            "priority",
            sa.Enum(
                "low", "medium", "high", name="notificationpriority", native_enum=False
            ),
            nullable=False,
            server_default="medium",
        ),
        sa.Column("action_url", sa.String(), nullable=True),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_notifications_id"), "notifications", ["id"], unique=False)

    op.create_table(
        "notification_audience",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("notification_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "audience_type",
            sa.Enum(
                "all", "tier", "user", "admin", name="audiencetype", native_enum=False
            ),
            nullable=False,
        ),
        sa.Column("audience_id", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(
            ["notification_id"], ["notifications.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_notification_audience_id"),
        "notification_audience",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notification_audience_notification_id"),
        "notification_audience",
        ["notification_id"],
        unique=False,
    )

    op.create_table(
        "user_notification_reads",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("notification_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["notification_id"], ["notifications.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "notification_id", "user_id", name="uq_notification_user_read"
        ),
    )
    op.create_index(
        op.f("ix_user_notification_reads_notification_id"),
        "user_notification_reads",
        ["notification_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_notification_reads_user_id"),
        "user_notification_reads",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_user_notification_reads_user_id"), table_name="user_notification_reads"
    )
    op.drop_index(
        op.f("ix_user_notification_reads_notification_id"),
        table_name="user_notification_reads",
    )
    op.drop_table("user_notification_reads")

    op.drop_index(
        op.f("ix_notification_audience_notification_id"),
        table_name="notification_audience",
    )
    op.drop_index(
        op.f("ix_notification_audience_id"), table_name="notification_audience"
    )
    op.drop_table("notification_audience")

    op.drop_index(op.f("ix_notifications_id"), table_name="notifications")
    op.drop_table("notifications")
