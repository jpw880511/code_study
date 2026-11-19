import pytest
from src.services.errors import DomainError
from src.services.task_errors import (
    CodeFileMissingError,
    CodeNotFoundError,
    InvalidTaskDescriptionError,
    InvalidTaskTitleError,
    TaskForbiddenError,
    TaskNotFoundError,
)
from src.services.task_service import normalize_task_description, normalize_task_title

# --- title ---------------------------------------------------------------------------------


def test_title_is_trimmed() -> None:
    assert normalize_task_title("  계산기 함수 학습 \n") == "계산기 함수 학습"


@pytest.mark.parametrize("title", ["abcd", "  abcd  ", "", "     ", "가나다라"])
def test_title_shorter_than_five_characters_is_refused(title: str) -> None:
    with pytest.raises(InvalidTaskTitleError) as raised:
        normalize_task_title(title)
    assert raised.value.message == "Task 제목은 최소 5자 이상이어야 합니다."


def test_none_title_is_refused_as_too_short() -> None:
    with pytest.raises(InvalidTaskTitleError, match="최소 5자"):
        normalize_task_title(None)


def test_title_boundaries_are_five_and_255_characters() -> None:
    assert normalize_task_title("가나다라마") == "가나다라마"
    assert normalize_task_title("a" * 255) == "a" * 255
    with pytest.raises(InvalidTaskTitleError) as raised:
        normalize_task_title("a" * 256)
    assert raised.value.message == "Task 제목은 최대 255자까지 입력 가능합니다."


def test_title_with_a_nul_character_is_refused() -> None:
    with pytest.raises(InvalidTaskTitleError) as raised:
        normalize_task_title("제목\x00입니다")
    assert raised.value.message == "Task 제목에 사용할 수 없는 문자가 포함되어 있습니다."


# --- description ---------------------------------------------------------------------------


def test_description_is_trimmed_and_blank_becomes_none() -> None:
    assert normalize_task_description("  설명  ") == "설명"
    assert normalize_task_description("   ") is None
    assert normalize_task_description("") is None
    assert normalize_task_description(None) is None


def test_description_limit_is_500_characters() -> None:
    assert normalize_task_description("가" * 500) == "가" * 500
    with pytest.raises(InvalidTaskDescriptionError) as raised:
        normalize_task_description("가" * 501)
    assert raised.value.message == "Task 설명은 최대 500자까지 입력 가능합니다."


def test_description_with_a_nul_character_is_refused() -> None:
    with pytest.raises(InvalidTaskDescriptionError) as raised:
        normalize_task_description("설명\x00")
    assert raised.value.message == "Task 설명에 사용할 수 없는 문자가 포함되어 있습니다."


# --- error classes -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("error", "code", "message"),
    [
        (
            TaskNotFoundError(),
            "task_not_found",
            "요청한 Task를 찾을 수 없습니다. 삭제되었거나 존재하지 않는 Task입니다.",
        ),
        (TaskForbiddenError(), "task_forbidden", "이 Task에 접근할 권한이 없습니다."),
        (CodeNotFoundError(), "code_not_found", "이 Task에는 업로드된 코드가 없습니다."),
        (
            CodeFileMissingError(),
            "code_file_missing",
            "저장된 코드 파일을 찾을 수 없습니다.",
        ),
    ],
)
def test_task_errors_have_stable_codes_and_korean_messages(
    error: DomainError, code: str, message: str
) -> None:
    assert error.code == code
    assert error.message == message
