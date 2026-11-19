import pytest
from src.utils.security import (
    BCRYPT_ROUNDS,
    MAX_PASSWORD_BYTES,
    hash_password,
    hash_refresh_token,
    verify_password,
)

PASSWORD = "correct horse battery staple"


def test_cost_factor_is_12() -> None:
    assert BCRYPT_ROUNDS == 12


def test_hash_is_bcrypt_with_cost_12_and_not_plaintext() -> None:
    hashed = hash_password(PASSWORD)
    assert hashed.startswith("$2b$12$")
    assert PASSWORD not in hashed
    assert len(hashed) == 60


def test_same_password_gets_different_hashes() -> None:
    assert hash_password(PASSWORD) != hash_password(PASSWORD)


def test_verify_accepts_correct_password() -> None:
    assert verify_password(PASSWORD, hash_password(PASSWORD)) is True


@pytest.mark.parametrize("wrong", ["wrong", PASSWORD.upper(), PASSWORD + " ", ""])
def test_verify_rejects_wrong_password(wrong: str) -> None:
    assert verify_password(wrong, hash_password(PASSWORD)) is False


def test_unicode_password_round_trip() -> None:
    password = "비밀번호-パスワード-🔑"
    assert verify_password(password, hash_password(password)) is True


@pytest.mark.parametrize("bad_hash", ["", "not-a-hash", "$2b$12$tooshort", "plaintext-password"])
def test_verify_returns_false_for_malformed_hash(bad_hash: str) -> None:
    assert verify_password(PASSWORD, bad_hash) is False


def test_empty_password_cannot_be_hashed() -> None:
    with pytest.raises(ValueError, match="empty"):
        hash_password("")


def test_password_over_bcrypt_limit_is_refused() -> None:
    too_long = "a" * (MAX_PASSWORD_BYTES + 1)
    with pytest.raises(ValueError, match="72"):
        hash_password(too_long)


def test_password_at_limit_is_accepted() -> None:
    at_limit = "a" * MAX_PASSWORD_BYTES
    assert verify_password(at_limit, hash_password(at_limit)) is True


def test_limit_counts_bytes_not_characters() -> None:
    korean = "가" * 25  # 75 bytes in UTF-8
    with pytest.raises(ValueError, match="72"):
        hash_password(korean)


def test_verify_returns_false_for_overlong_password() -> None:
    hashed = hash_password(PASSWORD)
    assert verify_password("a" * (MAX_PASSWORD_BYTES + 1), hashed) is False


def test_refresh_token_hash_is_the_sha256_hex_digest() -> None:
    # Well-known SHA-256 test vector for "abc".
    assert (
        hash_refresh_token("abc")
        == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )


def test_refresh_token_hash_is_deterministic_and_fits_the_column() -> None:
    token = "some.refresh.token"
    assert hash_refresh_token(token) == hash_refresh_token(token)
    assert len(hash_refresh_token(token)) == 64
    assert hash_refresh_token(token) != hash_refresh_token(token + "x")


def test_refresh_token_hash_never_contains_the_token() -> None:
    assert "secret-token" not in hash_refresh_token("secret-token")
