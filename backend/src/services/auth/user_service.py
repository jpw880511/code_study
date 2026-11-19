import asyncio
import re
from datetime import UTC, datetime
from functools import lru_cache

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import RefreshToken, User
from src.models.user import EMAIL_PATTERN
from src.services.auth.errors import (
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    InvalidEmailError,
    WeakPasswordError,
)
from src.utils.security import (
    MAX_PASSWORD_BYTES,
    hash_password,
    hash_refresh_token,
    verify_password,
)

EMAIL_REGEX = re.compile(EMAIL_PATTERN, re.IGNORECASE)
MAX_EMAIL_LENGTH = 255
MIN_PASSWORD_LENGTH = 8


def normalize_email(email: str) -> str:
    """Trim and lowercase, so that A@x.com and a@x.com are the same account."""
    normalized = email.strip().lower()
    if len(normalized) > MAX_EMAIL_LENGTH or not EMAIL_REGEX.fullmatch(normalized):
        raise InvalidEmailError()
    return normalized


def validate_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise WeakPasswordError(f"비밀번호는 {MIN_PASSWORD_LENGTH}자 이상이어야 합니다.")
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise WeakPasswordError(
            f"비밀번호가 너무 깁니다. 최대 {MAX_PASSWORD_BYTES}바이트(영문 기준 "
            f"{MAX_PASSWORD_BYTES}자, 한글은 {MAX_PASSWORD_BYTES // 3}자)까지 가능합니다."
        )
    if not (any(c.isalpha() for c in password) and any(c.isdigit() for c in password)):
        raise WeakPasswordError("비밀번호에는 문자와 숫자가 모두 포함되어야 합니다.")


@lru_cache(maxsize=1)
def _dummy_password_hash() -> str:
    return hash_password("dummy-password-for-timing-1")


class UserService:
    """Registration, login and logout. It never commits: the request's session does."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def register(self, email: str, password: str) -> User:
        normalized = normalize_email(email)
        validate_password(password)
        if await self._email_taken(normalized):
            raise EmailAlreadyRegisteredError()

        # bcrypt takes a few hundred milliseconds: keep it off the event loop.
        password_hash = await asyncio.to_thread(hash_password, password)
        user = User(email=normalized, password_hash=password_hash)
        try:
            async with self.session.begin_nested():
                self.session.add(user)
        except IntegrityError as exc:  # a concurrent request registered the same email first
            raise EmailAlreadyRegisteredError() from exc
        return user

    async def login(self, email: str, password: str) -> User:
        """Return the user for valid credentials; every failure raises the same error.

        An unknown email is checked against a dummy hash, so it costs the same time as a wrong
        password and the response does not reveal which emails are registered.
        """
        try:
            normalized: str | None = normalize_email(email)
        except InvalidEmailError:
            normalized = None
        user = await self._find_by_email(normalized) if normalized else None

        stored_hash = user.password_hash if user else await asyncio.to_thread(_dummy_password_hash)
        password_matches = await asyncio.to_thread(verify_password, password, stored_hash)
        if user is None or not password_matches:
            raise InvalidCredentialsError()

        user.last_login_at = datetime.now(UTC)
        await self.session.flush()
        return user

    async def logout(self, refresh_token: str) -> bool:
        """Revoke this device's refresh token only. Returns False if there was nothing to revoke."""
        if not refresh_token:
            return False
        token = (
            await self.session.execute(
                select(RefreshToken).where(
                    RefreshToken.token_hash == hash_refresh_token(refresh_token)
                )
            )
        ).scalar_one_or_none()
        if token is None or token.revoked:
            return False

        token.revoked = True
        token.revoked_at = datetime.now(UTC)
        await self.session.flush()
        return True

    async def _email_taken(self, email: str) -> bool:
        return (
            await self.session.execute(select(User.id).where(User.email == email))
        ).first() is not None

    async def _find_by_email(self, email: str) -> User | None:
        return (
            await self.session.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()
