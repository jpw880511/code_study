import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.session import create_engine, create_session_factory
from src.models import RefreshToken, User
from src.services.auth.errors import NotAuthenticatedError, SessionExpiredError
from src.services.auth.token_service import TokenService
from src.services.auth.user_service import UserService
from src.utils.jwt import JWTSettings, create_refresh_token
from src.utils.security import hash_refresh_token

SETTINGS = JWTSettings(  # type: ignore[call-arg]
    _env_file=None, secret_key="a" * 40, refresh_secret_key="r" * 40
)


def service(session: AsyncSession) -> TokenService:
    return TokenService(session, SETTINGS)


async def saved_user(session: AsyncSession, email: str = "student@example.com") -> User:
    user = User(email=email, password_hash="$2b$12$hash")
    session.add(user)
    await session.flush()
    return user


async def stored_token(session: AsyncSession, raw_refresh_token: str) -> RefreshToken:
    return (
        await session.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == hash_refresh_token(raw_refresh_token)
            )
        )
    ).scalar_one()


async def count_tokens(session: AsyncSession) -> int:
    return (await session.execute(select(func.count()).select_from(RefreshToken))).scalar_one()


class TestIssueTokens:
    async def test_returns_a_working_access_and_refresh_token(self, session: AsyncSession) -> None:
        user = await saved_user(session)

        pair = await service(session).issue_tokens(user.id)

        access = TokenService.verify_access_token(pair.access_token, SETTINGS)
        assert access.subject == str(user.id)
        assert pair.refresh_token != pair.access_token

    async def test_access_lasts_15_minutes_and_refresh_7_days(self, session: AsyncSession) -> None:
        user = await saved_user(session)
        before = datetime.now(UTC)

        pair = await service(session).issue_tokens(user.id)

        assert (
            timedelta(minutes=14, seconds=55)
            < pair.access_expires_at - before
            < timedelta(minutes=15, seconds=5)
        )
        assert (
            timedelta(days=6, hours=23)
            < pair.refresh_expires_at - before
            < timedelta(days=7, minutes=1)
        )

    async def test_stores_only_the_hash_of_the_refresh_token(self, session: AsyncSession) -> None:
        user = await saved_user(session)

        pair = await service(session).issue_tokens(user.id)

        row = await stored_token(session, pair.refresh_token)
        assert row.user_id == user.id
        assert row.token_hash == hash_refresh_token(pair.refresh_token)
        assert row.token_hash != pair.refresh_token
        assert row.expires_at == pair.refresh_expires_at
        assert not row.revoked
        assert row.revoked_at is None
        # The raw token is nowhere in the table.
        found = (
            await session.execute(
                text("SELECT count(*) FROM refresh_tokens WHERE token_hash = :t"),
                {"t": pair.refresh_token},
            )
        ).scalar_one()
        assert found == 0

    async def test_every_call_gives_new_tokens_and_a_new_row(self, session: AsyncSession) -> None:
        user = await saved_user(session)

        first = await service(session).issue_tokens(user.id)
        second = await service(session).issue_tokens(user.id)

        assert first.access_token != second.access_token
        assert first.refresh_token != second.refresh_token
        assert await count_tokens(session) == 2

    async def test_a_user_that_does_not_exist_cannot_get_tokens(
        self, session: AsyncSession
    ) -> None:
        with pytest.raises(IntegrityError):
            await service(session).issue_tokens(uuid.uuid4())


class TestRotateRefreshToken:
    async def test_swaps_the_old_token_for_a_new_pair(self, session: AsyncSession) -> None:
        user = await saved_user(session)
        old = await service(session).issue_tokens(user.id)

        new = await service(session).rotate_refresh_token(old.refresh_token)

        assert new.refresh_token != old.refresh_token
        assert new.access_token != old.access_token
        assert TokenService.verify_access_token(new.access_token, SETTINGS).subject == str(user.id)
        old_row = await stored_token(session, old.refresh_token)
        new_row = await stored_token(session, new.refresh_token)
        assert old_row.revoked is True
        assert abs(old_row.revoked_at - datetime.now(UTC)) < timedelta(minutes=1)  # type: ignore[operator]
        assert not new_row.revoked
        assert new_row.user_id == user.id

    async def test_the_new_token_can_be_rotated_again(self, session: AsyncSession) -> None:
        user = await saved_user(session)
        first = await service(session).issue_tokens(user.id)
        second = await service(session).rotate_refresh_token(first.refresh_token)
        third = await service(session).rotate_refresh_token(second.refresh_token)
        assert third.refresh_token not in {first.refresh_token, second.refresh_token}

    async def test_an_old_token_cannot_be_used_twice(self, session: AsyncSession) -> None:
        user = await saved_user(session)
        old = await service(session).issue_tokens(user.id)
        await service(session).rotate_refresh_token(old.refresh_token)

        with pytest.raises(NotAuthenticatedError):
            await service(session).rotate_refresh_token(old.refresh_token)

    async def test_replaying_an_old_token_does_not_revoke_the_newer_one(
        self, session: AsyncSession
    ) -> None:
        """Two tabs refreshing at once must not log the user out everywhere."""
        user = await saved_user(session)
        old = await service(session).issue_tokens(user.id)
        new = await service(session).rotate_refresh_token(old.refresh_token)

        with pytest.raises(NotAuthenticatedError):
            await service(session).rotate_refresh_token(old.refresh_token)

        assert not (await stored_token(session, new.refresh_token)).revoked
        assert (await service(session).rotate_refresh_token(new.refresh_token)) is not None

    async def test_a_token_revoked_by_logout_cannot_be_rotated(self, session: AsyncSession) -> None:
        user = await saved_user(session)
        pair = await service(session).issue_tokens(user.id)
        assert await UserService(session).logout(pair.refresh_token) is True

        with pytest.raises(NotAuthenticatedError):
            await service(session).rotate_refresh_token(pair.refresh_token)

    async def test_other_devices_keep_their_tokens(self, session: AsyncSession) -> None:
        user = await saved_user(session)
        this_device = await service(session).issue_tokens(user.id)
        other_device = await service(session).issue_tokens(user.id)

        await service(session).rotate_refresh_token(this_device.refresh_token)

        assert not (await stored_token(session, other_device.refresh_token)).revoked

    async def test_a_valid_signature_is_not_enough_the_token_must_be_on_file(
        self, session: AsyncSession
    ) -> None:
        user = await saved_user(session)
        never_stored = create_refresh_token(str(user.id), settings=SETTINGS)

        with pytest.raises(NotAuthenticatedError):
            await service(session).rotate_refresh_token(never_stored)

    @pytest.mark.parametrize("bad", ["", "garbage", "a.b.c"])
    async def test_garbage_is_rejected(self, session: AsyncSession, bad: str) -> None:
        with pytest.raises(NotAuthenticatedError):
            await service(session).rotate_refresh_token(bad)

    async def test_an_access_token_is_not_accepted(self, session: AsyncSession) -> None:
        user = await saved_user(session)
        pair = await service(session).issue_tokens(user.id)
        with pytest.raises(NotAuthenticatedError):
            await service(session).rotate_refresh_token(pair.access_token)

    async def test_an_expired_token_means_the_session_expired(self, session: AsyncSession) -> None:
        user = await saved_user(session)
        expired = create_refresh_token(
            str(user.id), settings=SETTINGS, expires_delta=timedelta(seconds=-1)
        )
        with pytest.raises(SessionExpiredError):
            await service(session).rotate_refresh_token(expired)

    async def test_the_stored_expiry_is_checked_as_well(self, session: AsyncSession) -> None:
        user = await saved_user(session)
        token = create_refresh_token(str(user.id), settings=SETTINGS)  # still valid as a JWT
        session.add(
            RefreshToken(
                user_id=user.id,
                token_hash=hash_refresh_token(token),
                expires_at=datetime.now(UTC) - timedelta(minutes=1),
            )
        )
        await session.flush()

        with pytest.raises(SessionExpiredError):
            await service(session).rotate_refresh_token(token)

    async def test_a_token_naming_another_user_than_the_stored_one_is_rejected(
        self, session: AsyncSession
    ) -> None:
        alice = await saved_user(session, "alice@example.com")
        bob = await saved_user(session, "bob@example.com")
        token = create_refresh_token(str(bob.id), settings=SETTINGS)
        session.add(
            RefreshToken(
                user_id=alice.id,
                token_hash=hash_refresh_token(token),
                expires_at=datetime.now(UTC) + timedelta(days=1),
            )
        )
        await session.flush()

        with pytest.raises(NotAuthenticatedError):
            await service(session).rotate_refresh_token(token)

    async def test_a_subject_that_is_not_a_user_id_is_rejected(self, session: AsyncSession) -> None:
        token = create_refresh_token("123", settings=SETTINGS)
        with pytest.raises(NotAuthenticatedError):
            await service(session).rotate_refresh_token(token)

    async def test_tokens_of_a_deleted_user_stop_working(self, session: AsyncSession) -> None:
        user = await saved_user(session)
        pair = await service(session).issue_tokens(user.id)
        await session.delete(user)
        await session.flush()

        with pytest.raises(NotAuthenticatedError):
            await service(session).rotate_refresh_token(pair.refresh_token)

    async def test_a_failed_rotation_changes_nothing(self, session: AsyncSession) -> None:
        user = await saved_user(session)
        old = await service(session).issue_tokens(user.id)
        await service(session).rotate_refresh_token(old.refresh_token)
        rows_before = await count_tokens(session)

        with pytest.raises(NotAuthenticatedError):
            await service(session).rotate_refresh_token(old.refresh_token)

        assert await count_tokens(session) == rows_before


async def test_two_simultaneous_rotations_of_one_token_let_only_one_win(
    test_database_url: str, migrated_engine: object
) -> None:
    """Real commits and two connections: a double refresh must not mint two new tokens."""
    engine = create_engine(test_database_url)
    factory = create_session_factory(engine)
    email = "race@example.com"
    try:
        async with factory() as setup:
            user = await saved_user(setup, email)
            old = await TokenService(setup, SETTINGS).issue_tokens(user.id)
            user_id = user.id
            await setup.commit()

        async def rotate() -> str | None:
            async with factory() as db_session:
                try:
                    pair = await TokenService(db_session, SETTINGS).rotate_refresh_token(
                        old.refresh_token
                    )
                    await asyncio.sleep(0.2)  # hold the row lock so the other request must wait
                    await db_session.commit()
                    return pair.refresh_token
                except NotAuthenticatedError:
                    await db_session.rollback()
                    return None

        results = await asyncio.gather(rotate(), rotate())

        winners = [token for token in results if token is not None]
        assert len(winners) == 1
        async with factory() as check:
            live = (
                await check.execute(
                    select(func.count())
                    .select_from(RefreshToken)
                    .where(RefreshToken.user_id == user_id, RefreshToken.revoked.is_not(True))
                )
            ).scalar_one()
        assert live == 1
    finally:
        async with factory() as cleanup:
            await cleanup.execute(text("DELETE FROM users WHERE email = :e"), {"e": email})
            await cleanup.commit()
        await engine.dispose()
