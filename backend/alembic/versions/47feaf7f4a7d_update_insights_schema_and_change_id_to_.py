"""update_insights_schema_and_change_id_to_uuid

Revision ID: 47feaf7f4a7d
Revises: dbbda685fdbb
Create Date: 2026-06-01 16:55:00.204952

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '47feaf7f4a7d'
down_revision: Union[str, Sequence[str], None] = 'dbbda685fdbb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Enable pgcrypto for gen_random_uuid()
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    # 2. Drop existing index and primary key on insights
    op.drop_index('ix_insights_id', table_name='insights')
    op.execute('ALTER TABLE insights DROP CONSTRAINT IF EXISTS insights_pkey CASCADE')

    # 3. Drop columns to be removed / modified
    op.drop_column('insights', 'id')
    op.drop_column('insights', 'title')
    op.drop_column('insights', 'approved')
    op.drop_column('insights', 'approved_at')

    # 4. Create Postgres Enum Types if they don't exist
    trend_type_enum = sa.Enum("daily", "weekly", name="trendtype")
    trend_type_enum.create(op.get_bind(), checkfirst=True)

    insight_status_enum = sa.Enum("draft", "approved", "published", "archived", name="insightstatus")
    insight_status_enum.create(op.get_bind(), checkfirst=True)

    # 5. Add new columns including the UUID id column
    op.add_column('insights', sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')))
    op.add_column('insights', sa.Column('ticker', sa.String(), nullable=True))
    op.add_column('insights', sa.Column('trend_type', trend_type_enum, nullable=True))
    op.add_column('insights', sa.Column('trend', sa.String(), nullable=True))
    op.add_column('insights', sa.Column('price_change_pct', sa.Float(), nullable=True))
    op.add_column('insights', sa.Column('key_event', sa.Text(), nullable=True))
    op.add_column('insights', sa.Column('verification_status', sa.String(), nullable=True))
    op.add_column('insights', sa.Column('citations', sa.ARRAY(sa.String()), nullable=True))
    op.add_column('insights', sa.Column('alert_message', sa.Text(), nullable=True))
    op.add_column('insights', sa.Column('status', insight_status_enum, nullable=False, server_default='draft'))
    op.add_column('insights', sa.Column('expires_at', sa.DateTime(), nullable=True))

    # 6. Restore primary key constraint and index
    op.create_primary_key('insights_pkey', 'insights', ['id'])
    op.create_index(op.f('ix_insights_id'), 'insights', ['id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # 1. Drop index and primary key on insights
    op.drop_index('ix_insights_id', table_name='insights')
    op.execute('ALTER TABLE insights DROP CONSTRAINT IF EXISTS insights_pkey CASCADE')

    # 2. Drop new columns
    op.drop_column('insights', 'id')
    op.drop_column('insights', 'ticker')
    op.drop_column('insights', 'trend_type')
    op.drop_column('insights', 'trend')
    op.drop_column('insights', 'price_change_pct')
    op.drop_column('insights', 'key_event')
    op.drop_column('insights', 'verification_status')
    op.drop_column('insights', 'citations')
    op.drop_column('insights', 'alert_message')
    op.drop_column('insights', 'status')
    op.drop_column('insights', 'expires_at')

    # 3. Add back the old columns
    op.add_column('insights', sa.Column('id', sa.Integer(), sa.Identity(always=False, start=1, increment=1), nullable=False))
    op.add_column('insights', sa.Column('title', sa.String(), nullable=False, server_default='Untitled'))
    op.add_column('insights', sa.Column('approved', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('insights', sa.Column('approved_at', sa.DateTime(), nullable=True))

    # Remove server default from title/approved to restore original definition
    op.alter_column('insights', 'title', server_default=None)
    op.alter_column('insights', 'approved', server_default=None)

    # 4. Drop Postgres Enum Types
    op.execute('DROP TYPE IF EXISTS trendtype CASCADE')
    op.execute('DROP TYPE IF EXISTS insightstatus CASCADE')

    # 5. Restore primary key and index
    op.create_primary_key('insights_pkey', 'insights', ['id'])
    op.create_index(op.f('ix_insights_id'), 'insights', ['id'], unique=False)
