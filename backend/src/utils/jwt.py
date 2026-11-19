import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import jwt
from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

TokenType = Literal["access", "refresh"]

PROJECT_ROOT = Path(__file__).resolve().parents[3]
MIN_SECRET_LENGTH = 32


class TokenError(Exception):
    """Base class for every token validation failure."""


class InvalidTokenError(TokenError):
    pass


class ExpiredTokenError(TokenError):
    pass


class JWTSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env", env_prefix="JWT_", extra="ignore", populate_by_name=True
    )

    secret_key: str = Field(min_length=MIN_SECRET_LENGTH, validation_alias="JWT_SECRET_KEY")
    refresh_secret_key: str = Field(
        min_length=MIN_SECRET_LENGTH, validation_alias="JWT_REFRESH_SECRET"
    )
    algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=15, ge=1)
    refresh_token_expire_days: int = Field(default=7, ge=1)

    def secret_for(self, token_type: TokenType) -> str:
        return self.secret_key if token_type == "access" else self.refresh_secret_key


@dataclass(frozen=True)
class TokenPayload:
    subject: str
    token_type: TokenType
    issued_at: datetime
    expires_at: datetime
    jti: str


@lru_cache
def get_jwt_settings() -> JWTSettings:
    try:
        return JWTSettings()  # type: ignore[call-arg]
    except ValidationError as exc:
        raise RuntimeError(
            f"JWT_SECRET_KEY and JWT_REFRESH_SECRET must be set "
            f"(at least {MIN_SECRET_LENGTH} characters each)"
        ) from exc


def _create_token(
    subject: str,
    token_type: TokenType,
    lifetime: timedelta,
    settings: JWTSettings | None,
) -> str:
    if not subject:
        raise ValueError("subject must not be empty")
    settings = settings or get_jwt_settings()
    issued_at = datetime.now(UTC).replace(microsecond=0)
    claims: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": issued_at,
        "exp": issued_at + lifetime,
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(claims, settings.secret_for(token_type), algorithm=settings.algorithm)


def create_access_token(
    subject: str,
    *,
    settings: JWTSettings | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    settings = settings or get_jwt_settings()
    lifetime = expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    return _create_token(subject, "access", lifetime, settings)


def create_refresh_token(
    subject: str,
    *,
    settings: JWTSettings | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    settings = settings or get_jwt_settings()
    lifetime = expires_delta or timedelta(days=settings.refresh_token_expire_days)
    return _create_token(subject, "refresh", lifetime, settings)


def decode_token(
    token: str, token_type: TokenType, settings: JWTSettings | None = None
) -> TokenPayload:
    settings = settings or get_jwt_settings()
    try:
        claims = jwt.decode(
            token,
            settings.secret_for(token_type),
            algorithms=[settings.algorithm],
            options={"require": ["exp", "iat", "sub", "jti"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise ExpiredTokenError("Token has expired") from exc
    except jwt.PyJWTError as exc:
        raise InvalidTokenError("Token is invalid") from exc

    if claims.get("type") != token_type:
        raise InvalidTokenError(f"Unexpected token type, expected {token_type}")
    return TokenPayload(
        subject=claims["sub"],
        token_type=token_type,
        issued_at=datetime.fromtimestamp(claims["iat"], UTC),
        expires_at=datetime.fromtimestamp(claims["exp"], UTC),
        jti=claims["jti"],
    )


def verify_token(token: str, token_type: TokenType, settings: JWTSettings | None = None) -> bool:
    try:
        decode_token(token, token_type, settings)
    except TokenError:
        return False
    return True
