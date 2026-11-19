from datetime import UTC, datetime

from fastapi import Response

from src.api.dependencies import ACCESS_TOKEN_COOKIE, REFRESH_COOKIE_PATH, REFRESH_TOKEN_COOKIE
from src.services.auth.token_service import TokenPair

# Both cookies are invisible to scripts and never sent on cross-site requests.
COOKIE_OPTIONS = {"httponly": True, "samesite": "strict"}
ACCESS_COOKIE_PATH = "/"


def seconds_until(moment: datetime) -> int:
    return max(0, int((moment - datetime.now(UTC)).total_seconds()))


def set_auth_cookies(response: Response, pair: TokenPair, *, secure: bool) -> None:
    response.set_cookie(
        ACCESS_TOKEN_COOKIE,
        pair.access_token,
        max_age=seconds_until(pair.access_expires_at),
        path=ACCESS_COOKIE_PATH,
        secure=secure,
        **COOKIE_OPTIONS,  # type: ignore[arg-type]
    )
    response.set_cookie(
        REFRESH_TOKEN_COOKIE,
        pair.refresh_token,
        max_age=seconds_until(pair.refresh_expires_at),
        path=REFRESH_COOKIE_PATH,
        secure=secure,
        **COOKIE_OPTIONS,  # type: ignore[arg-type]
    )


def clear_auth_cookies(response: Response, *, secure: bool) -> None:
    """Expire both cookies; the path must match the one they were set with."""
    for name, path in (
        (ACCESS_TOKEN_COOKIE, ACCESS_COOKIE_PATH),
        (REFRESH_TOKEN_COOKIE, REFRESH_COOKIE_PATH),
    ):
        response.delete_cookie(name, path=path, secure=secure, **COOKIE_OPTIONS)  # type: ignore[arg-type]
