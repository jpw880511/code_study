import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from pytest import MonkeyPatch
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.models import RefreshToken, User
from src.services.auth import user_service as user_service_module
from src.services.auth.errors import (
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    InvalidEmailError,
    WeakPasswordError,
)
from src.services.auth.user_service import UserService
from src.utils.security import hash_refresh_token, verify_password

EMAIL = "student@example.com"
PASSWORD = "Passw0rd-ok"


async def count_users(session: AsyncSession) -> int:
    return (await session.execute(select(func.count()).select_from(User))).scalar_one()


async def registered(session: AsyncSession, email: str = EMAIL) -> User:
    return await UserService(session).register(email, PASSWORD)


class TestRegister:
    async def test_creates_a_user_with_a_normalized_email(self, session: AsyncSession) -> None:
        user = await UserService(session).register("  Student@Example.COM ", PASSWORD)

        # Already loaded: async sessions cannot lazy-load, so no refresh() here.
        assert user.id is not None
        assert user.email == EMAIL
        assert user.skill_level == "Complete Beginner"
        assert user.last_login_at is None
        assert user.created_at.tzinfo is not None

    async def test_stores_only_a_bcrypt_hash_of_the_password(self, session: AsyncSession) -> None:
        user = await registered(session)
        assert user.password_hash.startswith("$2b$12$")
        assert PASSWORD not in user.password_hash
        assert verify_password(PASSWORD, user.password_hash)

    async def test_the_user_is_visible_to_later_queries(self, session: AsyncSession) -> None:
        await registered(session)
        stored = (await session.execute(select(User).where(User.email == EMAIL))).scalar_one()
        assert stored.email == EMAIL

    @pytest.mark.parametrize(
        "second_email", [EMAIL, "STUDENT@EXAMPLE.COM", "  student@example.com"]
    )
    async def test_rejects_an_email_that_is_already_registered(
        self, session: AsyncSession, second_email: str
    ) -> None:
        await registered(session)
        with pytest.raises(EmailAlreadyRegisteredError):
            await UserService(session).register(second_email, PASSWORD)
        assert await count_users(session) == 1

    async def test_a_lost_race_is_reported_as_already_registered_and_the_session_survives(
        self, session: AsyncSession, monkeypatch: MonkeyPatch
    ) -> None:
        service = UserService(session)
        await service.register(EMAIL, PASSWORD)

        async def not_taken(_: str) -> bool:  # another request registered it in the meantime
            return False

        monkeypatch.setattr(service, "_email_taken", not_taken)
        with pytest.raises(EmailAlreadyRegisteredError):
            await service.register(EMAIL, PASSWORD)

        assert await count_users(session) == 1  # the session is still usable

    @pytest.mark.parametrize("bad_email", ["", "nope", "a@b", "a@@x.com"])
    async def test_rejects_an_invalid_email_without_touching_the_database(
        self, session: AsyncSession, bad_email: str
    ) -> None:
        with pytest.raises(InvalidEmailError):
            await UserService(session).register(bad_email, PASSWORD)
        assert await count_users(session) == 0

    @pytest.mark.parametrize("weak", ["short1", "onlyletters", "12345678", ""])
    async def test_rejects_a_weak_password_without_touching_the_database(
        self, session: AsyncSession, weak: str
    ) -> None:
        with pytest.raises(WeakPasswordError):
            await UserService(session).register(EMAIL, weak)
        assert await count_users(session) == 0

    async def test_two_users_with_the_same_password_get_different_hashes(
        self, session: AsyncSession
    ) -> None:
        first = await registered(session, "one@example.com")
        second = await registered(session, "two@example.com")
        assert first.password_hash != second.password_hash

    async def test_hashing_does_not_block_the_event_loop(self, session: AsyncSession) -> None:
        ticks = 0

        async def ticker() -> None:
            nonlocal ticks
            while True:
                await asyncio.sleep(0.01)
                ticks += 1

        task = asyncio.create_task(ticker())
        await registered(session)
        task.cancel()

        assert ticks >= 10  # a blocked loop (bcrypt takes ~0.3 s) would manage about 0


