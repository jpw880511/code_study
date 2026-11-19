import uuid
from typing import Any, cast

from sqlalchemy import CheckConstraint, Column, DateTime, Integer, String, Table, Text, Uuid
from sqlalchemy.orm import class_mapper
from sqlalchemy.schema import DefaultClause, UniqueConstraint
from src.models import Base, Project, Task
from src.models.base import TimestampMixin, UUIDPrimaryKeyMixin

TABLE = cast(Table, Task.__table__)


def column(name: str) -> Column[Any]:
    return TABLE.c[name]


def default_sql(name: str) -> str:
    server_default = column(name).server_default
    assert isinstance(server_default, DefaultClause)
    return str(server_default.arg)


def test_registered_on_the_shared_metadata() -> None:
    assert Task.__tablename__ == "tasks"
    assert Base.metadata.tables["tasks"] is TABLE
    assert issubclass(Task, UUIDPrimaryKeyMixin)
    assert issubclass(Task, TimestampMixin)


def test_columns_match_the_migration() -> None:
    assert set(TABLE.c.keys()) == {
        "id",
        "project_id",
        "task_number",
        "title",
        "description",
        "upload_method",
        "created_at",
        "updated_at",
        "deletion_status",
        "trashed_at",
        "scheduled_deletion_at",
    }


def test_primary_key_is_a_database_generated_uuid() -> None:
    assert [c.name for c in TABLE.primary_key.columns] == ["id"]
    assert isinstance(column("id").type, Uuid)
    assert "gen_random_uuid()" in default_sql("id")


def test_project_id_is_a_required_foreign_key_that_cascades_on_delete() -> None:
    project_id = column("project_id")
    assert isinstance(project_id.type, Uuid)
    assert project_id.nullable is False
    (foreign_key,) = project_id.foreign_keys
    assert foreign_key.target_fullname == "projects.id"
    assert foreign_key.ondelete == "CASCADE"


def test_task_number_is_a_required_integer_without_a_database_default() -> None:
    task_number = column("task_number")
    assert isinstance(task_number.type, Integer)
    assert task_number.nullable is False
    assert task_number.server_default is None


def test_title_is_required_and_255_characters_long() -> None:
    title = column("title")
    assert isinstance(title.type, String)
    assert title.type.length == 255
    assert title.nullable is False


def test_description_is_optional_text() -> None:
    description = column("description")
    assert isinstance(description.type, Text)
    assert description.nullable is True
    assert description.server_default is None


def test_upload_method_is_optional_and_20_characters_long() -> None:
    upload_method = column("upload_method")
    assert isinstance(upload_method.type, String)
    assert upload_method.type.length == 20
    assert upload_method.nullable is True
    assert upload_method.server_default is None


def test_timestamps_are_timezone_aware() -> None:
    for name in ("created_at", "updated_at", "trashed_at", "scheduled_deletion_at"):
        column_type = column(name).type
        assert isinstance(column_type, DateTime)
        assert column_type.timezone is True
    assert column("created_at").nullable is False
    assert column("updated_at").nullable is False
    for name in ("trashed_at", "scheduled_deletion_at"):
        assert column(name).nullable is True
        assert column(name).server_default is None


def test_deletion_status_defaults_to_active() -> None:
    status = column("deletion_status")
    assert isinstance(status.type, String)
    assert status.type.length == 20
    assert default_sql("deletion_status") == "active"


def test_check_constraints_keep_the_migration_names() -> None:
    checks = {c.name: str(c.sqltext) for c in TABLE.constraints if isinstance(c, CheckConstraint)}
    assert set(checks) == {
        "title_min_length",
        "description_max_length",
        "tasks_upload_method_check",
        "tasks_deletion_status_check",
    }
    assert "char_length(title) >= 5" in checks["title_min_length"]
    assert "char_length(description) <= 500" in checks["description_max_length"]
    for method in ("'file'", "'folder'", "'paste'"):
        assert method in checks["tasks_upload_method_check"]
    for status in ("'active'", "'trashed'"):
        assert status in checks["tasks_deletion_status_check"]


def test_task_number_is_unique_within_a_project() -> None:
    uniques = {
        c.name: [col.name for col in c.columns]
        for c in TABLE.constraints
        if isinstance(c, UniqueConstraint)
    }
    assert uniques == {"unique_task_number_per_project": ["project_id", "task_number"]}


def test_indexes_match_the_migration() -> None:
    indexes = {index.name: [c.name for c in index.columns] for index in TABLE.indexes}
    assert indexes == {
        "idx_tasks_project_id": ["project_id"],
        "idx_tasks_deletion_status": ["deletion_status"],
        "idx_tasks_project_active": ["project_id", "deletion_status"],
        "idx_tasks_number_order": ["project_id", "task_number"],
    }
    partial = next(i for i in TABLE.indexes if i.name == "idx_tasks_project_active")
    assert "deletion_status = 'active'" in str(partial.dialect_options["postgresql"]["where"])


def test_repr_shows_ids_but_not_the_content() -> None:
    task = Task(
        id=uuid.UUID(int=3),
        project_id=uuid.UUID(int=9),
        task_number=2,
        title="비밀 제목",
        description="비밀 설명",
    )
    text = repr(task)
    assert str(uuid.UUID(int=3)) in text
    assert str(uuid.UUID(int=9)) in text
    assert "비밀" not in text


def test_project_has_many_tasks_and_a_task_belongs_to_one_project() -> None:
    project_side = class_mapper(Project).relationships["tasks"]
    task_side = class_mapper(Task).relationships["project"]
    assert project_side.mapper.class_ is Task
    assert task_side.mapper.class_ is Project
    assert project_side.back_populates == "project"
    assert task_side.back_populates == "tasks"
    assert project_side.uselist is True
    assert task_side.uselist is False


def test_deleting_a_project_deletes_its_tasks_and_leaves_that_to_the_database() -> None:
    project_side = class_mapper(Project).relationships["tasks"]
    assert project_side.cascade.delete is True
    assert project_side.cascade.delete_orphan is True
    assert project_side.passive_deletes is True


def test_relationships_never_lazy_load() -> None:
    assert class_mapper(Project).relationships["tasks"].lazy == "raise"
    assert class_mapper(Task).relationships["project"].lazy == "raise"
