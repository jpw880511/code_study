import uuid
from typing import Any, cast

from sqlalchemy import CheckConstraint, Column, DateTime, String, Table, Uuid
from sqlalchemy.schema import DefaultClause
from src.models import User
from src.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

TABLE = cast(Table, User.__table__)


def column(name: str) -> Column[Any]:
    return TABLE.c[name]


def default_sql(name: str) -> str:
    server_default = column(name).server_default
    assert isinstance(server_default, DefaultClause)
    return str(server_default.arg)


def string_length(name: str) -> int | None:
    column_type = column(name).type
    assert isinstance(column_type, String)
    return column_type.length


def test_user_is_registered_on_the_shared_metadata() -> None:
    assert User.__tablename__ == "users"
    assert Base.metadata.tables["users"] is TABLE
    assert issubclass(User, UUIDPrimaryKeyMixin)
    assert issubclass(User, TimestampMixin)


def test_columns_match_the_migration() -> None:
    assert set(TABLE.c.keys()) == {
        "id",
        "email",
        "password_hash",
        "skill_level",
        "created_at",
        "updated_at",
        "last_login_at",
    }


def test_primary_key_is_a_database_generated_uuid() -> None:
    assert [c.name for c in TABLE.primary_key.columns] == ["id"]
    assert isinstance(column("id").type, Uuid)
    assert "gen_random_uuid()" in default_sql("id")


def test_email_is_unique_required_and_255_characters_long() -> None:
    email = column("email")
    assert string_length("email") == 255
    assert email.nullable is False
    assert email.unique is True


def test_password_hash_is_required_and_255_characters_long() -> None:
    assert string_length("password_hash") == 255
    assert column("password_hash").nullable is False


def test_skill_level_defaults_to_complete_beginner() -> None:
    assert string_length("skill_level") == 50
    assert column("skill_level").nullable is True
    assert "Complete Beginner" in default_sql("skill_level")


def test_timestamps_are_timezone_aware() -> None:
    for name in ("created_at", "updated_at", "last_login_at"):
        column_type = column(name).type
        assert isinstance(column_type, DateTime)
        assert column_type.timezone is True
    assert column("created_at").nullable is False
    assert column("updated_at").nullable is False
    assert column("last_login_at").nullable is True
    assert column("last_login_at").server_default is None


def test_updated_at_is_refreshed_by_the_orm_on_every_update() -> None:
    assert column("updated_at").onupdate is not None
    assert column("created_at").onupdate is None


def test_email_index_matches_the_migration() -> None:
    indexes = {index.name: [c.name for c in index.columns] for index in TABLE.indexes}
    assert indexes == {"idx_users_email": ["email"]}


def test_valid_email_check_keeps_its_migration_name() -> None:
    checks = [c for c in TABLE.constraints if isinstance(c, CheckConstraint)]
    assert [c.name for c in checks] == ["valid_email"]


def test_repr_identifies_the_user_without_leaking_the_password_hash() -> None:
    user = User(id=uuid.UUID(int=7), email="a@example.com", password_hash="$2b$12$secret-hash")
    text = repr(user)
    assert "a@example.com" in text
    assert str(uuid.UUID(int=7)) in text
    assert "secret-hash" not in text
    assert "password" not in text.lower()


def test_models_fetch_database_defaults_with_the_insert() -> None:
    """Required for async sessions: lazy-loading expired attributes is not possible there."""
    assert Base.__mapper_args__ == {"eager_defaults": True}
