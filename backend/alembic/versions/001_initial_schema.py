"""Initial schema (hand-written SQL, mirrors specs/001-ai-code-learning-platform/data-model.md).

Revision ID: 001
Revises:
"""

from collections.abc import Sequence

from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES_IN_DROP_ORDER = (
    "refresh_tokens",
    "progress",
    "questions",
    "practice_problems",
    "learning_documents",
    "code_files",
    "uploaded_code",
    "tasks",
    "projects",
    "users",
)

STATEMENTS = (
    r"""
    CREATE TABLE users (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        email VARCHAR(255) UNIQUE NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        skill_level VARCHAR(50) DEFAULT 'Complete Beginner',
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        last_login_at TIMESTAMP WITH TIME ZONE,
        CONSTRAINT valid_email CHECK (
            email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$'
        )
    )
    """,
    "CREATE INDEX idx_users_email ON users(email)",
    """
    CREATE TABLE projects (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        title VARCHAR(255) NOT NULL,
        description TEXT,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        last_activity_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        deletion_status VARCHAR(20) DEFAULT 'active'
            CHECK (deletion_status IN ('active', 'trashed')),
        trashed_at TIMESTAMP WITH TIME ZONE,
        scheduled_deletion_at TIMESTAMP WITH TIME ZONE,
        CONSTRAINT title_min_length CHECK (char_length(title) >= 1)
    )
    """,
    "CREATE INDEX idx_projects_user_id ON projects(user_id)",
    "CREATE INDEX idx_projects_deletion_status ON projects(deletion_status)",
    """
    CREATE INDEX idx_projects_user_active ON projects(user_id, deletion_status)
        WHERE deletion_status = 'active'
    """,
    """
    CREATE TABLE tasks (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        task_number INTEGER NOT NULL,
        title VARCHAR(255) NOT NULL,
        description TEXT,
        upload_method VARCHAR(20) CHECK (upload_method IN ('file', 'folder', 'paste')),
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        deletion_status VARCHAR(20) DEFAULT 'active'
            CHECK (deletion_status IN ('active', 'trashed')),
        trashed_at TIMESTAMP WITH TIME ZONE,
        scheduled_deletion_at TIMESTAMP WITH TIME ZONE,
        CONSTRAINT title_min_length CHECK (char_length(title) >= 5),
        CONSTRAINT description_max_length CHECK (char_length(description) <= 500),
        CONSTRAINT unique_task_number_per_project UNIQUE (project_id, task_number)
    )
    """,
    "CREATE INDEX idx_tasks_project_id ON tasks(project_id)",
    "CREATE INDEX idx_tasks_deletion_status ON tasks(deletion_status)",
    """
    CREATE INDEX idx_tasks_project_active ON tasks(project_id, deletion_status)
        WHERE deletion_status = 'active'
    """,
    "CREATE INDEX idx_tasks_number_order ON tasks(project_id, task_number)",
    """
    CREATE TABLE uploaded_code (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        task_id UUID UNIQUE NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
        detected_language VARCHAR(50),
        complexity_level VARCHAR(20)
            CHECK (complexity_level IN ('beginner', 'intermediate', 'advanced')),
        total_lines INTEGER,
        total_files INTEGER,
        upload_size_bytes INTEGER,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT valid_upload_size CHECK (upload_size_bytes <= 10485760)
    )
    """,
    "CREATE INDEX idx_uploaded_code_task_id ON uploaded_code(task_id)",
    """
    CREATE TABLE code_files (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        uploaded_code_id UUID NOT NULL REFERENCES uploaded_code(id) ON DELETE CASCADE,
        file_name VARCHAR(255) NOT NULL,
        file_path TEXT,
        file_extension VARCHAR(20),
        file_size_bytes INTEGER,
        storage_path TEXT NOT NULL,
        mime_type VARCHAR(100),
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT supported_extension CHECK (
            file_extension IN (
                '.py', '.js', '.ts', '.jsx', '.tsx', '.html', '.css',
                '.java', '.cpp', '.c', '.txt', '.md'
            )
        )
    )
    """,
    "CREATE INDEX idx_code_files_uploaded_code_id ON code_files(uploaded_code_id)",
    """
    CREATE TABLE learning_documents (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        task_id UUID UNIQUE NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
        content JSONB NOT NULL,
        generation_status VARCHAR(20) DEFAULT 'pending' CHECK (
            generation_status IN ('pending', 'in_progress', 'completed', 'failed')
        ),
        generation_started_at TIMESTAMP WITH TIME ZONE,
        generation_completed_at TIMESTAMP WITH TIME ZONE,
        generation_error TEXT,
        celery_task_id VARCHAR(255),
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT valid_content_structure CHECK (
            jsonb_typeof(content) = 'object' AND
            content ?& ARRAY[
                'chapter1', 'chapter2', 'chapter3', 'chapter4',
                'chapter5', 'chapter6', 'chapter7'
            ]
        )
    )
    """,
    "CREATE INDEX idx_learning_documents_task_id ON learning_documents(task_id)",
    "CREATE INDEX idx_learning_documents_status ON learning_documents(generation_status)",
    "CREATE INDEX idx_learning_documents_celery_task ON learning_documents(celery_task_id)",
    """
    CREATE TABLE practice_problems (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
        problem_number INTEGER NOT NULL CHECK (problem_number BETWEEN 1 AND 5),
        problem_type VARCHAR(20) NOT NULL CHECK (
            problem_type IN ('follow_along', 'fill_blanks', 'modify', 'debug', 'create')
        ),
        problem_statement TEXT NOT NULL,
        learning_objective TEXT,
        hints JSONB,
        model_solution TEXT,
        expected_output TEXT,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT unique_problem_per_task UNIQUE (task_id, problem_number)
    )
    """,
    "CREATE INDEX idx_practice_problems_task_id ON practice_problems(task_id)",
    "CREATE INDEX idx_practice_problems_number ON practice_problems(task_id, problem_number)",
    """
    CREATE TABLE questions (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        question_text TEXT NOT NULL,
        selected_code_context TEXT,
        answer_text TEXT,
        answered_at TIMESTAMP WITH TIME ZONE,
        helpful_feedback BOOLEAN,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT question_length CHECK (
            char_length(question_text) >= 3 AND char_length(question_text) <= 500
        ),
        CONSTRAINT code_context_length CHECK (
            selected_code_context IS NULL OR char_length(selected_code_context) <= 50000
        )
    )
    """,
    "CREATE INDEX idx_questions_task_id ON questions(task_id)",
    "CREATE INDEX idx_questions_user_id ON questions(user_id)",
    "CREATE INDEX idx_questions_task_user ON questions(task_id, user_id)",
    """
    CREATE TABLE progress (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        task_id UUID UNIQUE NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        chapters_completed JSONB DEFAULT '[]'::jsonb,
        document_read_percentage INTEGER DEFAULT 0
            CHECK (document_read_percentage BETWEEN 0 AND 100),
        problems_completed JSONB DEFAULT '[]'::jsonb,
        practice_completion_count INTEGER DEFAULT 0
            CHECK (practice_completion_count BETWEEN 0 AND 5),
        questions_asked_count INTEGER DEFAULT 0,
        task_completed BOOLEAN DEFAULT FALSE,
        task_completion_date TIMESTAMP WITH TIME ZONE,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT valid_chapter_completion CHECK (
            jsonb_typeof(chapters_completed) = 'array' AND
            jsonb_array_length(chapters_completed) <= 7
        ),
        CONSTRAINT valid_problem_completion CHECK (
            jsonb_typeof(problems_completed) = 'array' AND
            jsonb_array_length(problems_completed) <= 5
        )
    )
    """,
    "CREATE INDEX idx_progress_task_id ON progress(task_id)",
    "CREATE INDEX idx_progress_user_id ON progress(user_id)",
    "CREATE INDEX idx_progress_task_user ON progress(task_id, user_id)",
    """
    CREATE TABLE refresh_tokens (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        token_hash VARCHAR(255) UNIQUE NOT NULL,
        expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        revoked BOOLEAN DEFAULT FALSE,
        revoked_at TIMESTAMP WITH TIME ZONE
    )
    """,
    "CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens(user_id)",
    "CREATE INDEX idx_refresh_tokens_hash ON refresh_tokens(token_hash)",
    "CREATE INDEX idx_refresh_tokens_expires ON refresh_tokens(expires_at)",
)


def upgrade() -> None:
    for statement in STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    for table in TABLES_IN_DROP_ORDER:
        op.execute(f"DROP TABLE IF EXISTS {table}")
