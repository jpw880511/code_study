import uuid
from typing import Any, cast

from sqlalchemy import CheckConstraint, Column, DateTime, Integer, String, Table, Uuid
from sqlalchemy.orm import class_mapper
from sqlalchemy.schema import DefaultClause, UniqueConstraint
from src.models import Base, Task, UploadedCode
from src.models.base import CreatedAtMixin, UUIDPrimaryKeyMixin

TABLE = cast(Table, UploadedCode.__table__)


def column(name: str) -> Column[Any]:
    return TABLE.c[name]


def default_sql(name: str) -> str:
    server_default = column(name).server_default
    assert isinstance(server_default, DefaultClause)
    return str(server_default.arg)


def test_registered_on_the_shared_metadata() -> None:
    assert UploadedCode.__tablename__ == "uploaded_code"
    assert Base.metadata.tables["uploaded_code"] is TABLE
    assert issubclass(UploadedCode, UUIDPrimaryKeyMixin)
    assert issubclass(UploadedCode, CreatedAtMixin)


def test_columns_match_the_migration() -> None:
    # The table has no updated_at: an upload is never edited, only replaced.
    assert set(TABLE.c.keys()) == {
        "id",
        "task_id",
        "detected_language",
        "complexity_level",
        "total_lines",
        "total_files",
        "upload_size_bytes",
        "created_at",
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


def test_a_task_has_at_most_one_uploaded_code() -> None:
    uniques = {
        c.name: [col.name for col in c.columns]
        for c in TABLE.constraints
        if isinstance(c, UniqueConstraint)
    }
    assert uniques == {"uploaded_code_task_id_key": ["task_id"]}


def test_detected_language_is_optional_and_50_characters_long() -> None:
    language = column("detected_language")
    assert isinstance(language.type, String)
    assert language.type.length == 50
    assert language.nullable is True


def test_complexity_level_is_optional_and_20_characters_long() -> None:
    level = column("complexity_level")
    assert isinstance(level.type, String)
    assert level.type.length == 20
    assert level.nullable is True


def test_counters_are_optional_integers() -> None:
    for name in ("total_lines", "total_files", "upload_size_bytes"):
        assert isinstance(column(name).type, Integer), name
        assert column(name).nullable is True, name
        assert column(name).server_default is None, name


def test_created_at_is_a_required_timezone_aware_timestamp() -> None:
    created_at = column("created_at")
    assert isinstance(created_at.type, DateTime)
    assert created_at.type.timezone is True
    assert created_at.nullable is False
    assert "CURRENT_TIMESTAMP" in default_sql("created_at")


def test_check_constraints_keep_the_migration_names() -> None:
    checks = {c.name: str(c.sqltext) for c in TABLE.constraints if isinstance(c, CheckConstraint)}
    assert set(checks) == {"valid_upload_size", "uploaded_code_complexity_level_check"}
    assert "upload_size_bytes <= 10485760" in checks["valid_upload_size"]
    for level in ("'beginner'", "'intermediate'", "'advanced'"):
        assert level in checks["uploaded_code_complexity_level_check"]


def test_indexes_match_the_migration() -> None:
    indexes = {index.name: [c.name for c in index.columns] for index in TABLE.indexes}
    assert indexes == {"idx_uploaded_code_task_id": ["task_id"]}


def test_repr_shows_ids_but_not_the_content() -> None:
    upload = UploadedCode(
        id=uuid.UUID(int=3), task_id=uuid.UUID(int=9), detected_language="비밀언어"
    )
    text = repr(upload)
    assert str(uuid.UUID(int=3)) in text
    assert str(uuid.UUID(int=9)) in text
    assert "비밀" not in text


def test_task_has_one_uploaded_code_and_an_upload_belongs_to_one_task() -> None:
    task_side = class_mapper(Task).relationships["uploaded_code"]
    upload_side = class_mapper(UploadedCode).relationships["task"]
    assert task_side.mapper.class_ is UploadedCode
    assert upload_side.mapper.class_ is Task
    assert task_side.back_populates == "task"
    assert upload_side.back_populates == "uploaded_code"
    assert task_side.uselist is False
    assert upload_side.uselist is False


def test_deleting_a_task_deletes_its_upload_and_leaves_that_to_the_database() -> None:
    task_side = class_mapper(Task).relationships["uploaded_code"]
    assert task_side.cascade.delete is True
    assert task_side.cascade.delete_orphan is True
    assert task_side.passive_deletes is True


def test_relationships_never_lazy_load() -> None:
    assert class_mapper(Task).relationships["uploaded_code"].lazy == "raise"
    assert class_mapper(UploadedCode).relationships["task"].lazy == "raise"
