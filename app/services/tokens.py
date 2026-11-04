import hashlib
import secrets
from datetime import datetime, timedelta

from app.config import settings
from app.timeutil import utcnow


def generate_token() -> tuple[str, str, datetime]:
    """Return (raw_token, token_hash, expires_at). Only the hash is stored."""
    raw_token = secrets.token_urlsafe(32)
    token_hash = hash_token(raw_token)
    expires_at = utcnow() + timedelta(hours=settings.approval_token_ttl_hours)
    return raw_token, token_hash, expires_at


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
