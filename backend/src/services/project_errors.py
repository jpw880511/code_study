from src.services.errors import DomainError


class ProjectNotFoundError(DomainError):
    """The project does not exist or is in the trash (the same answer for everyone)."""

    code = "project_not_found"
    default_message = (
        "요청한 프로젝트를 찾을 수 없습니다. 삭제되었거나 존재하지 않는 프로젝트입니다."
    )


class ProjectForbiddenError(DomainError):
    code = "project_forbidden"
    default_message = "이 프로젝트에 접근할 권한이 없습니다."


class InvalidProjectTitleError(DomainError):
    code = "invalid_project_title"
    default_message = "프로젝트 제목이 올바르지 않습니다."


class InvalidProjectDescriptionError(DomainError):
    code = "invalid_project_description"
    default_message = "프로젝트 설명이 올바르지 않습니다."
