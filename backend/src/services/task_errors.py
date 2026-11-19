from src.services.errors import DomainError


class TaskNotFoundError(DomainError):
    """The task does not exist, or it (or its project) is in the trash: same answer for everyone."""

    code = "task_not_found"
    default_message = "요청한 Task를 찾을 수 없습니다. 삭제되었거나 존재하지 않는 Task입니다."


class TaskForbiddenError(DomainError):
    code = "task_forbidden"
    default_message = "이 Task에 접근할 권한이 없습니다."


class InvalidTaskTitleError(DomainError):
    code = "invalid_task_title"
    default_message = "Task 제목이 올바르지 않습니다."


class InvalidTaskDescriptionError(DomainError):
    code = "invalid_task_description"
    default_message = "Task 설명이 올바르지 않습니다."


class CodeNotFoundError(DomainError):
    """The task was created without code."""

    code = "code_not_found"
    default_message = "이 Task에는 업로드된 코드가 없습니다."


class CodeFileMissingError(DomainError):
    """A stored file is gone from the disk, or its stored path points outside the storage root."""

    code = "code_file_missing"
    default_message = "저장된 코드 파일을 찾을 수 없습니다."
