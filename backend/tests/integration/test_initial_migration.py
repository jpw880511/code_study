import uuid
from collections.abc import Iterator
from typing import cast

import pytest
from alembic import command
from sqlalchemy import Connection, Engine, create_engine, exc, inspect, text
from tests.conftest import alembic_config

EXPECTED_TABLES = {
    "users",
    "projects",
    "tasks",
    "uploaded_code",
    "code_files",
    "learning_documents",
    "practice_problems",
    "questions",
    "progress",
    "refresh_tokens",
}

EXPECTED_INDEXES = {
    "users": {"idx_users_email"},
    "projects": {
        "idx_projects_user_id",
        "idx_projects_deletion_status",
        "idx_projects_user_active",
    },
    "tasks": {
        "idx_tasks_project_id",
        "idx_tasks_deletion_status",
        "idx_tasks_project_active",
        "idx_tasks_number_order",
    },
    "uploaded_code": {"idx_uploaded_code_task_id"},
    "code_files": {"idx_code_files_uploaded_code_id"},
    "learning_documents": {
        "idx_learning_documents_task_id",
        "idx_learning_documents_status",
        "idx_learning_documents_celery_task",
    },
    "practice_problems": {"idx_practice_problems_task_id", "idx_practice_problems_number"},
    "questions": {"idx_questions_task_id", "idx_questions_user_id", "idx_questions_task_user"},
    "progress": {"idx_progress_task_id", "idx_progress_user_id", "idx_progress_task_user"},
    "refresh_tokens": {
        "idx_refresh_tokens_user_id",
        "idx_refresh_tokens_hash",
        "idx_refresh_tokens_expires",
    },
}

ALL_CHAPTERS = ", ".join(f'"chapter{i}": {{}}' for i in range(1, 8))


@pytest.fixture
def conn(migrated_engine: Engine) -> Iterator[Connection]:
    """Each test runs in a transaction that is rolled back afterwards."""
    connection = migrated_engine.connect()
    transaction = connection.begin()
    yield connection
    transaction.rollback()
    connection.close()


def _insert_user(conn: Connection, email: str = "a@example.com") -> uuid.UUID:
    return cast(
        uuid.UUID,
        conn.execute(
            text("INSERT INTO users (email, password_hash) VALUES (:e, 'h') RETURNING id"),
            {"e": email},
        ).scalar_one(),
    )


def _insert_project(conn: Connection, user_id: uuid.UUID) -> uuid.UUID:
    return cast(
        uuid.UUID,
        conn.execute(
            text("INSERT INTO projects (user_id, title) VALUES (:u, 'p') RETURNING id"),
            {"u": user_id},
        ).scalar_one(),
    )


def _insert_task(conn: Connection, project_id: uuid.UUID, number: int = 1) -> uuid.UUID:
    return cast(
        uuid.UUID,
        conn.execute(
            text(
                "INSERT INTO tasks (project_id, task_number, title) "
                "VALUES (:p, :n, 'valid title') RETURNING id"
            ),
            {"p": project_id, "n": number},
        ).scalar_one(),
    )


def _task_for_new_user(conn: Connection) -> uuid.UUID:
    return _insert_task(conn, _insert_project(conn, _insert_user(conn)))


def test_all_tables_created(migrated_engine: Engine) -> None:
    assert EXPECTED_TABLES <= set(inspect(migrated_engine).get_table_names())


def test_all_indexes_created(migrated_engine: Engine) -> None:
    inspector = inspect(migrated_engine)
    for table, expected in EXPECTED_INDEXES.items():
        actual = {index["name"] for index in inspector.get_indexes(table)}
        assert expected <= actual, f"{table}: missing {expected - actual}"


def test_user_defaults(conn: Connection) -> None:
    row = conn.execute(
        text(
            "INSERT INTO users (email, password_hash) VALUES ('d@example.com', 'h') "
            "RETURNING id, skill_level, created_at, updated_at"
        )
    ).one()
    assert row.id is not None
    assert row.skill_level == "Complete Beginner"
    assert row.created_at is not None
    assert row.updated_at is not None


@pytest.mark.parametrize("email", ["not-an-email", "a@b", "@example.com"])
def test_user_rejects_invalid_email(conn: Connection, email: str) -> None:
    with pytest.raises(exc.IntegrityError):
        _insert_user(conn, email)


def test_user_email_unique(conn: Connection) -> None:
    _insert_user(conn)
    with pytest.raises(exc.IntegrityError):
        _insert_user(conn)


def test_project_title_required_and_status_checked(conn: Connection) -> None:
    user_id = _insert_user(conn)
    with pytest.raises(exc.IntegrityError), conn.begin_nested():
        conn.execute(text("INSERT INTO projects (user_id, title) VALUES (:u, '')"), {"u": user_id})
    with pytest.raises(exc.IntegrityError), conn.begin_nested():
        conn.execute(
            text("INSERT INTO projects (user_id, title, deletion_status) VALUES (:u, 't', 'gone')"),
            {"u": user_id},
        )


def test_task_constraints(conn: Connection) -> None:
    project_id = _insert_project(conn, _insert_user(conn))
    _insert_task(conn, project_id, 1)
    with pytest.raises(exc.IntegrityError), conn.begin_nested():  # duplicate task_number
        _insert_task(conn, project_id, 1)
    with pytest.raises(exc.IntegrityError), conn.begin_nested():  # title shorter than 5
        conn.execute(
            text("INSERT INTO tasks (project_id, task_number, title) VALUES (:p, 2, 'abcd')"),
            {"p": project_id},
        )
    with pytest.raises(exc.IntegrityError), conn.begin_nested():  # description over 500
        conn.execute(
            text(
                "INSERT INTO tasks (project_id, task_number, title, description) "
                "VALUES (:p, 3, 'valid title', :d)"
            ),
            {"p": project_id, "d": "x" * 501},
        )


