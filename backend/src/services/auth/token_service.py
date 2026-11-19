import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import RefreshToken
from src.services.auth.errors import NotAuthenticatedError, SessionExpiredError
from src.utils.jwt import (
    ExpiredTokenError,
    JWTSettings,
    TokenError,
    TokenPayload,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_jwt_settings,
)
from src.utils.security import hash_refresh_token


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    access_expires_at: datetime
    refresh_expires_at: datetime


class TokenService:
    """Issues, verifies and rotates the JWTs. It never commits: the request's session does.

    Access tokens are stateless; refresh tokens are also recorded (as a SHA-256 hash only) so
    that they can be revoked and used just once.
    """

    def __init__(self, session: AsyncSession, settings: JWTSettings | None = None) -> None:
        self.session = session
        self.settings = settings or get_jwt_settings()

    async def issue_tokens(self, user_id: uuid.UUID) -> TokenPair:
        subject = str(user_id)
        access_token = create_access_token(subject, settings=self.settings)
        refresh_token = create_refresh_token(subject, settings=self.settings)
        # Read the expiry back from the tokens so the stored value cannot drift from the JWT's.
        access = decode_token(access_token, "access", self.settings)
        refresh = decode_token(refresh_token, "refresh", self.settings)

        self.session.add(
            RefreshToken(
                user_id=user_id,
                token_hash=hash_refresh_token(refresh_token),
                expires_at=refresh.expires_at,
            )
        )
        await self.session.flush()
        return TokenPair(access_token, refresh_token, access.expires_at, refresh.expires_at)

    @staticmethod
    def verify_access_token(token: str, settings: JWTSettings | None = None) -> TokenPayload:
        """Check an access token without touching the database."""
        try:
            return decode_token(token, "access", settings)
        except ExpiredTokenError as exc:
            raise SessionExpiredError() from exc
        except TokenError as exc:
            raise NotAuthenticatedError() from exc

    async def rotate_refresh_token(self, refresh_token: str) -> TokenPair:
        """Trade a refresh token for a new pair; the old refresh token stops working.

        The row is locked while it is checked, so two simultaneous requests with the same token
        cannot both succeed. A token that was already used is simply refused: it does not revoke
        the user's newer tokens, because two browser tabs refreshing at once would otherwise log
        the user out everywhere.
        """
        try:
            payload = decode_token(refresh_token, "refresh", self.settings)
        except ExpiredTokenError as exc:
            raise SessionExpiredError() from exc
        except TokenError as exc:
            raise NotAuthenticatedError() from exc

        stored = (
            await self.session.execute(
                select(RefreshToken)
                .where(RefreshToken.token_hash == hash_refresh_token(refresh_token))
                .with_for_update()
            )
        ).scalar_one_or_none()
        if stored is None or stored.revoked or str(stored.user_id) != payload.subject:
            raise NotAuthenticatedError()

        now = datetime.now(UTC)
        if stored.expires_at <= now:
            raise SessionExpiredError()

        stored.revoked = True
        stored.revoked_at = now
        return await self.issue_tokens(stored.user_id)
