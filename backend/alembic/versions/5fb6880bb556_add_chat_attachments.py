"""add chat attachments

Revision ID: 5fb6880bb556
Revises: 2e39d12f2d43
Create Date: 2026-05-06 16:08:16.453881

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5fb6880bb556'
down_revision: Union[str, Sequence[str], None] = '2e39d12f2d43'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if 'attachments' not in tables:
        op.create_table('attachments',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('file_name', sa.String(length=255), nullable=False),
            sa.Column('file_type', sa.String(length=50), nullable=True),
            sa.Column('file_size', sa.BigInteger(), nullable=True),
            sa.Column('storage_url', sa.Text(), nullable=True),
            sa.Column('storage_provider', sa.String(length=50), nullable=True),
            sa.Column('checksum', sa.String(length=255), nullable=True),
            sa.Column('status', sa.String(length=50), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
    
    if 'message_attachments' not in tables:
        op.create_table('message_attachments',
            sa.Column('id', sa.BigInteger(), nullable=False),
            sa.Column('message_id', sa.Integer(), nullable=False),
            sa.Column('attachment_id', sa.UUID(), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
            sa.ForeignKeyConstraint(['attachment_id'], ['attachments.id'], ),
            sa.ForeignKeyConstraint(['message_id'], ['chat_messages.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_message_attachments_id'), 'message_attachments', ['id'], unique=False)
    
    # Check if column has_attachments exists in chat_messages
    columns = [c['name'] for c in inspector.get_columns('chat_messages')]
    if 'has_attachments' not in columns:
        op.add_column('chat_messages', sa.Column('has_attachments', sa.Boolean(), server_default='false', nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    # Note: Downgrade will attempt to drop everything. Use with caution.
    op.drop_column('chat_messages', 'has_attachments')
    op.drop_index(op.f('ix_message_attachments_id'), table_name='message_attachments')
    op.drop_table('message_attachments')
    op.drop_table('attachments')