def test_code_file_rejects_unsupported_extension(conn: Connection) -> None:
    task_id = _task_for_new_user(conn)
    code_id = conn.execute(
        text("INSERT INTO uploaded_code (task_id) VALUES (:t) RETURNING id"), {"t": task_id}
    ).scalar_one()
    insert = text(
        "INSERT INTO code_files (uploaded_code_id, file_name, storage_path, file_extension) "
        "VALUES (:c, 'f', 's', :ext)"
    )
    conn.execute(insert, {"c": code_id, "ext": ".py"})
    with pytest.raises(exc.IntegrityError), conn.begin_nested():
        conn.execute(insert, {"c": code_id, "ext": ".exe"})


def test_uploaded_code_size_limit(conn: Connection) -> None:
    task_id = _task_for_new_user(conn)
    with pytest.raises(exc.IntegrityError):
        conn.execute(
            text("INSERT INTO uploaded_code (task_id, upload_size_bytes) VALUES (:t, 10485761)"),
            {"t": task_id},
        )


def test_learning_document_requires_seven_chapters(conn: Connection) -> None:
    task_id = _task_for_new_user(conn)
    insert = text(
        "INSERT INTO learning_documents (task_id, content) VALUES (:t, CAST(:c AS jsonb)) "
        "RETURNING generation_status"
    )
    with pytest.raises(exc.IntegrityError), conn.begin_nested():
        conn.execute(insert, {"t": task_id, "c": '{"chapter1": {}}'})
    status = conn.execute(insert, {"t": task_id, "c": "{" + ALL_CHAPTERS + "}"}).scalar_one()
    assert status == "pending"


def test_practice_problem_constraints(conn: Connection) -> None:
    task_id = _task_for_new_user(conn)
    insert = text(
        "INSERT INTO practice_problems (task_id, problem_number, problem_type, problem_statement) "
        "VALUES (:t, :n, :ty, 's')"
    )
    conn.execute(insert, {"t": task_id, "n": 1, "ty": "debug"})
    for params in (
        {"t": task_id, "n": 6, "ty": "debug"},
        {"t": task_id, "n": 2, "ty": "quiz"},
        {"t": task_id, "n": 1, "ty": "debug"},
    ):
        with pytest.raises(exc.IntegrityError), conn.begin_nested():
            conn.execute(insert, params)


def test_question_length_limits(conn: Connection) -> None:
    user_id = _insert_user(conn)
    task_id = _insert_task(conn, _insert_project(conn, user_id))
    insert = text("INSERT INTO questions (task_id, user_id, question_text) VALUES (:t, :u, :q)")
    conn.execute(insert, {"t": task_id, "u": user_id, "q": "why?"})
    for question in ("hi", "x" * 501):
        with pytest.raises(exc.IntegrityError), conn.begin_nested():
            conn.execute(insert, {"t": task_id, "u": user_id, "q": question})


def test_progress_defaults_and_constraints(conn: Connection) -> None:
    user_id = _insert_user(conn)
    task_id = _insert_task(conn, _insert_project(conn, user_id))
    row = conn.execute(
        text(
            "INSERT INTO progress (task_id, user_id) VALUES (:t, :u) "
            "RETURNING chapters_completed, problems_completed, task_completed"
        ),
        {"t": task_id, "u": user_id},
    ).one()
    assert row.chapters_completed == []
    assert row.problems_completed == []
    assert row.task_completed is False
    with pytest.raises(exc.IntegrityError), conn.begin_nested():
        conn.execute(
            text("UPDATE progress SET document_read_percentage = 101 WHERE task_id = :t"),
            {"t": task_id},
        )


def test_refresh_token_hash_unique_and_default(conn: Connection) -> None:
    user_id = _insert_user(conn)
    insert = text(
        "INSERT INTO refresh_tokens (user_id, token_hash, expires_at) "
        "VALUES (:u, 'hash', now() + interval '7 days') RETURNING revoked"
    )
    assert conn.execute(insert, {"u": user_id}).scalar_one() is False
    with pytest.raises(exc.IntegrityError), conn.begin_nested():
        conn.execute(insert, {"u": user_id})


def test_deleting_user_cascades_everywhere(conn: Connection) -> None:
    user_id = _insert_user(conn)
    task_id = _insert_task(conn, _insert_project(conn, user_id))
    conn.execute(
        text("INSERT INTO progress (task_id, user_id) VALUES (:t, :u)"),
        {"t": task_id, "u": user_id},
    )
    conn.execute(text("DELETE FROM users WHERE id = :u"), {"u": user_id})
    for table in ("projects", "tasks", "progress"):
        assert conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() == 0


def test_downgrade_removes_all_tables(test_database_url: str, migrated_engine: Engine) -> None:
    migrated_engine.dispose()
    config = alembic_config(test_database_url)
    command.downgrade(config, "base")
    engine = create_engine(test_database_url)
    try:
        assert not (EXPECTED_TABLES & set(inspect(engine).get_table_names()))
    finally:
        engine.dispose()
        command.upgrade(config, "head")
