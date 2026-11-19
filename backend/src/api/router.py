from fastapi import APIRouter

from src.api.auth import auth_router
from src.api.documents import documents_router
from src.api.projects import projects_router
from src.api.tasks import tasks_router

API_PREFIX = "/api/v1"

api_router = APIRouter(prefix=API_PREFIX)


async def health() -> dict[str, str]:
    return {"status": "ok"}


api_router.add_api_route("/health", health, tags=["health"])
api_router.include_router(auth_router)
api_router.include_router(projects_router)
api_router.include_router(tasks_router)
api_router.include_router(documents_router)
