import uuid
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from sqlalchemy import Engine, Table, func, inspect, select
from sqlalchemy.exc import DBAPIError, IntegrityError, InvalidRequestError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from src.models import RefreshToken, User

IN_A_WEEK = datetime.now(UTC) + timedelta(days=7)


def new_user(email: str = "student@example.com") -> User:
    return User(email=email, password_hash="$2b$12$hash")


def new_token(user: User, token_hash: str = "a" * 64, **values: object) -> RefreshToken:
    return RefreshToken(user_id=user.id, token_hash=token_hash, expires_at=IN_A_WEEK, **values)


async def saved_user(session: AsyncSession, email: str = "student@example.com") -> User:
    user = new_user(email)
    session.add(user)
    await session.flush()
    return user


async def count_tokens(session: AsyncSession) -> int:
    return (await session.execute(select(func.count()).select_from(RefreshToken))).scalar_one()


async def test_database_fills_in_id_created_at_and_revoked(session: AsyncSession) -> None:
    token = new_token(await saved_user(session))
    session.add(token)
    await session.flush()

    # No refresh(): the values must already be loaded (async sessions cannot lazy-load).
    assert token.id is not None
    assert token.created_at.tzinfo is not None
    assert abs(token.created_at - datetime.now(UTC)) < timedelta(minutes=1)
    assert token.revoked is False
    assert token.revoked_at is None
    assert token.expires_at == IN_A_WEEK


async def test_token_can_be_revoked(session: AsyncSession) -> None:
    token = new_token(await saved_user(session))
    session.add(token)
    await session.flush()
    revoked_at = datetime(2026, 11, 5, 12, 0, tzinfo=UTC)

    token.revoked = True
    token.revoked_at = revoked_at
    await session.flush()
    session.expunge_all()

    stored = (await session.execute(select(RefreshToken))).scalar_one()
    assert stored.revoked is True
    assert stored.revoked_at == revoked_at


async def test_token_is_found_by_its_hash(session: AsyncSession) -> None:
    user = await saved_user(session)
    session.add_all([new_token(user, "1" * 64), new_token(user, "2" * 64)])
    await session.flush()
    session.expunge_all()

    found = (
        await session.execute(select(RefreshToken).where(RefreshToken.token_hash == "2" * 64))
    ).scalar_one()

    assert found.token_hash == "2" * 64


async def test_token_hash_must_be_unique(session: AsyncSession) -> None:
    user = await saved_user(session)
    session.add(new_token(user, "same-hash"))
    await session.flush()
    session.add(new_token(user, "same-hash"))
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_token_hash_is_limited_to_255_characters(session: AsyncSession) -> None:
    session.add(new_token(await saved_user(session), "h" * 256))
    with pytest.raises(DBAPIError):
        await session.flush()


async def test_user_id_is_required(session: AsyncSession) -> None:
    session.add(RefreshToken(token_hash="x" * 64, expires_at=IN_A_WEEK))
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_expires_at_is_required(session: AsyncSession) -> None:
    user = await saved_user(session)
    session.add(RefreshToken(user_id=user.id, token_hash="x" * 64))
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_token_must_belong_to_an_existing_user(session: AsyncSession) -> None:
    session.add(RefreshToken(user_id=uuid.uuid4(), token_hash="x" * 64, expires_at=IN_A_WEEK))
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_user_can_have_many_tokens_and_load_them_explicitly(session: AsyncSession) -> None:
    user = await saved_user(session)
    other = await saved_user(session, "other@example.com")
    session.add_all(
        [new_token(user, "1" * 64), new_token(user, "2" * 64), new_token(other, "3" * 64)]
    )
    await session.flush()
    session.expunge_all()

    loaded = (
        await session.execute(
            select(User)
            .where(User.email == "student@example.com")
            .options(selectinload(User.refresh_tokens))
        )
    ).scalar_one()

    assert sorted(t.token_hash for t in loaded.refresh_tokens) == ["1" * 64, "2" * 64]


async def test_token_can_load_its_user_explicitly(session: AsyncSession) -> None:
    user = await saved_user(session)
    session.add(new_token(user))
    await session.flush()
    session.expunge_all()

    token = (
        await session.execute(select(RefreshToken).options(selectinload(RefreshToken.user)))
    ).scalar_one()

    assert token.user.email == "student@example.com"


async def test_relationships_must_be_loaded_explicitly_in_async_code(session: AsyncSession) -> None:
    user = await saved_user(session)
    session.add(new_token(user))
    await session.flush()
    session.expunge_all()

    stored = (await session.execute(select(User))).scalar_one()

    with pytest.raises(InvalidRequestError):
        _ = stored.refresh_tokens


async def test_deleting_a_user_deletes_its_tokens(session: AsyncSession) -> None:
    user = await saved_user(session)
    other = await saved_user(session, "other@example.com")
    session.add_all(
        [new_token(user, "1" * 64), new_token(user, "2" * 64), new_token(other, "3" * 64)]
    )
    await session.flush()

    await session.delete(user)
    await session.flush()

    remaining = (await session.execute(select(RefreshToken.token_hash))).scalars().all()
    assert remaining == ["3" * 64]


async def test_removing_a_token_from_the_user_deletes_the_row(session: AsyncSession) -> None:
    user = await saved_user(session)
    session.add_all([new_token(user, "1" * 64), new_token(user, "2" * 64)])
    await session.flush()
    session.expunge_all()
    loaded = (
        await session.execute(select(User).options(selectinload(User.refresh_tokens)))
    ).scalar_one()

    loaded.refresh_tokens.remove(loaded.refresh_tokens[0])
    await session.flush()

    assert await count_tokens(session) == 1


def test_model_matches_the_migrated_schema(migrated_engine: Engine) -> None:
    inspector = inspect(migrated_engine)
    table = cast(Table, RefreshToken.__table__)

    db_columns = {c["name"]: c for c in inspector.get_columns("refresh_tokens")}
    assert set(db_columns) == set(table.c.keys())
    for model_column in table.c:
        db_column = db_columns[model_column.name]
        assert db_column["nullable"] == model_column.nullable, model_column.name
        db_length = getattr(db_column["type"], "length", None)
        assert db_length == getattr(model_column.type, "length", None), model_column.name

    assert str(db_columns["id"]["default"]).startswith("gen_random_uuid()")
    assert "CURRENT_TIMESTAMP" in str(db_columns["created_at"]["default"])
    assert str(db_columns["revoked"]["default"]).lower() == "false"
    assert db_columns["expires_at"]["default"] is None
    assert db_columns["revoked_at"]["default"] is None

    assert inspector.get_pk_constraint("refresh_tokens")["constrained_columns"] == ["id"]

    (foreign_key,) = inspector.get_foreign_keys("refresh_tokens")
    assert foreign_key["constrained_columns"] == ["user_id"]
    assert foreign_key["referred_table"] == "users"
    assert foreign_key["referred_columns"] == ["id"]
    assert foreign_key["options"]["ondelete"] == "CASCADE"

    db_indexes = {i["name"]: i["column_names"] for i in inspector.get_indexes("refresh_tokens")}
    for index in table.indexes:
        assert db_indexes[index.name] == [c.name for c in index.columns]

    unique_columns = [u["column_names"] for u in inspector.get_unique_constraints("refresh_tokens")]
    assert ["token_hash"] in unique_columns
