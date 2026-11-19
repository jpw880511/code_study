import pytest
from src.services.auth.errors import (
    AuthError,
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    InvalidEmailError,
    WeakPasswordError,
)
from src.services.auth.user_service import normalize_email, validate_password


class TestNormalizeEmail:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("student@example.com", "student@example.com"),
            ("  Student@Example.COM  ", "student@example.com"),
            ("A.B+tag@Sub.Example.co.kr", "a.b+tag@sub.example.co.kr"),
        ],
    )
    def test_trims_and_lowercases(self, raw: str, expected: str) -> None:
        assert normalize_email(raw) == expected

    @pytest.mark.parametrize(
        "bad",
        [
            "",
            "   ",
            "not-an-email",
            "a@b",
            "@example.com",
            "a@example",
            "a b@example.com",
            "a@@x.com",
        ],
    )
    def test_rejects_malformed_addresses(self, bad: str) -> None:
        with pytest.raises(InvalidEmailError):
            normalize_email(bad)

    def test_rejects_addresses_longer_than_the_column(self) -> None:
        with pytest.raises(InvalidEmailError):
            normalize_email("a" * 250 + "@example.com")

    def test_accepts_the_longest_address_that_fits(self) -> None:
        email = "a" * 243 + "@example.com"  # exactly 255 characters
        assert len(email) == 255
        assert normalize_email(email) == email


class TestValidatePassword:
    @pytest.mark.parametrize("good", ["abcdefg1", "Passw0rd!", "비밀번호1234", "a1" * 36])
    def test_accepts_valid_passwords(self, good: str) -> None:
        validate_password(good)  # does not raise

    def test_requires_at_least_eight_characters(self) -> None:
        with pytest.raises(WeakPasswordError, match="8자 이상"):
            validate_password("abc1234")

    @pytest.mark.parametrize("bad", ["abcdefgh", "12345678", "!!!!!!!!"])
    def test_requires_both_letters_and_digits(self, bad: str) -> None:
        with pytest.raises(WeakPasswordError, match="문자와 숫자"):
            validate_password(bad)

    def test_rejects_passwords_over_the_bcrypt_limit_of_72_bytes(self) -> None:
        with pytest.raises(WeakPasswordError, match="72"):
            validate_password("a1" * 37)  # 74 bytes

    def test_counts_bytes_not_characters(self) -> None:
        with pytest.raises(WeakPasswordError, match="72"):
            validate_password("가" * 24 + "1")  # 24 Korean characters + 1 digit = 73 bytes

    def test_does_not_echo_the_password_in_the_message(self) -> None:
        with pytest.raises(WeakPasswordError) as caught:
            validate_password("short1")
        assert "short1" not in str(caught.value)


class TestAuthErrors:
    @pytest.mark.parametrize(
        ("error", "code", "message_part"),
        [
            (InvalidEmailError(), "invalid_email", "이메일 형식"),
            (WeakPasswordError(), "weak_password", "비밀번호"),
            (EmailAlreadyRegisteredError(), "email_already_registered", "이미 가입"),
            (InvalidCredentialsError(), "invalid_credentials", "이메일 또는 비밀번호"),
        ],
    )
    def test_each_error_has_a_stable_code_and_a_korean_message(
        self, error: AuthError, code: str, message_part: str
    ) -> None:
        assert isinstance(error, AuthError)
        assert error.code == code
        assert message_part in error.message
        assert str(error) == error.message

    def test_a_custom_message_replaces_the_default(self) -> None:
        assert WeakPasswordError("직접 쓴 메시지").message == "직접 쓴 메시지"

    def test_services_do_not_depend_on_the_api_layer(self) -> None:
        assert not any(base.__module__.startswith("src.api") for base in AuthError.__mro__)
