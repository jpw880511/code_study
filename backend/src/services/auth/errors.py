from src.services.errors import DomainError


class AuthError(DomainError):
    """Base class for authentication problems."""

    code = "auth_error"
    default_message = "인증 처리 중 오류가 발생했습니다."


class InvalidEmailError(AuthError):
    code = "invalid_email"
    default_message = "올바른 이메일 형식이 아닙니다."


class WeakPasswordError(AuthError):
    code = "weak_password"
    default_message = "비밀번호가 규칙에 맞지 않습니다."


class EmailAlreadyRegisteredError(AuthError):
    code = "email_already_registered"
    default_message = "이미 가입된 이메일입니다."


class InvalidCredentialsError(AuthError):
    code = "invalid_credentials"
    default_message = "이메일 또는 비밀번호가 올바르지 않습니다."


class NotAuthenticatedError(AuthError):
    code = "not_authenticated"
    default_message = "로그인이 필요합니다."


class SessionExpiredError(AuthError):
    code = "session_expired"
    default_message = "세션이 만료되었습니다. 다시 로그인하세요."
