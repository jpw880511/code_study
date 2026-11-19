class DomainError(Exception):
    """Base class for problems the services report (auth, projects, ...).

    Services raise these instead of HTTP errors, so the service layer stays independent of the
    API layer. The API maps each `code` to a response.
    """

    code = "domain_error"
    default_message = "요청을 처리하는 중 오류가 발생했습니다."

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.default_message
        super().__init__(self.message)
