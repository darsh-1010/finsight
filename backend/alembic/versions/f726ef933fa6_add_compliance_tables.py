"""Add compliance tables

Revision ID: f726ef933fa6
Revises: 57c7a26720e3
Create Date: 2026-01-21 11:07:51.188299
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'f726ef933fa6'
down_revision: Union[str, Sequence[str], None] = '57c7a26720e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    disclosure_type_enum = postgresql.ENUM(
        'risk', 'info', 'warning', 'success',
        name='disclosuretype'
    )
    disclosure_type_enum.create(op.get_bind(), checkfirst=True)

    # Create compliance_groups table
    op.create_table(
        'compliance_groups',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('key', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_compliance_groups_id'), 'compliance_groups', ['id'], unique=False)
    op.create_index(op.f('ix_compliance_groups_key'), 'compliance_groups', ['key'], unique=True)

    # Create compliance_disclosures table (reuse enum, DO NOT create)
    op.create_table(
        'compliance_disclosures',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('group_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column(
            'disclosure_type',
            postgresql.ENUM(
                'risk', 'info', 'warning', 'success',
                name='disclosuretype',
                create_type=False
            ),
            nullable=False
        ),
        sa.Column('icon_name', sa.String(), nullable=False),
        sa.Column('color', sa.String(), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['group_id'], ['compliance_groups.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_compliance_disclosures_id'), 'compliance_disclosures', ['id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop compliance_disclosures table
    op.drop_index(op.f('ix_compliance_disclosures_id'), table_name='compliance_disclosures', if_exists=True)
    op.drop_table('compliance_disclosures', if_exists=True)

    # Drop compliance_groups table
    op.drop_index(op.f('ix_compliance_groups_key'), table_name='compliance_groups', if_exists=True)
    op.drop_index(op.f('ix_compliance_groups_id'), table_name='compliance_groups', if_exists=True)
    op.drop_table('compliance_groups', if_exists=True)

    # Drop disclosure_type enum
    disclosure_type_enum = postgresql.ENUM(
        'risk', 'info', 'warning', 'success',
        name='disclosuretype'
    )
    disclosure_type_enum.drop(op.get_bind(), checkfirst=True)