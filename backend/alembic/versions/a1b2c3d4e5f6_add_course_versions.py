"""add_course_versions

Revision ID: a1b2c3d4e5f6
Revises: 600e34347c56
Create Date: 2026-03-16 14:41:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "600e34347c56"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema for course versioning.

    DB state when this runs:
      - course_versions already exists (id, course_id, version, title, subtitle, description, published, created_at)
      - courses still has: title, description, course_image, estimated_duration (need to drop after migration)
      - modules: has course_id but NO course_version_id yet
    """

    # 1. Create course_versions table
    op.create_table(
        "course_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("subtitle", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("published", sa.Boolean(), default=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True
        ),
        sa.Column("course_image", sa.String(), nullable=True),
        sa.Column("estimated_duration", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # 2. Migrate existing course data into course_versions (if course_versions is empty, seed from courses)
    op.execute("""
        INSERT INTO course_versions (course_id, version, title, course_image, description, estimated_duration, published, created_at)
        SELECT c.id, 1,
               COALESCE(c.title, 'Untitled'),
               c.course_image,
               c.description,
               c.estimated_duration,
               c.published,
               c.created_at
        FROM courses c
        WHERE NOT EXISTS (
            SELECT 1 FROM course_versions cv WHERE cv.course_id = c.id
        )
    """)

    # 3. Add course_version_id FK column to modules
    op.add_column(
        "modules", sa.Column("course_version_id", sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        "fk_modules_course_version_id",
        "modules",
        "course_versions",
        ["course_version_id"],
        ["id"],
    )

    # 4. Populate course_version_id on existing modules using their course_id -> version 1
    op.execute("""
        UPDATE modules m
        SET course_version_id = cv.id
        FROM course_versions cv
        WHERE cv.course_id = m.course_id
          AND cv.version = 1
    """)

    # 5. Drop old columns from courses (now live in course_versions)
    op.drop_column("courses", "title")
    op.drop_column("courses", "description")
    op.drop_column("courses", "course_image")
    op.drop_column("courses", "estimated_duration")


def downgrade() -> None:
    """Downgrade schema - reverse course versioning."""

    # Re-add columns to courses
    op.add_column("courses", sa.Column("title", sa.String(), nullable=True))
    op.add_column("courses", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("courses", sa.Column("course_image", sa.String(), nullable=True))
    op.add_column(
        "courses", sa.Column("estimated_duration", sa.Integer(), nullable=True)
    )

    # Restore course data from version 1
    op.execute("""
        UPDATE courses c
        SET title = cv.title,
            description = cv.description,
            course_image = cv.course_image,
            estimated_duration = cv.estimated_duration
        FROM course_versions cv
        WHERE cv.course_id = c.id AND cv.version = 1
    """)

    # Drop course_version_id from modules
    op.drop_constraint("fk_modules_course_version_id", "modules", type_="foreignkey")
    op.drop_column("modules", "course_version_id")

    # Drop course_versions table entirely
    op.drop_table("course_versions")
