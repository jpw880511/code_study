from src.services.errors import DomainError


class AIServiceError(DomainError):
    """The AI service could not give an answer. `retryable` tells the caller whether asking the
    same thing again may work (busy, timeout) or not (bad request, blocked, no key).

    The messages are for the learner and say nothing about the cause; the upstream error stays
    on `__cause__` and is never put in the message (it may carry details nobody should see).
    """

    code = "ai_error"
    default_message = "AI 서비스를 사용하는 중 오류가 발생했습니다."
    retryable = False

    def __init__(
        self,
        message: str | None = None,
        *,
        status_code: int | None = None,
        reason: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code  # HTTP status of the upstream answer, if there was one
        self.reason = reason  # why an answer was unusable (e.g. SAFETY, MAX_TOKENS)


class AINotConfiguredError(AIServiceError):
    code = "ai_not_configured"
    default_message = "AI 서비스가 설정되지 않았습니다. 관리자에게 문의하세요."
    retryable = False


class AIServiceUnavailableError(AIServiceError):
    """Overloaded, rate limited, failing on its side, too slow or not reachable."""

    code = "ai_unavailable"
    default_message = (
        "AI 서비스가 응답하지 않습니다. 잠시 후 다시 시도하거나 고객지원에 문의하세요."
    )
    retryable = True


class AIRequestRejectedError(AIServiceError):
    """The service understood the request and refused it (bad request, key rejected, ...)."""

    code = "ai_request_rejected"
    default_message = (
        "AI 서비스가 요청을 처리하지 못했습니다. 문제가 계속되면 고객지원에 문의하세요."
    )
    retryable = False


class AIResponseError(AIServiceError):
    """The service answered, but with nothing usable: blocked, cut off by a filter, or empty."""

    code = "ai_response_invalid"
    default_message = "AI가 답변을 만들지 못했습니다. 코드를 확인한 뒤 다시 시도하세요."
    retryable = False
