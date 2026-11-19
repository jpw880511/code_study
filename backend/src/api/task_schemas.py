"""Request and response shapes of the task endpoints (contracts/phase5-tasks-upload-api.md).

The responses list their fields explicitly and are built field by field from the models, so a
column added to a model later (storage_path, user_id, the deletion fields) cannot leak into the
API by accident.
"""

import uuid
from datetime import datetime
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, model_validator

from src.models import CodeFile, Task
from src.services.code_analysis.code_upload_service import (
    StoredCode,
    UploadResult,
    sort_files,
)


class TaskUpdate(BaseModel):
    """A partial update: only the fields present in the JSON body change.

    `description: null` clears the description; `title: null` is present (and invalid).
    """

    title: str | None = None
    description: str | None = None

    @model_validator(mode="after")
    def at_least_one_field(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("title 또는 description 중 하나 이상을 보내야 합니다.")
        return self


class UploadSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    detected_language: str | None
    complexity_level: str | None
    total_lines: int | None
    total_files: int | None
    upload_size_bytes: int | None


class CodeFileSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    file_name: str
    file_path: str | None
    file_extension: str | None
    file_size_bytes: int | None
    mime_type: str | None


class TaskResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    task_number: int
    title: str
    description: str | None
    upload_method: str | None
    created_at: datetime
    updated_at: datetime
    upload: UploadSummary | None


class TaskDetailResponse(TaskResponse):
    files: list[CodeFileSummary]


class UploadWarningResponse(BaseModel):
    code: str
    message: str


class CreateTaskResponse(TaskDetailResponse):
    excluded_paths: list[str]
    warnings: list[UploadWarningResponse]


class CodeFileContent(CodeFileSummary):
    language: str
    content: str


class CodeResponse(BaseModel):
    files: list[CodeFileContent]


def _task_fields(task: Task) -> dict[str, Any]:
    return {
        "id": task.id,
        "project_id": task.project_id,
        "task_number": task.task_number,
        "title": task.title,
        "description": task.description,
        "upload_method": task.upload_method,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "upload": UploadSummary.model_validate(task.uploaded_code) if task.uploaded_code else None,
    }


def _files(task: Task) -> list[CodeFileSummary]:
    files: list[CodeFile] = task.uploaded_code.code_files if task.uploaded_code else []
    return [CodeFileSummary.model_validate(f) for f in sort_files(files)]


def task_response(task: Task) -> TaskResponse:
    return TaskResponse(**_task_fields(task))


def task_detail_response(task: Task) -> TaskDetailResponse:
    return TaskDetailResponse(**_task_fields(task), files=_files(task))


def create_task_response(result: UploadResult) -> CreateTaskResponse:
    return CreateTaskResponse(
        **_task_fields(result.task),
        files=_files(result.task),
        excluded_paths=result.excluded_paths,
        warnings=[UploadWarningResponse(code=w.code, message=w.message) for w in result.warnings],
    )


def code_response(codes: list[StoredCode]) -> CodeResponse:
    return CodeResponse(
        files=[
            CodeFileContent(
                **CodeFileSummary.model_validate(c.file).model_dump(),
                language=c.language,
                content=c.content,
            )
            for c in codes
        ]
    )