class TestLogin:
    async def test_returns_the_user_and_records_the_login_time(self, session: AsyncSession) -> None:
        created = await registered(session)

        user = await UserService(session).login(EMAIL, PASSWORD)

        assert user.id == created.id
        assert user.last_login_at is not None
        assert abs(user.last_login_at - datetime.now(UTC)) < timedelta(minutes=1)

    @pytest.mark.parametrize("typed", ["STUDENT@EXAMPLE.COM", "  Student@Example.com "])
    async def test_ignores_email_case_and_surrounding_spaces(
        self, session: AsyncSession, typed: str
    ) -> None:
        created = await registered(session)
        assert (await UserService(session).login(typed, PASSWORD)).id == created.id

    async def test_rejects_a_wrong_password_and_leaves_last_login_unchanged(
        self, session: AsyncSession
    ) -> None:
        created = await registered(session)
        with pytest.raises(InvalidCredentialsError):
            await UserService(session).login(EMAIL, "Wrong-passw0rd")
        assert created.last_login_at is None

    @pytest.mark.parametrize(
        ("email", "password"),
        [
            ("nobody@example.com", PASSWORD),  # unknown user
            ("not-an-email", PASSWORD),  # malformed address
            (EMAIL, ""),  # empty password
            (EMAIL, "a1" * 40),  # longer than bcrypt's 72 bytes
        ],
    )
    async def test_all_failures_look_the_same(
        self, session: AsyncSession, email: str, password: str
    ) -> None:
        await registered(session)
        with pytest.raises(InvalidCredentialsError) as caught:
            await UserService(session).login(email, password)
        assert caught.value.code == "invalid_credentials"
        assert "이메일 또는 비밀번호" in caught.value.message

    async def test_an_unknown_email_still_costs_a_password_check(
        self, session: AsyncSession, monkeypatch: MonkeyPatch
    ) -> None:
        """Equal work for known and unknown emails, so response time does not reveal accounts."""
        calls: list[str] = []

        def spy(password: str, password_hash: str) -> bool:
            calls.append(password_hash)
            return verify_password(password, password_hash)

        monkeypatch.setattr(user_service_module, "verify_password", spy)

        with pytest.raises(InvalidCredentialsError):
            await UserService(session).login("nobody@example.com", PASSWORD)

        assert len(calls) == 1
        assert calls[0].startswith("$2b$12$")

    async def test_the_error_does_not_leak_the_credentials(self, session: AsyncSession) -> None:
        with pytest.raises(InvalidCredentialsError) as caught:
            await UserService(session).login("nobody@example.com", "S3cret-typed")
        assert "S3cret-typed" not in str(caught.value)
        assert "nobody@example.com" not in str(caught.value)


class TestLogout:
    async def add_token(self, session: AsyncSession, user: User, raw_token: str) -> RefreshToken:
        token = RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(raw_token),
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        session.add(token)
        await session.flush()
        return token

    async def test_revokes_only_the_given_token(self, session: AsyncSession) -> None:
        user = await registered(session)
        mine = await self.add_token(session, user, "token-on-this-device")
        other = await self.add_token(session, user, "token-on-another-device")

        revoked = await UserService(session).logout("token-on-this-device")

        assert revoked is True
        assert mine.revoked is True
        assert mine.revoked_at is not None
        assert abs(mine.revoked_at - datetime.now(UTC)) < timedelta(minutes=1)
        assert not other.revoked
        assert other.revoked_at is None

    async def test_an_unknown_token_is_not_an_error(self, session: AsyncSession) -> None:
        await registered(session)
        assert await UserService(session).logout("never-issued") is False

    @pytest.mark.parametrize("empty", ["", None])
    async def test_an_empty_token_does_nothing(
        self, session: AsyncSession, empty: str | None
    ) -> None:
        user = await registered(session)
        token = await self.add_token(session, user, "kept")
        assert await UserService(session).logout(empty or "") is False
        assert not token.revoked

    async def test_logging_out_twice_keeps_the_first_revocation_time(
        self, session: AsyncSession
    ) -> None:
        user = await registered(session)
        token = await self.add_token(session, user, "once")
        service = UserService(session)
        assert await service.logout("once") is True
        first_revoked_at = token.revoked_at

        assert await service.logout("once") is False
        assert token.revoked_at == first_revoked_at

    async def test_a_token_whose_revoked_flag_is_null_counts_as_not_revoked(
        self, session: AsyncSession
    ) -> None:
        user = await registered(session)
        token = await self.add_token(session, user, "null-flag")
        token.revoked = None
        await session.flush()

        assert await UserService(session).logout("null-flag") is True
        assert token.revoked is True

    async def test_only_the_hash_is_compared_never_the_raw_token(
        self, session: AsyncSession
    ) -> None:
        user = await registered(session)
        token = await self.add_token(session, user, "real-token")
        # Sending the stored hash itself must not work: it is not a token anyone was given.
        assert await UserService(session).logout(token.token_hash) is False
        assert not token.revoked
