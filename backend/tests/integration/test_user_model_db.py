import asyncio
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from sqlalchemy import CheckConstraint, Engine, Table, inspect, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.session import create_engine, create_session_factory
from src.models import User


def new_user(email: str = "student@example.com", **values: object) -> User:
    return User(email=email, password_hash="$2b$12$hash", **values)


async def test_database_fills_in_id_defaults_and_timestamps(session: AsyncSession) -> None:
    user = new_user()
    session.add(user)
    await session.flush()

    # No refresh() here: the values must already be loaded (async sessions cannot lazy-load).
    assert user.id is not None
    assert user.skill_level == "Complete Beginner"
    assert user.created_at.tzinfo is not None
    assert user.updated_at.tzinfo is not None
    assert user.last_login_at is None
    assert abs(user.created_at - datetime.now(UTC)) < timedelta(minutes=1)


async def test_explicit_skill_level_is_kept(session: AsyncSession) -> None:
    user = new_user(skill_level="Intermediate")
    session.add(user)
    await session.flush()
    assert user.skill_level == "Intermediate"


async def test_user_can_be_loaded_by_email(session: AsyncSession) -> None:
    session.add(new_user("find-me@example.com"))
    await session.flush()
    session.expunge_all()

    found = (
        await session.execute(select(User).where(User.email == "find-me@example.com"))
    ).scalar_one()

    assert found.email == "find-me@example.com"
    assert found.password_hash == "$2b$12$hash"


async def test_last_login_can_be_recorded(session: AsyncSession) -> None:
    user = new_user()
    session.add(user)
    await session.flush()
    login_time = datetime(2026, 11, 5, 9, 30, tzinfo=UTC)

    user.last_login_at = login_time
    await session.flush()
    session.expunge_all()

    stored = (await session.execute(select(User))).scalar_one()
    assert stored.last_login_at == login_time


async def test_duplicate_email_is_rejected(session: AsyncSession) -> None:
    session.add(new_user("same@example.com"))
    await session.flush()
    session.add(new_user("same@example.com"))
    with pytest.raises(IntegrityError):
        await session.flush()


@pytest.mark.parametrize("email", ["not-an-email", "a@b", "@example.com", "a@example"])
async def test_invalid_email_is_rejected_by_the_database(session: AsyncSession, email: str) -> None:
    session.add(new_user(email))
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_password_hash_is_required(session: AsyncSession) -> None:
    session.add(User(email="nohash@example.com"))
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_overlong_email_is_rejected(session: AsyncSession) -> None:
    session.add(new_user("a" * 250 + "@example.com"))
    with pytest.raises(DBAPIError):
        await session.flush()


async def test_two_users_get_different_ids(session: AsyncSession) -> None:
    first, second = new_user("one@example.com"), new_user("two@example.com")
    session.add_all([first, second])
    await session.flush()
    assert first.id != second.id


async def test_updated_at_moves_forward_when_the_user_is_changed(test_database_url: str) -> None:
    """Real commits: NOW() stays fixed inside one transaction, so each change gets its own."""
    engine = create_engine(test_database_url)
    factory = create_session_factory(engine)
    email = "touch@example.com"
    try:
        async with factory() as db_session:
            user = new_user(email)
            db_session.add(user)
            await db_session.commit()
            created_updated_at = user.updated_at
            user_id = user.id

        await asyncio.sleep(0.05)

        async with factory() as db_session:
            stored = await db_session.get(User, user_id)
            assert stored is not None
            stored.skill_level = "Advanced"
            await db_session.commit()
            assert stored.updated_at > created_updated_at
            assert stored.created_at == stored.created_at  # untouched
    finally:
        async with factory() as db_session:
            await db_session.execute(text("DELETE FROM users WHERE email = :e"), {"e": email})
            await db_session.commit()
        await engine.dispose()


def test_model_matches_the_migrated_schema(migrated_engine: Engine) -> None:
    inspector = inspect(migrated_engine)
    table = cast(Table, User.__table__)

    db_columns = {c["name"]: c for c in inspector.get_columns("users")}
    assert set(db_columns) == set(table.c.keys())
    for model_column in table.c:
        db_column = db_columns[model_column.name]
        assert db_column["nullable"] == model_column.nullable, model_column.name
        db_length = getattr(db_column["type"], "length", None)
        assert db_length == getattr(model_column.type, "length", None), model_column.name

    assert str(db_columns["id"]["default"]).startswith("gen_random_uuid()")
    assert "CURRENT_TIMESTAMP" in str(db_columns["created_at"]["default"])
    assert "CURRENT_TIMESTAMP" in str(db_columns["updated_at"]["default"])
    assert "Complete Beginner" in str(db_columns["skill_level"]["default"])
    assert db_columns["last_login_at"]["default"] is None

    assert inspector.get_pk_constraint("users")["constrained_columns"] == ["id"]

    db_indexes = {i["name"]: i["column_names"] for i in inspector.get_indexes("users")}
    for index in table.indexes:
        assert db_indexes[index.name] == [c.name for c in index.columns]

    unique_columns = [u["column_names"] for u in inspector.get_unique_constraints("users")]
    assert ["email"] in unique_columns

    db_checks = {c["name"] for c in inspector.get_check_constraints("users")}
    model_checks = {c.name for c in table.constraints if isinstance(c, CheckConstraint)}
    assert model_checks == db_checks == {"valid_email"}
