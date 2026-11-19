from typing import Literal

from fastapi import APIRouter

from src.api.exceptions import ConflictError, ForbiddenError, NotFoundError
from src.api.router import API_PREFIX

# Development-only helpers; create_app() does not mount this router in production.
debug_router = APIRouter(prefix=API_PREFIX, tags=["debug"])


@debug_router.get("/test-errors")
async def test_errors(
    type: Literal["notfound", "forbidden", "conflict"] | None = None,
) -> dict[str, str]:
    if type == "notfound":
        raise NotFoundError()
    if type == "forbidden":
        raise ForbiddenError()
    if type == "conflict":
        raise ConflictError()
    return {"status": "ok"}
