"""Response shapes of the document endpoints (contracts/phase6-document-generation-api.md).

Built field by field, so a column added to the model later (celery_task_id, ...) cannot leak.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from src.models import LearningDocument
from src.services.document.document_queue_service import DocumentStatus


class DocumentStatusResponse(BaseModel):
    status: str
    generation_started_at: datetime | None
    generation_completed_at: datetime | None
    elapsed_seconds: int | None
    estimated_total_seconds: int | None
    notice: str | None
    error: str | None


class DocumentResponse(BaseModel):
    task_id: uuid.UUID
    status: str
    content: dict[str, Any] | None
    generation_started_at: datetime | None
    generation_completed_at: datetime | None
    error: str | None
    created_at: datetime
    updated_at: datetime


def document_status_response(status: DocumentStatus) -> DocumentStatusResponse:
    return DocumentStatusResponse(
        status=status.status,
        generation_started_at=status.generation_started_at,
        generation_completed_at=status.generation_completed_at,
        elapsed_seconds=status.elapsed_seconds,
        estimated_total_seconds=status.estimated_total_seconds,
        notice=status.notice,
        error=status.error,
    )


def document_response(document: LearningDocument) -> DocumentResponse:
    status = document.generation_status or "pending"
    return DocumentResponse(
        task_id=document.task_id,
        status=status,
        # Only a finished document has content; the other states hold empty placeholders.
        content=document.content if status == "completed" else None,
        generation_started_at=document.generation_started_at,
        generation_completed_at=document.generation_completed_at,
        error=document.generation_error if status == "failed" else None,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )
