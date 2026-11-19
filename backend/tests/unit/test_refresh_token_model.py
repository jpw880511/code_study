import uuid
from typing import Any, cast

from sqlalchemy import Boolean, Column, DateTime, String, Table, Uuid
from sqlalchemy.orm import class_mapper
from sqlalchemy.schema import DefaultClause
from src.models import Base, RefreshToken, User
from src.models.base import CreatedAtMixin, UUIDPrimaryKeyMixin

TABLE = cast(Table, RefreshToken.__table__)


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


def test_registered_on_the_shared_metadata() -> None:
    assert RefreshToken.__tablename__ == "refresh_tokens"
    assert Base.metadata.tables["refresh_tokens"] is TABLE
    assert issubclass(RefreshToken, UUIDPrimaryKeyMixin)
    assert issubclass(RefreshToken, CreatedAtMixin)


def test_columns_match_the_migration_and_there_is_no_updated_at() -> None:
    assert set(TABLE.c.keys()) == {
        "id",
        "user_id",
        "token_hash",
        "expires_at",
        "created_at",
        "revoked",
        "revoked_at",
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


def test_token_hash_is_required_unique_and_255_characters_long() -> None:
    assert string_length("token_hash") == 255
    assert column("token_hash").nullable is False
    assert column("token_hash").unique is True


def test_expires_at_is_a_required_timezone_aware_timestamp_without_default() -> None:
    expires_at = column("expires_at")
    assert isinstance(expires_at.type, DateTime)
    assert expires_at.type.timezone is True
    assert expires_at.nullable is False
    assert expires_at.server_default is None


def test_created_at_is_required_with_a_database_default() -> None:
    created_at = column("created_at")
    assert created_at.nullable is False
    assert "CURRENT_TIMESTAMP" in default_sql("created_at")
    assert created_at.onupdate is None


def test_revoked_defaults_to_false_and_revoked_at_is_optional() -> None:
    assert isinstance(column("revoked").type, Boolean)
    assert column("revoked").nullable is True
    assert default_sql("revoked").lower() == "false"
    revoked_at = column("revoked_at")
    assert isinstance(revoked_at.type, DateTime)
    assert revoked_at.type.timezone is True
    assert revoked_at.nullable is True
    assert revoked_at.server_default is None


def test_indexes_match_the_migration() -> None:
    indexes = {index.name: [c.name for c in index.columns] for index in TABLE.indexes}
    assert indexes == {
        "idx_refresh_tokens_user_id": ["user_id"],
        "idx_refresh_tokens_hash": ["token_hash"],
        "idx_refresh_tokens_expires": ["expires_at"],
    }


def test_repr_never_shows_the_token_hash() -> None:
    token = RefreshToken(
        id=uuid.UUID(int=3), user_id=uuid.UUID(int=9), token_hash="deadbeef-secret-hash"
    )
    text = repr(token)
    assert str(uuid.UUID(int=3)) in text
    assert str(uuid.UUID(int=9)) in text
    assert "deadbeef" not in text
    assert "hash" not in text.lower()


def test_user_has_many_refresh_tokens_and_a_token_belongs_to_one_user() -> None:
    user_side = class_mapper(User).relationships["refresh_tokens"]
    token_side = class_mapper(RefreshToken).relationships["user"]
    assert user_side.mapper.class_ is RefreshToken
    assert token_side.mapper.class_ is User
    assert user_side.back_populates == "user"
    assert token_side.back_populates == "refresh_tokens"
    assert user_side.uselist is True
    assert token_side.uselist is False


def test_deleting_a_user_deletes_its_tokens_and_leaves_that_to_the_database() -> None:
    user_side = class_mapper(User).relationships["refresh_tokens"]
    assert user_side.cascade.delete is True
    assert user_side.cascade.delete_orphan is True
    assert user_side.passive_deletes is True


def test_relationships_never_lazy_load_so_async_code_must_load_them_explicitly() -> None:
    user_side = class_mapper(User).relationships["refresh_tokens"]
    token_side = class_mapper(RefreshToken).relationships["user"]
    assert user_side.lazy == "raise"
    assert token_side.lazy == "raise"
