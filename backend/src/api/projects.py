import uuid

from fastapi import APIRouter, Response

from src.api.dependencies import CurrentUser, DbSession
from src.api.schemas import ProjectCreate, ProjectResponse, ProjectUpdate
from src.services.project_service import ProjectService

projects_router = APIRouter(prefix="/projects", tags=["projects"])


@projects_router.get("", response_model=list[ProjectResponse])
async def list_projects(user: CurrentUser, session: DbSession) -> list[ProjectResponse]:
    projects = await ProjectService(session).list(user.id)
    return [ProjectResponse.model_validate(p) for p in projects]


@projects_router.post("", status_code=201, response_model=ProjectResponse)
async def create_project(
    body: ProjectCreate, user: CurrentUser, session: DbSession
) -> ProjectResponse:
    project = await ProjectService(session).create(user.id, body.title, body.description)
    return ProjectResponse.model_validate(project)


@projects_router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> ProjectResponse:
    project = await ProjectService(session).get(user.id, project_id)
    return ProjectResponse.model_validate(project)


@projects_router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID, body: ProjectUpdate, user: CurrentUser, session: DbSession
) -> ProjectResponse:
    project = await ProjectService(session).update(
        user.id, project_id, **body.model_dump(exclude_unset=True)
    )
    return ProjectResponse.model_validate(project)


@projects_router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: uuid.UUID, user: CurrentUser, session: DbSession) -> Response:
    await ProjectService(session).soft_delete(user.id, project_id)
    return Response(status_code=204)
