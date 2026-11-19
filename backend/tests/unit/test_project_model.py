import uuid
from typing import Any, cast

from sqlalchemy import CheckConstraint, Column, DateTime, String, Table, Text, Uuid
from sqlalchemy.orm import class_mapper
from sqlalchemy.schema import DefaultClause
from src.models import Base, Project, User
from src.models.base import TimestampMixin, UUIDPrimaryKeyMixin

TABLE = cast(Table, Project.__table__)


def column(name: str) -> Column[Any]:
    return TABLE.c[name]


def default_sql(name: str) -> str:
    server_default = column(name).server_default
    assert isinstance(server_default, DefaultClause)
    return str(server_default.arg)


def test_registered_on_the_shared_metadata() -> None:
    assert Project.__tablename__ == "projects"
    assert Base.metadata.tables["projects"] is TABLE
    assert issubclass(Project, UUIDPrimaryKeyMixin)
    assert issubclass(Project, TimestampMixin)


def test_columns_match_the_migration() -> None:
    assert set(TABLE.c.keys()) == {
        "id",
        "user_id",
        "title",
        "description",
        "created_at",
        "updated_at",
        "last_activity_at",
        "deletion_status",
        "trashed_at",
        "scheduled_deletion_at",
    }


def test_primary_key_is_a_database_generated_uuid() -> None:
    assert [c.name for c in TABLE.primary_key.columns] == ["id"]
    assert isinstance(column("id").type, Uuid)
    assert "gen_random_uuid()" in default_sql("id")


def test_user_id_is_a_required_foreign_key_that_cascades_on_delete() -> None:
    user_id = column("user_id")
    assert isinstance(user_id.type, Uuid)
    assert user_id.nullable is False
    (foreign_key,) = user_id.foreign_keys
    assert foreign_key.target_fullname == "users.id"
    assert foreign_key.ondelete == "CASCADE"


def test_title_is_required_and_255_characters_long() -> None:
    title = column("title")
    assert isinstance(title.type, String)
    assert title.type.length == 255
    assert title.nullable is False


def test_description_is_optional_unbounded_text() -> None:
    description = column("description")
    assert isinstance(description.type, Text)
    assert description.type.length is None
    assert description.nullable is True
    assert description.server_default is None


def test_timestamps_are_timezone_aware() -> None:
    for name in (
        "created_at",
        "updated_at",
        "last_activity_at",
        "trashed_at",
        "scheduled_deletion_at",
    ):
        column_type = column(name).type
        assert isinstance(column_type, DateTime)
        assert column_type.timezone is True
    assert column("created_at").nullable is False
    assert column("updated_at").nullable is False
    assert column("last_activity_at").nullable is True
    assert "CURRENT_TIMESTAMP" in default_sql("last_activity_at")
    for name in ("trashed_at", "scheduled_deletion_at"):
        assert column(name).nullable is True
        assert column(name).server_default is None


def test_deletion_status_defaults_to_active() -> None:
    status = column("deletion_status")
    assert isinstance(status.type, String)
    assert status.type.length == 20
    assert status.nullable is True
    assert default_sql("deletion_status") == "active"


def test_check_constraints_keep_the_migration_names() -> None:
    checks = {c.name: str(c.sqltext) for c in TABLE.constraints if isinstance(c, CheckConstraint)}
    assert set(checks) == {"title_min_length", "projects_deletion_status_check"}
    assert "char_length(title) >= 1" in checks["title_min_length"]
    assert "'active'" in checks["projects_deletion_status_check"]
    assert "'trashed'" in checks["projects_deletion_status_check"]


def test_indexes_match_the_migration() -> None:
    indexes = {index.name: [c.name for c in index.columns] for index in TABLE.indexes}
    assert indexes == {
        "idx_projects_user_id": ["user_id"],
        "idx_projects_deletion_status": ["deletion_status"],
        "idx_projects_user_active": ["user_id", "deletion_status"],
    }
    partial = next(i for i in TABLE.indexes if i.name == "idx_projects_user_active")
    where = partial.dialect_options["postgresql"]["where"]
    assert "deletion_status = 'active'" in str(where)


def test_repr_shows_ids_but_not_the_content() -> None:
    project = Project(
        id=uuid.UUID(int=3), user_id=uuid.UUID(int=9), title="비밀 제목", description="비밀 설명"
    )
    text = repr(project)
    assert str(uuid.UUID(int=3)) in text
    assert str(uuid.UUID(int=9)) in text
    assert "비밀" not in text


def test_user_has_many_projects_and_a_project_belongs_to_one_user() -> None:
    user_side = class_mapper(User).relationships["projects"]
    project_side = class_mapper(Project).relationships["user"]
    assert user_side.mapper.class_ is Project
    assert project_side.mapper.class_ is User
    assert user_side.back_populates == "user"
    assert project_side.back_populates == "projects"
    assert user_side.uselist is True
    assert project_side.uselist is False


def test_deleting_a_user_deletes_its_projects_and_leaves_that_to_the_database() -> None:
    user_side = class_mapper(User).relationships["projects"]
    assert user_side.cascade.delete is True
    assert user_side.cascade.delete_orphan is True
    assert user_side.passive_deletes is True


def test_relationships_never_lazy_load() -> None:
    assert class_mapper(User).relationships["projects"].lazy == "raise"
    assert class_mapper(Project).relationships["user"].lazy == "raise"
