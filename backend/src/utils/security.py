import hashlib

import bcrypt

BCRYPT_ROUNDS = 12
MAX_PASSWORD_BYTES = 72  # bcrypt ignores (or rejects) anything beyond 72 bytes


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("Password must not be empty")
    encoded = password.encode("utf-8")
    if len(encoded) > MAX_PASSWORD_BYTES:
        raise ValueError(f"Password must be at most {MAX_PASSWORD_BYTES} bytes in UTF-8")
    return bcrypt.hashpw(encoded, bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    encoded = password.encode("utf-8")
    if not encoded or len(encoded) > MAX_PASSWORD_BYTES:
        return False
    try:
        return bcrypt.checkpw(encoded, password_hash.encode("utf-8"))
    except ValueError:
        return False


def hash_refresh_token(token: str) -> str:
    """SHA-256 hex digest stored in refresh_tokens.token_hash; the token itself is never stored."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
