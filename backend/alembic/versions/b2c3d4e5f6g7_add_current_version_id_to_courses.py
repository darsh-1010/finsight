"""add_current_version_id_to_courses

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-16 15:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6g7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add current_version_id column
    op.add_column('courses', sa.Column('current_version_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_courses_current_version_id',
        'courses', 'course_versions',
        ['current_version_id'], ['id']
    )

    # 2. Populate current_version_id for existing courses (use the latest version)
    op.execute("""
        UPDATE courses c
        SET current_version_id = cv.id
        FROM (
            SELECT DISTINCT ON (course_id) id, course_id
            FROM course_versions
            ORDER BY course_id, version DESC
        ) cv
        WHERE c.id = cv.course_id
    """)


def downgrade() -> None:
    op.drop_constraint('fk_courses_current_version_id', 'courses', type_='foreignkey')
    op.drop_column('courses', 'current_version_id')
