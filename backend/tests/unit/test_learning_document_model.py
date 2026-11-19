import uuid
from typing import Any, cast

from sqlalchemy import CheckConstraint, Column, DateTime, String, Table, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import class_mapper
from sqlalchemy.schema import DefaultClause, UniqueConstraint
from src.models import Base, LearningDocument, Task
from src.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from src.models.learning_document import CHAPTER_KEYS, GENERATION_STATUSES, empty_content

TABLE = cast(Table, LearningDocument.__table__)


def column(name: str) -> Column[Any]:
    return TABLE.c[name]


def default_sql(name: str) -> str:
    server_default = column(name).server_default
    assert isinstance(server_default, DefaultClause)
    return str(server_default.arg)


def test_registered_on_the_shared_metadata() -> None:
    assert LearningDocument.__tablename__ == "learning_documents"
    assert Base.metadata.tables["learning_documents"] is TABLE
    assert issubclass(LearningDocument, UUIDPrimaryKeyMixin)
    assert issubclass(LearningDocument, TimestampMixin)


def test_columns_match_the_migration() -> None:
    assert set(TABLE.c.keys()) == {
        "id",
        "task_id",
        "content",
        "generation_status",
        "generation_started_at",
        "generation_completed_at",
        "generation_error",
        "celery_task_id",
        "created_at",
        "updated_at",
    }


def test_primary_key_is_a_database_generated_uuid() -> None:
    assert [c.name for c in TABLE.primary_key.columns] == ["id"]
    assert isinstance(column("id").type, Uuid)
    assert "gen_random_uuid()" in default_sql("id")


def test_task_id_is_a_required_foreign_key_that_cascades_on_delete() -> None:
    task_id = column("task_id")
    assert isinstance(task_id.type, Uuid)
    assert task_id.nullable is False
    (foreign_key,) = task_id.foreign_keys
    assert foreign_key.target_fullname == "tasks.id"
    assert foreign_key.ondelete == "CASCADE"


def test_a_task_has_at_most_one_document() -> None:
    uniques = {
        c.name: [col.name for col in c.columns]
        for c in TABLE.constraints
        if isinstance(c, UniqueConstraint)
    }
    assert uniques == {"learning_documents_task_id_key": ["task_id"]}


def test_content_is_a_required_jsonb_column_filled_by_the_application() -> None:
    content = column("content")
    assert isinstance(content.type, JSONB)
    assert content.nullable is False
    # The database has no default; the model supplies the empty seven chapters (see below).
    assert content.server_default is None
    assert content.default is not None


def test_generation_status_defaults_to_pending() -> None:
    status = column("generation_status")
    assert isinstance(status.type, String)
    assert status.type.length == 20
    assert default_sql("generation_status") == "pending"


def test_the_lifecycle_columns_are_optional() -> None:
    for name in (
        "generation_started_at",
        "generation_completed_at",
        "generation_error",
        "celery_task_id",
    ):
        assert column(name).nullable is True, name
        assert column(name).server_default is None, name
    assert isinstance(column("generation_error").type, Text)
    celery_task_id = column("celery_task_id")
    assert isinstance(celery_task_id.type, String)
    assert celery_task_id.type.length == 255


def test_timestamps_are_timezone_aware() -> None:
    for name in ("generation_started_at", "generation_completed_at", "created_at", "updated_at"):
        column_type = column(name).type
        assert isinstance(column_type, DateTime)
        assert column_type.timezone is True
    assert column("created_at").nullable is False
    assert column("updated_at").nullable is False


def test_the_seven_chapter_keys_and_four_statuses_are_those_of_the_specification() -> None:
    assert CHAPTER_KEYS == (
        "chapter1",
        "chapter2",
        "chapter3",
        "chapter4",
        "chapter5",
        "chapter6",
        "chapter7",
    )
    assert GENERATION_STATUSES == ("pending", "in_progress", "completed", "failed")


def test_an_empty_document_has_every_chapter_with_nothing_in_it() -> None:
    assert empty_content() == {key: {} for key in CHAPTER_KEYS}


def test_every_empty_document_is_a_separate_object() -> None:
    first, second = empty_content(), empty_content()
    first["chapter1"]["title"] = "changed"
    assert second == {key: {} for key in CHAPTER_KEYS}


def test_check_constraints_keep_the_migration_names() -> None:
    checks = {c.name: str(c.sqltext) for c in TABLE.constraints if isinstance(c, CheckConstraint)}
    assert set(checks) == {"valid_content_structure", "learning_documents_generation_status_check"}
    assert "jsonb_typeof(content) = 'object'" in checks["valid_content_structure"]
    for key in CHAPTER_KEYS:
        assert f"'{key}'" in checks["valid_content_structure"]
    for status in GENERATION_STATUSES:
        assert f"'{status}'" in checks["learning_documents_generation_status_check"]


def test_indexes_match_the_migration() -> None:
    indexes = {index.name: [c.name for c in index.columns] for index in TABLE.indexes}
    assert indexes == {
        "idx_learning_documents_task_id": ["task_id"],
        "idx_learning_documents_status": ["generation_status"],
        "idx_learning_documents_celery_task": ["celery_task_id"],
    }


def test_repr_shows_ids_and_status_but_not_the_content_or_the_error() -> None:
    document = LearningDocument(
        id=uuid.UUID(int=3),
        task_id=uuid.UUID(int=9),
        generation_status="failed",
        generation_error="비밀 오류",
        content={"chapter1": {"title": "비밀 제목"}},
    )
    text = repr(document)
    assert str(uuid.UUID(int=3)) in text
    assert str(uuid.UUID(int=9)) in text
    assert "failed" in text
    assert "비밀" not in text


def test_task_has_one_document_and_a_document_belongs_to_one_task() -> None:
    task_side = class_mapper(Task).relationships["learning_document"]
    document_side = class_mapper(LearningDocument).relationships["task"]
    assert task_side.mapper.class_ is LearningDocument
    assert document_side.mapper.class_ is Task
    assert task_side.back_populates == "task"
    assert document_side.back_populates == "learning_document"
    assert task_side.uselist is False
    assert document_side.uselist is False


def test_deleting_a_task_deletes_its_document_and_leaves_that_to_the_database() -> None:
    task_side = class_mapper(Task).relationships["learning_document"]
    assert task_side.cascade.delete is True
    assert task_side.cascade.delete_orphan is True
    assert task_side.passive_deletes is True


def test_relationships_never_lazy_load() -> None:
    assert class_mapper(Task).relationships["learning_document"].lazy == "raise"
    assert class_mapper(LearningDocument).relationships["task"].lazy == "raise"
