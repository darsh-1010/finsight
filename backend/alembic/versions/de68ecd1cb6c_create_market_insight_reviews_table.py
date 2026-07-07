"""create_market_insight_reviews_table

Revision ID: de68ecd1cb6c
Revises: 47feaf7f4a7d
Create Date: 2026-06-01 17:01:48.041093

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'de68ecd1cb6c'
down_revision: Union[str, Sequence[str], None] = '47feaf7f4a7d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'market_insight_reviews',
        sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('market_insight_id', sa.UUID(), nullable=False),
        sa.Column('reviewer_id', sa.Integer(), nullable=False),
        sa.Column('review_status', sa.String(), nullable=False),
        sa.Column('review_notes', sa.Text(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['market_insight_id'], ['insights.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reviewer_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_market_insight_reviews_id'), 'market_insight_reviews', ['id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_market_insight_reviews_id'), table_name='market_insight_reviews')
    op.drop_table('market_insight_reviews')
