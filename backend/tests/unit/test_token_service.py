from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta

import jwt as pyjwt
import pytest
from src.services.auth.errors import AuthError, NotAuthenticatedError, SessionExpiredError
from src.services.auth.token_service import TokenPair, TokenService
from src.utils.jwt import (
    ExpiredTokenError,
    InvalidTokenError,
    JWTSettings,
    create_access_token,
    create_refresh_token,
)

USER_ID = "3f2b8c1e-0000-4000-8000-000000000001"


def make_settings(**values: object) -> JWTSettings:
    options: dict[str, object] = {
        "_env_file": None,
        "secret_key": "a" * 40,
        "refresh_secret_key": "r" * 40,
        **values,
    }
    return JWTSettings(**options)  # type: ignore[arg-type]


@pytest.fixture
def settings() -> JWTSettings:
    return make_settings()


class TestErrors:
    @pytest.mark.parametrize(
        ("error", "code", "message"),
        [
            (NotAuthenticatedError(), "not_authenticated", "로그인이 필요합니다."),
            (SessionExpiredError(), "session_expired", "세션이 만료되었습니다. 다시 로그인하세요."),
        ],
    )
    def test_codes_and_messages_follow_the_requirements_addendum(
        self, error: AuthError, code: str, message: str
    ) -> None:
        assert isinstance(error, AuthError)
        assert error.code == code
        assert error.message == message


class TestTokenPair:
    def test_is_immutable(self) -> None:
        now = datetime.now(UTC)
        pair = TokenPair("access", "refresh", now, now)
        with pytest.raises(FrozenInstanceError):
            pair.access_token = "other"  # type: ignore[misc]


class TestVerifyAccessToken:
    def test_returns_the_payload_of_a_valid_token(self, settings: JWTSettings) -> None:
        token = create_access_token(USER_ID, settings=settings)

        payload = TokenService.verify_access_token(token, settings)

        assert payload.subject == USER_ID
        assert payload.token_type == "access"

    def test_needs_no_database_session(self, settings: JWTSettings) -> None:
        # Called on the class: the auth dependency can verify a request without opening a session.
        token = create_access_token(USER_ID, settings=settings)
        assert TokenService.verify_access_token(token, settings).subject == USER_ID

    def test_an_expired_token_means_the_session_expired(self, settings: JWTSettings) -> None:
        token = create_access_token(USER_ID, settings=settings, expires_delta=timedelta(seconds=-1))

        with pytest.raises(SessionExpiredError) as caught:
            TokenService.verify_access_token(token, settings)

        assert isinstance(caught.value.__cause__, ExpiredTokenError)

    @pytest.mark.parametrize("garbage", ["", "abc", "a.b.c"])
    def test_garbage_means_not_authenticated(self, settings: JWTSettings, garbage: str) -> None:
        with pytest.raises(NotAuthenticatedError) as caught:
            TokenService.verify_access_token(garbage, settings)
        assert isinstance(caught.value.__cause__, InvalidTokenError)

    def test_a_refresh_token_is_not_accepted_as_an_access_token(
        self, settings: JWTSettings
    ) -> None:
        refresh = create_refresh_token(USER_ID, settings=settings)
        with pytest.raises(NotAuthenticatedError):
            TokenService.verify_access_token(refresh, settings)

    def test_a_token_signed_with_another_secret_is_rejected(self, settings: JWTSettings) -> None:
        forged = create_access_token(USER_ID, settings=make_settings(secret_key="z" * 40))
        with pytest.raises(NotAuthenticatedError):
            TokenService.verify_access_token(forged, settings)

    def test_an_unsigned_token_is_rejected(self, settings: JWTSettings) -> None:
        unsigned = pyjwt.encode(
            {"sub": USER_ID, "type": "access", "exp": 9999999999},
            None,
            algorithm="none",  # type: ignore[arg-type]
        )
        with pytest.raises(NotAuthenticatedError):
            TokenService.verify_access_token(unsigned, settings)

    def test_error_messages_do_not_contain_the_token(self, settings: JWTSettings) -> None:
        token = create_access_token(USER_ID, settings=settings, expires_delta=timedelta(seconds=-1))
        with pytest.raises(SessionExpiredError) as caught:
            TokenService.verify_access_token(token, settings)
        assert token not in str(caught.value)
