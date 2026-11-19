import uuid

from fastapi import APIRouter

from src.api.dependencies import CurrentUser, DbSession, Notices
from src.api.document_schemas import (
    DocumentResponse,
    DocumentStatusResponse,
    document_response,
    document_status_response,
)
from src.services.document.document_queue_service import ACTIVE_STATUSES, DocumentQueueService
from src.services.task_service import TaskService

documents_router = APIRouter(tags=["documents"])


@documents_router.get("/tasks/{task_id}/document/status", response_model=DocumentStatusResponse)
async def get_document_status(
    task_id: uuid.UUID, user: CurrentUser, session: DbSession, notices: Notices
) -> DocumentStatusResponse:
    task = await TaskService(session).get(user.id, task_id)  # ownership, trash rules
    queue = DocumentQueueService(session)
    document = await queue.get(task.id)
    notice = None
    if document.generation_status in ACTIVE_STATUSES:
        notice = await notices.get(task.id)
    return document_status_response(queue.describe(task, document, notice))


@documents_router.get("/tasks/{task_id}/document", response_model=DocumentResponse)
async def get_document(
    task_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> DocumentResponse:
    task = await TaskService(session).get(user.id, task_id)
    return document_response(await DocumentQueueService(session).get(task.id))
