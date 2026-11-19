import uuid
from collections.abc import Callable, Coroutine
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, File, Form, Request, Response, UploadFile
from fastapi.routing import APIRoute

from src.api.dependencies import CurrentUser, DbSession, Dispatcher, Storage
from src.api.task_schemas import (
    CodeResponse,
    CreateTaskResponse,
    TaskDetailResponse,
    TaskResponse,
    TaskUpdate,
    code_response,
    create_task_response,
    task_detail_response,
    task_response,
)
from src.models.uploaded_code import MAX_UPLOAD_SIZE_BYTES
from src.services.code_analysis.code_upload_service import CodeUploadService, IncomingFile
from src.services.task_service import TaskService

# Starlette refuses a text field above 1 MB, but pasted code may be as large as a file (10 MB).
# Twice the limit lets a slightly oversized paste reach the service, which answers with the
# usual 413 file_too_large; anything far beyond that is refused by the parser (400).
MAX_FORM_FIELD_BYTES = 2 * MAX_UPLOAD_SIZE_BYTES


class LargeFieldRoute(APIRoute):
    """A route whose multipart form is parsed with the larger field limit above."""

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        handler = super().get_route_handler()

        async def with_large_fields(request: Request) -> Response:
            await request.form(max_part_size=MAX_FORM_FIELD_BYTES)  # cached for FastAPI's read
            return await handler(request)

        return with_large_fields


tasks_router = APIRouter(tags=["tasks"])


@tasks_router.get("/projects/{project_id}/tasks", response_model=list[TaskResponse])
async def list_tasks(
    project_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> list[TaskResponse]:
    tasks = await TaskService(session).list(user.id, project_id)
    return [task_response(t) for t in tasks]


async def create_task(
    project_id: uuid.UUID,
    user: CurrentUser,
    session: DbSession,
    storage: Storage,
    background: BackgroundTasks,
    dispatcher: Dispatcher,
    title: Annotated[str, Form()],
    upload_method: Annotated[str, Form()],
    description: Annotated[str | None, Form()] = None,
    files: Annotated[list[UploadFile] | None, File()] = None,
    paths: Annotated[list[str] | None, Form()] = None,
    code: Annotated[str | None, Form()] = None,
    language: Annotated[str | None, Form()] = None,
) -> CreateTaskResponse:
    result = await CodeUploadService(session, storage).create_task(
        user.id,
        project_id,
        title=title,
        description=description,
        upload_method=upload_method,
        files=[IncomingFile(name=f.filename or "", source=f) for f in files or []],
        paths=paths or [],
        code=code,
        language=language,
    )
    response = create_task_response(result)
    # Background tasks start only once the response is going out, i.e. after DbSession has
    # committed, and not at all when this handler or the commit failed.
    if result.document_job_id is not None:
        background.add_task(dispatcher.dispatch, result.task.id, result.document_job_id)
    return response


tasks_router.add_api_route(
    "/projects/{project_id}/tasks",
    create_task,
    methods=["POST"],
    status_code=201,
    response_model=CreateTaskResponse,
    route_class_override=LargeFieldRoute,
)


@tasks_router.get("/tasks/{task_id}", response_model=TaskDetailResponse)
async def get_task(task_id: uuid.UUID, user: CurrentUser, session: DbSession) -> TaskDetailResponse:
    return task_detail_response(await TaskService(session).get(user.id, task_id))


@tasks_router.patch("/tasks/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: uuid.UUID, body: TaskUpdate, user: CurrentUser, session: DbSession
) -> TaskResponse:
    task = await TaskService(session).update(
        user.id, task_id, **body.model_dump(exclude_unset=True)
    )
    return task_response(task)


@tasks_router.delete("/tasks/{task_id}", status_code=204)
async def delete_task(task_id: uuid.UUID, user: CurrentUser, session: DbSession) -> Response:
    await TaskService(session).soft_delete(user.id, task_id)
    return Response(status_code=204)


@tasks_router.get("/tasks/{task_id}/code", response_model=CodeResponse)
async def get_task_code(
    task_id: uuid.UUID, user: CurrentUser, session: DbSession, storage: Storage
) -> CodeResponse:
    return code_response(await CodeUploadService(session, storage).read_code(user.id, task_id))
