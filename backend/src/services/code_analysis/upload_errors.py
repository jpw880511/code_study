from src.services.errors import DomainError


class InvalidUploadMethodError(DomainError):
    code = "invalid_upload_method"
    default_message = "업로드 방식이 올바르지 않습니다. file, folder, paste 중 하나를 선택하세요."


class NoFilesError(DomainError):
    code = "no_files"
    default_message = "업로드할 파일을 선택하세요."


class TooManyFilesError(DomainError):
    code = "too_many_files"
    default_message = (
        "업로드당 최대 20개 파일까지 가능합니다. 파일 수를 줄이거나 폴더 업로드를 사용하세요."
    )


class InvalidFilePathError(DomainError):
    code = "invalid_file_path"
    default_message = "파일 경로가 올바르지 않습니다."


class LanguageRequiredError(DomainError):
    code = "language_required"
    default_message = "업로드하기 전에 프로그래밍 언어를 선택하세요."


class UnsupportedLanguageError(DomainError):
    code = "unsupported_language"
    default_message = "지원하지 않는 프로그래밍 언어입니다."


class EmptyCodeError(DomainError):
    code = "empty_code"
    default_message = "붙여넣은 코드가 비어 있습니다."
