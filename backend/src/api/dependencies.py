import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Cookie, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import AppSettings
from src.db import session as session_module
from src.db.session import get_session
from src.models import User
from src.services.auth.errors import NotAuthenticatedError
from src.services.auth.token_service import TokenService
from src.services.code_analysis.file_storage import FileStorage
from src.services.document.document_dispatcher import DocumentDispatcher
from src.services.document.document_notice_store import NoticeStore
from src.tasks import document_generation
from src.tasks.celery_app import RedisSettings
from src.utils.jwt import JWTSettings, get_jwt_settings

# The JWTs travel in HTTP-only cookies (research.md), so the access token is read from there.
ACCESS_TOKEN_COOKIE = "access_token"
REFRESH_TOKEN_COOKIE = "refresh_token"
# The refresh cookie is only sent to the auth endpoints, which are the only ones that read it.
REFRESH_COOKIE_PATH = "/api/v1/auth"

# One session per request (see db/session.py). scope="function" ends it (so it commits) right
# after the endpoint returns and BEFORE the response is sent: a client that receives a 2xx can
# rely on the data being stored, and a failed commit becomes a 500 instead of a lie.
DbSession = Annotated[AsyncSession, Depends(get_session, scope="function")]


def get_app_settings(request: Request) -> AppSettings:
    settings: AppSettings = request.app.state.settings
    return settings


def get_file_storage(settings: Annotated[AppSettings, Depends(get_app_settings)]) -> FileStorage:
    return FileStorage(settings.upload_storage_path)


def get_document_dispatcher() -> DocumentDispatcher:
    # Looked up when a request asks, not when this module loads, so tests can replace them.
    return DocumentDispatcher(
        document_generation.enqueue_generation, session_module.get_session_factory
    )


async def get_notice_store() -> AsyncIterator[NoticeStore]:
    """The Redis note store of a request. It connects on first use and fails quietly."""
    store = NoticeStore.from_url(RedisSettings().redis_url)
    try:
        yield store
    finally:
        await store.aclose()


async def get_current_user_id(
    settings: Annotated[JWTSettings, Depends(get_jwt_settings)],
    access_token: Annotated[str | None, Cookie(alias=ACCESS_TOKEN_COOKIE)] = None,
) -> uuid.UUID:
    """The id of the logged-in user, from the access token alone (no database query)."""
    if not access_token:
        raise NotAuthenticatedError()
    payload = TokenService.verify_access_token(access_token, settings)
    try:
        return uuid.UUID(payload.subject)
    except ValueError as exc:
        raise NotAuthenticatedError() from exc


async def get_current_user(
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    session: DbSession,
) -> User:
    """The logged-in user. A valid token for a user that was deleted since is refused."""
    user = await session.get(User, user_id)
    if user is None:
        raise NotAuthenticatedError()
    return user


# Use these as endpoint parameter types: `async def handler(user: CurrentUser): ...`
CurrentUserId = Annotated[uuid.UUID, Depends(get_current_user_id)]
CurrentUser = Annotated[User, Depends(get_current_user)]
Storage = Annotated[FileStorage, Depends(get_file_storage)]
Dispatcher = Annotated[DocumentDispatcher, Depends(get_document_dispatcher)]
Notices = Annotated[NoticeStore, Depends(get_notice_store)]
