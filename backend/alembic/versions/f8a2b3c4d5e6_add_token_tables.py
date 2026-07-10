"""add token wallet and usage tables

Revision ID: f8a2b3c4d5e6
Revises: 5fb6880bb556
Create Date: 2026-05-19 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f8a2b3c4d5e6"
down_revision: str | Sequence[str] | None = "5fb6880bb556"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "tier_token_configs" in tables:
        return

    op.create_table(
        "tier_token_configs",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("tier_id", sa.Integer(), nullable=False),
        sa.Column("weekly_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "daily_token_limit", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("monthly_token_limit", sa.Integer(), nullable=True),
        sa.Column(
            "refill_frequency",
            sa.String(length=20),
            nullable=False,
            server_default="weekly",
        ),
        sa.Column(
            "max_tokens_per_prompt", sa.Integer(), nullable=False, server_default="1"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tier_id"], ["tiers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tier_id"),
    )
    op.create_index(
        op.f("ix_tier_token_configs_id"),
        "tier_token_configs",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tier_token_configs_tier_id"),
        "tier_token_configs",
        ["tier_id"],
        unique=True,
    )

    op.create_table(
        "user_token_wallets",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("available_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "total_used_tokens", sa.BigInteger(), nullable=False, server_default="0"
        ),
        sa.Column("last_refill_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_refill_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(
        op.f("ix_user_token_wallets_id"),
        "user_token_wallets",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_token_wallets_user_id"),
        "user_token_wallets",
        ["user_id"],
        unique=True,
    )

    op.create_table(
        "daily_token_usage",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column("tokens_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "usage_date", name="uq_daily_token_usage_user_date"
        ),
    )
    op.create_index(
        op.f("ix_daily_token_usage_id"),
        "daily_token_usage",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_daily_token_usage_user_id"),
        "daily_token_usage",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_daily_token_usage_usage_date"),
        "daily_token_usage",
        ["usage_date"],
        unique=False,
    )

    op.create_table(
        "token_transactions",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("transaction_type", sa.String(length=50), nullable=False),
        sa.Column("tokens", sa.Integer(), nullable=False),
        sa.Column("balance_before", sa.Integer(), nullable=False),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("reference_type", sa.String(length=50), nullable=True),
        sa.Column("reference_id", sa.BigInteger(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_token_transactions_id"),
        "token_transactions",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_token_transactions_user_id"),
        "token_transactions",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_token_transactions_transaction_type"),
        "token_transactions",
        ["transaction_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_token_transactions_transaction_type"),
        table_name="token_transactions",
    )
    op.drop_index(
        op.f("ix_token_transactions_user_id"), table_name="token_transactions"
    )
    op.drop_index(op.f("ix_token_transactions_id"), table_name="token_transactions")
    op.drop_table("token_transactions")

    op.drop_index(
        op.f("ix_daily_token_usage_usage_date"), table_name="daily_token_usage"
    )
    op.drop_index(op.f("ix_daily_token_usage_user_id"), table_name="daily_token_usage")
    op.drop_index(op.f("ix_daily_token_usage_id"), table_name="daily_token_usage")
    op.drop_table("daily_token_usage")

    op.drop_index(
        op.f("ix_user_token_wallets_user_id"), table_name="user_token_wallets"
    )
    op.drop_index(op.f("ix_user_token_wallets_id"), table_name="user_token_wallets")
    op.drop_table("user_token_wallets")

    op.drop_index(
        op.f("ix_tier_token_configs_tier_id"), table_name="tier_token_configs"
    )
    op.drop_index(op.f("ix_tier_token_configs_id"), table_name="tier_token_configs")
    op.drop_table("tier_token_configs")
