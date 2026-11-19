from datetime import timedelta
from typing import Any

import jwt as pyjwt
import pytest
from pydantic import ValidationError
from src.utils.jwt import (
    ExpiredTokenError,
    InvalidTokenError,
    JWTSettings,
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_jwt_settings,
    verify_token,
)

ACCESS_SECRET = "a" * 40
REFRESH_SECRET = "r" * 40
USER_ID = "3f2b8c1e-0000-4000-8000-000000000001"


def make_settings(**values: Any) -> JWTSettings:
    options: dict[str, Any] = {
        "_env_file": None,
        "secret_key": ACCESS_SECRET,
        "refresh_secret_key": REFRESH_SECRET,
        **values,
    }
    return JWTSettings(**options)


@pytest.fixture
def settings() -> JWTSettings:
    return make_settings()


def test_access_token_round_trip(settings: JWTSettings) -> None:
    token = create_access_token(USER_ID, settings=settings)
    payload = decode_token(token, "access", settings=settings)
    assert payload.subject == USER_ID
    assert payload.token_type == "access"


def test_refresh_token_round_trip(settings: JWTSettings) -> None:
    token = create_refresh_token(USER_ID, settings=settings)
    payload = decode_token(token, "refresh", settings=settings)
    assert payload.subject == USER_ID
    assert payload.token_type == "refresh"


def test_default_lifetimes(settings: JWTSettings) -> None:
    access = decode_token(create_access_token(USER_ID, settings=settings), "access", settings)
    refresh = decode_token(create_refresh_token(USER_ID, settings=settings), "refresh", settings)
    assert access.expires_at - access.issued_at == timedelta(minutes=15)
    assert refresh.expires_at - refresh.issued_at == timedelta(days=7)


def test_custom_lifetime(settings: JWTSettings) -> None:
    token = create_access_token(USER_ID, settings=settings, expires_delta=timedelta(minutes=1))
    payload = decode_token(token, "access", settings)
    assert payload.expires_at - payload.issued_at == timedelta(minutes=1)


def test_each_token_has_unique_id(settings: JWTSettings) -> None:
    first = decode_token(create_refresh_token(USER_ID, settings=settings), "refresh", settings)
    second = decode_token(create_refresh_token(USER_ID, settings=settings), "refresh", settings)
    assert first.jti != second.jti


def test_access_and_refresh_use_different_secrets(settings: JWTSettings) -> None:
    access = create_access_token(USER_ID, settings=settings)
    refresh = create_refresh_token(USER_ID, settings=settings)
    with pytest.raises(InvalidTokenError):
        decode_token(access, "refresh", settings=settings)
    with pytest.raises(InvalidTokenError):
        decode_token(refresh, "access", settings=settings)


def test_token_type_claim_is_enforced_even_with_shared_secret() -> None:
    shared = make_settings(refresh_secret_key=ACCESS_SECRET)
    refresh = create_refresh_token(USER_ID, settings=shared)
    with pytest.raises(InvalidTokenError, match="type"):
        decode_token(refresh, "access", settings=shared)


def test_expired_token_is_rejected(settings: JWTSettings) -> None:
    token = create_access_token(USER_ID, settings=settings, expires_delta=timedelta(seconds=-1))
    with pytest.raises(ExpiredTokenError):
        decode_token(token, "access", settings=settings)


def test_expired_error_is_a_token_error() -> None:
    assert issubclass(ExpiredTokenError, TokenError)
    assert issubclass(InvalidTokenError, TokenError)


def test_tampered_token_is_rejected(settings: JWTSettings) -> None:
    token = create_access_token(USER_ID, settings=settings)
    header, body, signature = token.split(".")
    tampered = ".".join([header, body, signature[:-2] + ("AA" if signature[-2:] != "AA" else "BB")])
    with pytest.raises(InvalidTokenError):
        decode_token(tampered, "access", settings=settings)


def test_token_signed_with_other_secret_is_rejected(settings: JWTSettings) -> None:
    other = make_settings(secret_key="z" * 40)
    token = create_access_token(USER_ID, settings=other)
    with pytest.raises(InvalidTokenError):
        decode_token(token, "access", settings=settings)


def test_unsigned_token_is_rejected(settings: JWTSettings) -> None:
    claims = {"sub": USER_ID, "type": "access", "exp": 9999999999}
    token = pyjwt.encode(claims, None, algorithm="none")  # type: ignore[arg-type]
    with pytest.raises(InvalidTokenError):
        decode_token(token, "access", settings=settings)


@pytest.mark.parametrize("garbage", ["", "abc", "a.b.c"])
def test_garbage_is_rejected(settings: JWTSettings, garbage: str) -> None:
    with pytest.raises(InvalidTokenError):
        decode_token(garbage, "access", settings=settings)


def test_token_without_subject_is_rejected(settings: JWTSettings) -> None:
    token = pyjwt.encode(
        {"type": "access", "exp": 9999999999, "iat": 1, "jti": "x"}, ACCESS_SECRET, "HS256"
    )
    with pytest.raises(InvalidTokenError):
        decode_token(token, "access", settings=settings)


def test_empty_subject_is_refused(settings: JWTSettings) -> None:
    with pytest.raises(ValueError, match="subject"):
        create_access_token("", settings=settings)


def test_verify_token(settings: JWTSettings) -> None:
    good = create_access_token(USER_ID, settings=settings)
    expired = create_access_token(USER_ID, settings=settings, expires_delta=timedelta(seconds=-1))
    assert verify_token(good, "access", settings=settings) is True
    assert verify_token(good, "refresh", settings=settings) is False
    assert verify_token(expired, "access", settings=settings) is False
    assert verify_token("garbage", "access", settings=settings) is False


@pytest.mark.parametrize("field", ["secret_key", "refresh_secret_key"])
def test_short_secret_is_rejected(field: str) -> None:
    with pytest.raises(ValidationError):
        make_settings(**{field: "too-short"})


def test_settings_defaults() -> None:
    s = make_settings()
    assert s.algorithm == "HS256"
    assert s.access_token_expire_minutes == 15
    assert s.refresh_token_expire_days == 7


def test_settings_read_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", ACCESS_SECRET)
    monkeypatch.setenv("JWT_REFRESH_SECRET", REFRESH_SECRET)
    monkeypatch.setenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    get_jwt_settings.cache_clear()
    loaded = get_jwt_settings()
    assert loaded.secret_key == ACCESS_SECRET
    assert loaded.refresh_secret_key == REFRESH_SECRET
    assert loaded.access_token_expire_minutes == 30
    get_jwt_settings.cache_clear()


def test_missing_secrets_give_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    monkeypatch.delenv("JWT_REFRESH_SECRET", raising=False)
    get_jwt_settings.cache_clear()
    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        get_jwt_settings()
    get_jwt_settings.cache_clear()
