"""Password hashing for external customer accounts (PBKDF2-HMAC-SHA256)."""

import hashlib
import hmac
import os

_ITERATIONS = 260_000


def hash_password(plain_password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, _ITERATIONS)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(plain_password: str, stored_hash: str) -> bool:
    try:
        salt_hex, digest_hex = stored_hash.split("$", 1)
    except ValueError:
        return False
    salt = bytes.fromhex(salt_hex)
    expected = bytes.fromhex(digest_hex)
    actual = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, _ITERATIONS)
    return hmac.compare_digest(actual, expected)
