from src.services.ai.errors import AIServiceError
from src.services.errors import DomainError


class DocumentGenerationError(AIServiceError):
    """The AI answered, but never with a document that passes the checks, even after being asked
    again with the problems pointed out. `problems` are those of the last answer."""

    code = "document_generation_failed"
    default_message = (
        "학습 문서를 만들지 못했습니다. "
        "더 작은 코드 파일로 다시 업로드하거나 고객지원에 문의하세요."
    )
    retryable = False  # it has already been retried

    def __init__(self, problems: list[str], *, model_calls: int) -> None:
        super().__init__()
        self.problems = problems
        self.model_calls = model_calls


class DocumentNotFoundError(DomainError):
    """The task has no learning document: made before documents existed, or never queued."""

    code = "document_not_found"
    default_message = "이 Task에는 아직 학습 문서가 없습니다."
