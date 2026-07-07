"""Add suggested_follow_ups to ChatMessage

Revision ID: 8d84464ce929
Revises: 39dd9a9c7cb3
Create Date: 2026-06-29 09:29:45.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '8d84464ce929'
down_revision = '39dd9a9c7cb3'
branch_labels = None
depends_on = None


def upgrade():
    # Empty migration to resolve missing revision error without modifying schema
    pass


def downgrade():
    pass
