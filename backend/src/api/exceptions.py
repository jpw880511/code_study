import logging
from collections.abc import Awaitable, Callable
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from src.services.errors import DomainError
from src.utils.file_validator import FileValidationError

logger = logging.getLogger(__name__)

ERROR_MESSAGES: dict[str, str] = {
    "bad_request": "요청이 올바르지 않습니다.",
    "unauthorized": "로그인이 필요합니다.",
    "forbidden": "접근 권한이 없습니다.",
    "not_found": "요청한 항목을 찾을 수 없습니다.",
    "method_not_allowed": "허용되지 않는 요청 방식입니다.",
    "conflict": "요청이 현재 상태와 충돌합니다.",
    "validation_error": "입력값이 올바르지 않습니다.",
    "http_error": "요청을 처리할 수 없습니다.",
    "internal_error": (
        "서버 오류가 발생했습니다. 잠시 후 다시 시도하세요. 문제가 계속되면 고객지원에 문의하세요."
    ),
}

ERROR_CODES_BY_STATUS = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    422: "validation_error",
}


# How the service layer's error codes appear on the wire. An unlisted code is still the
# caller's problem (400), never a server error.
AUTH_ERROR_STATUS = {
    "invalid_email": 422,
    "weak_password": 422,
    "email_already_registered": 409,
    "invalid_credentials": 401,
    "not_authenticated": 401,
    "session_expired": 401,
}

DOMAIN_ERROR_STATUS = {
    **AUTH_ERROR_STATUS,
    "project_not_found": 404,
    "project_forbidden": 403,
    "invalid_project_title": 422,
    "invalid_project_description": 422,
    "task_not_found": 404,
    "task_forbidden": 403,
    "code_not_found": 404,
    "code_file_missing": 404,
    "document_not_found": 404,
    "invalid_task_title": 422,
    "invalid_task_description": 422,
    "invalid_upload_method": 422,
    "no_files": 422,
    "too_many_files": 422,
    "invalid_file_path": 422,
    "language_required": 422,
    "unsupported_language": 422,
    "empty_code": 422,
}

# The upload validator's refusals (utils/file_validator.py) keep their own code, details and
# suggestion; only the status is chosen here.
FILE_VALIDATION_STATUS = {
    "file_too_large": 413,
    "unsupported_file_type": 415,
    "binary_file_rejected": 415,
}


class ErrorResponse(BaseModel):
    error: str
    message: str
    details: dict[str, Any] | None = None
    suggestion: str | None = None


class AppError(Exception):
    """Base class for errors that map to a structured JSON response."""

    status_code = 500
    error = "internal_error"

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
        suggestion: str | None = None,
    ) -> None:
        self.message = message or ERROR_MESSAGES.get(self.error, ERROR_MESSAGES["http_error"])
        self.details = details
        self.suggestion = suggestion
        super().__init__(self.message)


class NotFoundError(AppError):
    status_code = 404
    error = "not_found"


class ConflictError(AppError):
    status_code = 409
    error = "conflict"


class UnauthorizedError(AppError):
    status_code = 401
    error = "unauthorized"


class ForbiddenError(AppError):
    status_code = 403
    error = "forbidden"


def error_response(
    status_code: int,
    error: str,
    message: str,
    *,
    details: dict[str, Any] | None = None,
    suggestion: str | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body = ErrorResponse(error=error, message=message, details=details, suggestion=suggestion)
    return JSONResponse(
        status_code=status_code, content=body.model_dump(exclude_none=True), headers=headers
    )


def _standard_phrase(status_code: int) -> str | None:
    try:
        return HTTPStatus(status_code).phrase
    except ValueError:
        return None


async def handle_app_error(_: Request, exc: Exception) -> Response:
    assert isinstance(exc, AppError)
    return error_response(
        exc.status_code, exc.error, exc.message, details=exc.details, suggestion=exc.suggestion
    )


async def handle_domain_error(_: Request, exc: Exception) -> Response:
    assert isinstance(exc, DomainError)
    return error_response(DOMAIN_ERROR_STATUS.get(exc.code, 400), exc.code, exc.message)


async def handle_file_validation_error(_: Request, exc: Exception) -> Response:
    assert isinstance(exc, FileValidationError)
    return error_response(
        FILE_VALIDATION_STATUS.get(exc.code, 400),
        exc.code,
        exc.message,
        details=exc.details or None,
        suggestion=exc.suggestion,
    )


async def handle_http_exception(_: Request, exc: Exception) -> Response:
    assert isinstance(exc, StarletteHTTPException)
    code = ERROR_CODES_BY_STATUS.get(exc.status_code, "http_error")
    detail = exc.detail
    custom = isinstance(detail, str) and detail != _standard_phrase(exc.status_code)
    return error_response(
        exc.status_code,
        code,
        ERROR_MESSAGES[code],
        details={"detail": detail} if custom else None,
        headers=dict(exc.headers) if exc.headers else None,
    )


async def handle_validation_error(_: Request, exc: Exception) -> Response:
    assert isinstance(exc, RequestValidationError)
    errors = [
        {"field": ".".join(str(part) for part in e["loc"]), "message": e["msg"], "type": e["type"]}
        for e in exc.errors()
    ]
    return error_response(
        422,
        "validation_error",
        ERROR_MESSAGES["validation_error"],
        details={"errors": errors},
    )


class UnhandledErrorMiddleware(BaseHTTPMiddleware):
    """Turn unexpected exceptions into a generic 500 without leaking internals.

    It sits inside the CORS and request-metadata middleware so that 500 responses still
    carry CORS headers and the request id.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        try:
            return await call_next(request)
        except Exception:
            logger.exception(
                "Unhandled error [request_id=%s] %s %s",
                getattr(request.state, "request_id", "-"),
                request.method,
                request.url.path,
            )
            return error_response(500, "internal_error", ERROR_MESSAGES["internal_error"])


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, handle_app_error)
    app.add_exception_handler(DomainError, handle_domain_error)
    app.add_exception_handler(FileValidationError, handle_file_validation_error)
    app.add_exception_handler(StarletteHTTPException, handle_http_exception)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
