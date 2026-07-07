"""change_courses_ids_to_uuid

Revision ID: a855713e88bf
Revises: b74fcab99764
Create Date: 2026-04-22 10:56:45.512892

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a855713e88bf'
down_revision: Union[str, Sequence[str], None] = 'b74fcab99764'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Use raw SQL to handle the change correctly without losing data
    op.execute('''
        -- 1. Add uuid generation extension if not exists
        CREATE EXTENSION IF NOT EXISTS "pgcrypto";
        
        -- 2. Add columns
        ALTER TABLE courses ADD COLUMN uuid UUID;
        ALTER TABLE course_versions ADD COLUMN uuid UUID;
        ALTER TABLE modules ADD COLUMN uuid UUID;
        ALTER TABLE lessons ADD COLUMN uuid UUID;
        ALTER TABLE lesson_subtitles ADD COLUMN uuid UUID;
        ALTER TABLE lesson_progress ADD COLUMN uuid UUID;
        ALTER TABLE lesson_resources ADD COLUMN uuid UUID;

        UPDATE courses SET uuid = gen_random_uuid();
        UPDATE course_versions SET uuid = gen_random_uuid();
        UPDATE modules SET uuid = gen_random_uuid();
        UPDATE lessons SET uuid = gen_random_uuid();
        UPDATE lesson_subtitles SET uuid = gen_random_uuid();
        UPDATE lesson_progress SET uuid = gen_random_uuid();
        UPDATE lesson_resources SET uuid = gen_random_uuid();

        ALTER TABLE courses ALTER COLUMN uuid SET DEFAULT gen_random_uuid(), ALTER COLUMN uuid SET NOT NULL;
        ALTER TABLE course_versions ALTER COLUMN uuid SET DEFAULT gen_random_uuid(), ALTER COLUMN uuid SET NOT NULL;
        ALTER TABLE modules ALTER COLUMN uuid SET DEFAULT gen_random_uuid(), ALTER COLUMN uuid SET NOT NULL;
        ALTER TABLE lessons ALTER COLUMN uuid SET DEFAULT gen_random_uuid(), ALTER COLUMN uuid SET NOT NULL;
        ALTER TABLE lesson_subtitles ALTER COLUMN uuid SET DEFAULT gen_random_uuid(), ALTER COLUMN uuid SET NOT NULL;
        ALTER TABLE lesson_progress ALTER COLUMN uuid SET DEFAULT gen_random_uuid(), ALTER COLUMN uuid SET NOT NULL;
        ALTER TABLE lesson_resources ALTER COLUMN uuid SET DEFAULT gen_random_uuid(), ALTER COLUMN uuid SET NOT NULL;

        ALTER TABLE courses ADD COLUMN new_current_version_id UUID;
        ALTER TABLE course_versions ADD COLUMN new_course_id UUID;
        ALTER TABLE modules ADD COLUMN new_course_id UUID, ADD COLUMN new_course_version_id UUID;
        ALTER TABLE lessons ADD COLUMN new_module_id UUID;
        ALTER TABLE lesson_subtitles ADD COLUMN new_lesson_id UUID;
        ALTER TABLE lesson_progress ADD COLUMN new_lesson_id UUID;
        ALTER TABLE lesson_resources ADD COLUMN new_lesson_id UUID;

        -- 3. Populate foreign keys
        UPDATE courses c SET new_current_version_id = cv.uuid FROM course_versions cv WHERE c.current_version_id = cv.id;
        UPDATE course_versions cv SET new_course_id = c.uuid FROM courses c WHERE cv.course_id = c.id;
        UPDATE modules m SET new_course_id = c.uuid FROM courses c WHERE m.course_id = c.id;
        UPDATE modules m SET new_course_version_id = cv.uuid FROM course_versions cv WHERE m.course_version_id = cv.id;
        UPDATE lessons l SET new_module_id = m.uuid FROM modules m WHERE l.module_id = m.id;
        UPDATE lesson_subtitles ls SET new_lesson_id = l.uuid FROM lessons l WHERE ls.lesson_id = l.id;
        UPDATE lesson_progress lp SET new_lesson_id = l.uuid FROM lessons l WHERE lp.lesson_id = l.id;
        UPDATE lesson_resources lr SET new_lesson_id = l.uuid FROM lessons l WHERE lr.lesson_id = l.id;

        -- 4. Drop old columns and rename new columns
        ALTER TABLE courses DROP COLUMN current_version_id CASCADE;
        ALTER TABLE courses DROP COLUMN id CASCADE;
        ALTER TABLE courses RENAME COLUMN uuid TO id;
        ALTER TABLE courses RENAME COLUMN new_current_version_id TO current_version_id;

        ALTER TABLE course_versions DROP COLUMN course_id CASCADE;
        ALTER TABLE course_versions DROP COLUMN id CASCADE;
        ALTER TABLE course_versions RENAME COLUMN uuid TO id;
        ALTER TABLE course_versions RENAME COLUMN new_course_id TO course_id;

        ALTER TABLE modules DROP COLUMN course_id CASCADE;
        ALTER TABLE modules DROP COLUMN course_version_id CASCADE;
        ALTER TABLE modules DROP COLUMN id CASCADE;
        ALTER TABLE modules RENAME COLUMN uuid TO id;
        ALTER TABLE modules RENAME COLUMN new_course_id TO course_id;
        ALTER TABLE modules RENAME COLUMN new_course_version_id TO course_version_id;

        ALTER TABLE lessons DROP COLUMN module_id CASCADE;
        ALTER TABLE lessons DROP COLUMN id CASCADE;
        ALTER TABLE lessons RENAME COLUMN uuid TO id;
        ALTER TABLE lessons RENAME COLUMN new_module_id TO module_id;

        ALTER TABLE lesson_subtitles DROP COLUMN lesson_id CASCADE;
        ALTER TABLE lesson_subtitles DROP COLUMN id CASCADE;
        ALTER TABLE lesson_subtitles RENAME COLUMN uuid TO id;
        ALTER TABLE lesson_subtitles RENAME COLUMN new_lesson_id TO lesson_id;

        ALTER TABLE lesson_progress DROP COLUMN lesson_id CASCADE;
        ALTER TABLE lesson_progress DROP COLUMN id CASCADE;
        ALTER TABLE lesson_progress RENAME COLUMN uuid TO id;
        ALTER TABLE lesson_progress RENAME COLUMN new_lesson_id TO lesson_id;

        ALTER TABLE lesson_resources DROP COLUMN lesson_id CASCADE;
        ALTER TABLE lesson_resources DROP COLUMN id CASCADE;
        ALTER TABLE lesson_resources RENAME COLUMN uuid TO id;
        ALTER TABLE lesson_resources RENAME COLUMN new_lesson_id TO lesson_id;

        -- 5. Restore primary keys
        ALTER TABLE courses ADD PRIMARY KEY (id);
        ALTER TABLE course_versions ADD PRIMARY KEY (id);
        ALTER TABLE modules ADD PRIMARY KEY (id);
        ALTER TABLE lessons ADD PRIMARY KEY (id);
        ALTER TABLE lesson_subtitles ADD PRIMARY KEY (id);
        ALTER TABLE lesson_progress ADD PRIMARY KEY (id);
        ALTER TABLE lesson_resources ADD PRIMARY KEY (id);

        -- 6. Add NOT NULL constraints where applicable
        ALTER TABLE course_versions ALTER COLUMN course_id SET NOT NULL;
        ALTER TABLE lessons ALTER COLUMN module_id SET NOT NULL;
        ALTER TABLE lesson_subtitles ALTER COLUMN lesson_id SET NOT NULL;
        ALTER TABLE lesson_progress ALTER COLUMN lesson_id SET NOT NULL;
        ALTER TABLE lesson_resources ALTER COLUMN lesson_id SET NOT NULL;

        -- 7. Restore foreign keys
        ALTER TABLE courses ADD CONSTRAINT fk_courses_current_version FOREIGN KEY (current_version_id) REFERENCES course_versions(id);
        ALTER TABLE course_versions ADD CONSTRAINT fk_course_versions_course FOREIGN KEY (course_id) REFERENCES courses(id);
        ALTER TABLE modules ADD CONSTRAINT fk_modules_course FOREIGN KEY (course_id) REFERENCES courses(id);
        ALTER TABLE modules ADD CONSTRAINT fk_modules_course_version FOREIGN KEY (course_version_id) REFERENCES course_versions(id);
        ALTER TABLE lessons ADD CONSTRAINT fk_lessons_module FOREIGN KEY (module_id) REFERENCES modules(id);
        ALTER TABLE lesson_subtitles ADD CONSTRAINT fk_lesson_subtitles_lesson FOREIGN KEY (lesson_id) REFERENCES lessons(id) ON DELETE CASCADE;
        ALTER TABLE lesson_progress ADD CONSTRAINT fk_lesson_progress_lesson FOREIGN KEY (lesson_id) REFERENCES lessons(id) ON DELETE CASCADE;
        ALTER TABLE lesson_resources ADD CONSTRAINT fk_lesson_resources_lesson FOREIGN KEY (lesson_id) REFERENCES lessons(id) ON DELETE CASCADE;

        -- Create indices
        CREATE INDEX ix_courses_id ON courses (id);
        CREATE INDEX ix_modules_id ON modules (id);
        CREATE INDEX ix_lessons_id ON lessons (id);
        CREATE INDEX ix_lesson_progress_id ON lesson_progress (id);
        CREATE INDEX ix_lesson_resources_id ON lesson_resources (id);
    ''')

def downgrade() -> None:
    # Downgrading involves converting UUID to SERIAL which is complex.
    # Since UUID to ID is hard without recreating, we will just pass for now
    # or raise NotImplementedError.
    raise NotImplementedError("Downgrade from UUID to SERIAL is not supported.")
