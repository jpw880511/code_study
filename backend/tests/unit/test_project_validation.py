import pytest
from src.services.project_errors import InvalidProjectDescriptionError, InvalidProjectTitleError
from src.services.project_service import (
    MAX_DESCRIPTION_LENGTH,
    MAX_TITLE_LENGTH,
    normalize_description,
    normalize_title,
)

TITLE_TOO_SHORT = "프로젝트 제목은 최소 1자 이상이어야 합니다."
TITLE_TOO_LONG = "프로젝트 제목은 최대 255자까지 입력 가능합니다."
DESCRIPTION_TOO_LONG = "프로젝트 설명은 최대 2000자까지 입력 가능합니다."


def test_limits() -> None:
    assert MAX_TITLE_LENGTH == 255
    assert MAX_DESCRIPTION_LENGTH == 2000


def test_title_is_trimmed() -> None:
    assert normalize_title("  내 프로젝트 \n") == "내 프로젝트"


def test_inner_whitespace_is_kept() -> None:
    assert normalize_title("a  b") == "a  b"


@pytest.mark.parametrize("title", ["", " ", "\t\n  ", "　"])
def test_empty_or_blank_title_is_refused(title: str) -> None:
    with pytest.raises(InvalidProjectTitleError) as caught:
        normalize_title(title)
    assert caught.value.message == TITLE_TOO_SHORT


def test_none_title_is_refused() -> None:
    with pytest.raises(InvalidProjectTitleError) as caught:
        normalize_title(None)
    assert caught.value.message == TITLE_TOO_SHORT


def test_title_of_255_characters_is_allowed_and_256_is_not() -> None:
    assert normalize_title("가" * 255) == "가" * 255
    with pytest.raises(InvalidProjectTitleError) as caught:
        normalize_title("가" * 256)
    assert caught.value.message == TITLE_TOO_LONG


def test_length_is_checked_after_trimming() -> None:
    assert normalize_title(" " + "a" * 255 + " ") == "a" * 255


def test_title_with_a_nul_character_is_refused() -> None:
    with pytest.raises(InvalidProjectTitleError):
        normalize_title("bad\x00title")


def test_description_is_trimmed() -> None:
    assert normalize_description("  설명\n") == "설명"


@pytest.mark.parametrize("description", [None, "", "   ", "\n\t"])
def test_empty_description_becomes_none(description: str | None) -> None:
    assert normalize_description(description) is None


def test_description_of_2000_characters_is_allowed_and_2001_is_not() -> None:
    assert normalize_description("a" * 2000) == "a" * 2000
    with pytest.raises(InvalidProjectDescriptionError) as caught:
        normalize_description("a" * 2001)
    assert caught.value.message == DESCRIPTION_TOO_LONG


def test_description_length_is_checked_after_trimming() -> None:
    assert normalize_description(" " + "a" * 2000 + " ") == "a" * 2000


def test_description_with_a_nul_character_is_refused() -> None:
    with pytest.raises(InvalidProjectDescriptionError):
        normalize_description("bad\x00text")
