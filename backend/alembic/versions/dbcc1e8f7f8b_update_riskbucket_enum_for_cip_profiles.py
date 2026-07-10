"""Update RiskBucket enum for CIP profiles

Revision ID: dbcc1e8f7f8b
Revises: c8d508f52d22
"""

from collections.abc import Sequence

from alembic import op

revision: str = "dbcc1e8f7f8b"
down_revision: str | Sequence[str] | None = "c8d508f52d22"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- ENUM changes must be autocommitted in Postgres ---
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE riskbucket ADD VALUE IF NOT EXISTS 'risk_averse'")
        op.execute("ALTER TYPE riskbucket ADD VALUE IF NOT EXISTS 'moderate'")
        op.execute(
            "ALTER TYPE riskbucket ADD VALUE IF NOT EXISTS 'moderately_aggressive'"
        )
        op.execute("ALTER TYPE riskbucket ADD VALUE IF NOT EXISTS 'very_aggressive'")

    # --- Now we can safely use new enum values ---
    op.execute("""
        UPDATE user_profiles
        SET risk_bucket = 'moderate'
        WHERE risk_bucket = 'balanced';
    """)


def downgrade() -> None:

    # 1. Map new values back to old enum-compatible values
    op.execute("""
        UPDATE user_profiles
        SET risk_bucket = CASE
            WHEN risk_bucket = 'risk_averse' THEN 'conservative'
            WHEN risk_bucket = 'moderate' THEN 'balanced'
            WHEN risk_bucket = 'moderately_aggressive' THEN 'aggressive'
            WHEN risk_bucket = 'very_aggressive' THEN 'aggressive'
            ELSE risk_bucket
        END;
    """)

    # 2. Recreate old enum
    with op.get_context().autocommit_block():
        op.execute("DROP TYPE IF EXISTS riskbucket_old;")

        op.execute("""
            CREATE TYPE riskbucket_old AS ENUM (
                'no_risk',
                'conservative',
                'balanced',
                'aggressive'
            );
        """)

    # 3. Cast column to old enum
    op.execute("""
        ALTER TABLE user_profiles
        ALTER COLUMN risk_bucket
        TYPE riskbucket_old
        USING risk_bucket::text::riskbucket_old;
    """)

    # 4. Swap enum types
    with op.get_context().autocommit_block():
        op.execute("DROP TYPE riskbucket;")
        op.execute("ALTER TYPE riskbucket_old RENAME TO riskbucket;")
