from datetime import UTC, datetime, timedelta

from fastapi import Response
from src.api.cookies import clear_auth_cookies, seconds_until, set_auth_cookies
from src.api.dependencies import ACCESS_TOKEN_COOKIE, REFRESH_COOKIE_PATH, REFRESH_TOKEN_COOKIE
from src.services.auth.token_service import TokenPair


def test_seconds_until_counts_down_and_never_goes_negative() -> None:
    now = datetime.now(UTC)
    assert 98 <= seconds_until(now + timedelta(seconds=100)) <= 100
    assert seconds_until(now - timedelta(seconds=5)) == 0


def test_set_auth_cookies_sets_both_cookies_from_the_pair() -> None:
    now = datetime.now(UTC)
    pair = TokenPair("A", "R", now + timedelta(minutes=15), now + timedelta(days=7))
    response = Response()

    set_auth_cookies(response, pair, secure=False)

    headers = response.headers.getlist("set-cookie")
    assert len(headers) == 2
    access = next(h for h in headers if h.startswith(f"{ACCESS_TOKEN_COOKIE}=A;"))
    refresh = next(h for h in headers if h.startswith(f"{REFRESH_TOKEN_COOKIE}=R;"))
    assert "Path=/;" in access and f"Path={REFRESH_COOKIE_PATH};" in refresh
    assert all("HttpOnly" in h and "SameSite=strict" in h for h in (access, refresh))
    assert all("Secure" not in h for h in headers)


def test_secure_flag_follows_the_argument() -> None:
    response = Response()
    clear_auth_cookies(response, secure=True)
    assert all("Secure" in h for h in response.headers.getlist("set-cookie"))
