from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Response

from src.api.cookies import clear_auth_cookies, set_auth_cookies
from src.api.dependencies import (
    REFRESH_TOKEN_COOKIE,
    CurrentUser,
    DbSession,
    get_app_settings,
)
from src.api.exceptions import AUTH_ERROR_STATUS, error_response
from src.api.schemas import Credentials, UserResponse
from src.config import AppSettings
from src.services.auth.errors import AuthError, NotAuthenticatedError
from src.services.auth.token_service import TokenService
from src.services.auth.user_service import UserService
from src.utils.jwt import JWTSettings, get_jwt_settings

auth_router = APIRouter(prefix="/auth", tags=["auth"])

Settings = Annotated[AppSettings, Depends(get_app_settings)]
JwtSettings = Annotated[JWTSettings, Depends(get_jwt_settings)]
RefreshCookie = Annotated[str | None, Cookie(alias=REFRESH_TOKEN_COOKIE)]


def is_secure(settings: AppSettings) -> bool:
    """Cookies are Secure only in production; development runs on plain http://localhost."""
    return settings.environment == "production"


@auth_router.post("/register", status_code=201, response_model=UserResponse)
async def register(body: Credentials, session: DbSession) -> UserResponse:
    user = await UserService(session).register(body.email, body.password)
    return UserResponse.model_validate(user)


@auth_router.post("/login", response_model=UserResponse)
async def login(
    body: Credentials,
    response: Response,
    session: DbSession,
    settings: Settings,
    jwt_settings: JwtSettings,
) -> UserResponse:
    user = await UserService(session).login(body.email, body.password)
    pair = await TokenService(session, jwt_settings).issue_tokens(user.id)
    set_auth_cookies(response, pair, secure=is_secure(settings))
    return UserResponse.model_validate(user)


@auth_router.get("/me", response_model=UserResponse)
async def me(user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(user)


@auth_router.post("/logout", status_code=204)
async def logout(
    session: DbSession, settings: Settings, refresh_token: RefreshCookie = None
) -> Response:
    """Always succeeds, so a client with a dead session can still get its cookies cleared."""
    await UserService(session).logout(refresh_token or "")
    response = Response(status_code=204)
    clear_auth_cookies(response, secure=is_secure(settings))
    return response


@auth_router.post("/refresh", status_code=204)
async def refresh(
    session: DbSession,
    settings: Settings,
    jwt_settings: JwtSettings,
    refresh_token: RefreshCookie = None,
) -> Response:
    """Rotate the refresh token. A refused token also clears the cookies, so the client logs out."""
    try:
        if not refresh_token:
            raise NotAuthenticatedError()
        pair = await TokenService(session, jwt_settings).rotate_refresh_token(refresh_token)
    except AuthError as exc:
        failure = error_response(AUTH_ERROR_STATUS.get(exc.code, 401), exc.code, exc.message)
        clear_auth_cookies(failure, secure=is_secure(settings))
        return failure
    response = Response(status_code=204)
    set_auth_cookies(response, pair, secure=is_secure(settings))
    return response
