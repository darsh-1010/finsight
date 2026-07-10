"""added mcq question options table

Revision ID: aeb96aba880b
Revises: 072fb12742fe
Create Date: 2026-01-24 21:26:32.276704
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "aeb96aba880b"
down_revision: str | Sequence[str] | None = "072fb12742fe"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ---- INLINE FIX: CREATE ENUM TYPE FIRST ----
    question_type_enum = sa.Enum(
        "TEXT",
        "NUMBER",
        "EMAIL",
        "PHONE",
        "DATE",
        "SINGLE_CHOICE",
        "MULTI_CHOICE",
        "DROPDOWN",
        "FILE",
        name="question_type_enum",
    )
    question_type_enum.create(op.get_bind(), checkfirst=True)

    # ---- INLINE FIX: CLEAN BAD DATA BEFORE CAST ----
    op.execute("""
        UPDATE onboarding_questions
        SET question_type = 'TEXT'
        WHERE question_type IS NULL
           OR LOWER(question_type) IN ('tes', 'text', 'string', 'str');
    """)

    # ### auto-generated + adjusted ###
    op.create_table(
        "onboarding_question_options",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("value", sa.String(), nullable=False),
        sa.Column("order", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["question_id"], ["onboarding_questions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_onboarding_question_options_id"),
        "onboarding_question_options",
        ["id"],
        unique=False,
    )

    op.add_column(
        "onboarding_questions",
        sa.Column("question_description", sa.String(), nullable=True),
    )
    op.add_column(
        "onboarding_questions", sa.Column("title", sa.String(), nullable=True)
    )
    op.add_column(
        "onboarding_questions",
        sa.Column("depends_on_question_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "onboarding_questions",
        sa.Column("depends_on_value", sa.String(), nullable=True),
    )
    op.add_column(
        "onboarding_questions", sa.Column("updated_at", sa.DateTime(), nullable=True)
    )

    op.alter_column(
        "onboarding_questions",
        "question_text",
        existing_type=sa.TEXT(),
        type_=sa.String(),
        existing_nullable=False,
    )

    # ---- INLINE FIX: SAFE CAST VARCHAR -> ENUM ----
    op.execute(
        "ALTER TABLE onboarding_questions "
        "ALTER COLUMN question_type TYPE question_type_enum "
        "USING question_type::question_type_enum"
    )

    # ---- INLINE FIX: SAFE CAST VARCHAR -> JSONB ----
    # ---- INLINE FIX: SANITIZE INVALID JSON THEN CAST TO JSONB ----

    # 1. If value is plain words like 'string', 'number', etc → replace with empty object
    op.execute("""
    UPDATE onboarding_questions
    SET validation_rules = '{}'
    WHERE validation_rules IS NULL
    OR validation_rules ~ '^[A-Za-z_]+$';
    """)

    # 2. If value looks like JSON but stored as text, keep it
    # (Postgres will cast valid JSON strings correctly)

    # 3. Now safely cast
    op.execute("""
    ALTER TABLE onboarding_questions
    ALTER COLUMN validation_rules TYPE JSONB
    USING validation_rules::jsonb
    """)

    op.create_foreign_key(
        None,
        "onboarding_questions",
        "onboarding_questions",
        ["depends_on_question_id"],
        ["id"],
    )

    op.add_column(
        "user_onboarding_answers",
        sa.Column(
            "answer_value", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
    )
    op.add_column(
        "user_onboarding_answers",
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.drop_column("user_onboarding_answers", "answer_text")


def downgrade() -> None:
    op.add_column(
        "user_onboarding_answers", sa.Column("answer_text", sa.TEXT(), nullable=False)
    )
    op.drop_column("user_onboarding_answers", "updated_at")
    op.drop_column("user_onboarding_answers", "answer_value")

    op.drop_constraint(
        "onboarding_questions_depends_on_question_id_fkey",
        "onboarding_questions",
        type_="foreignkey",
    )

    op.alter_column(
        "onboarding_questions",
        "validation_rules",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        type_=sa.VARCHAR(),
        existing_nullable=True,
    )

    op.alter_column(
        "onboarding_questions",
        "question_type",
        existing_type=sa.Enum(name="question_type_enum"),
        type_=sa.VARCHAR(),
        nullable=True,
    )

    op.alter_column(
        "onboarding_questions",
        "question_text",
        existing_type=sa.String(),
        type_=sa.TEXT(),
        existing_nullable=False,
    )

    op.drop_column("onboarding_questions", "updated_at")
    op.drop_column("onboarding_questions", "depends_on_value")
    op.drop_column("onboarding_questions", "depends_on_question_id")
    op.drop_column("onboarding_questions", "title")
    op.drop_column("onboarding_questions", "question_description")

    op.drop_index(
        op.f("ix_onboarding_question_options_id"),
        table_name="onboarding_question_options",
    )
    op.drop_table("onboarding_question_options")

    question_type_enum = sa.Enum(name="question_type_enum")
    question_type_enum.drop(op.get_bind(), checkfirst=True)
