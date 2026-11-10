"""Issue and check the 6-digit codes emailed for sign-up and password reset."""

import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.models.email_code import EmailCode
from app.services import notifications
from app.timeutil import utcnow

CODE_TTL = timedelta(minutes=10)
RESEND_COOLDOWN = timedelta(seconds=60)
MAX_SENDS_PER_HOUR = 5
MAX_ATTEMPTS = 5


class CodeThrottled(Exception):
    """Raised when a new code is requested too soon or too often."""

    def __init__(self, retry_after_seconds: int, message: str):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds
        self.message = message


@dataclass
class VerifyResult:
    ok: bool
    row: EmailCode | None = None
    # "wrong" | "expired" | "locked" | "missing" when not ok
    reason: str | None = None
    attempts_left: int = 0

    @property
    def payload(self) -> dict:
        if self.row is None or not self.row.payload_json:
            return {}
        return json.loads(self.row.payload_json)


def _hash(code: str) -> str:
    return hmac.new(settings.session_secret.encode(), code.encode(), hashlib.sha256).hexdigest()


def _latest(db: Session, email: str, purpose: str) -> EmailCode | None:
    return (
        db.query(EmailCode)
        .filter(EmailCode.email == email, EmailCode.purpose == purpose)
        .order_by(EmailCode.created_at.desc())
        .first()
    )


def seconds_until_resend(db: Session, email: str, purpose: str) -> int:
    latest = _latest(db, email, purpose)
    if latest is None:
        return 0
    remaining = (latest.created_at + RESEND_COOLDOWN - utcnow()).total_seconds()
    return max(0, int(remaining + 0.999))


def issue(db: Session, email: str, purpose: str, payload: dict | None = None) -> str:
    """Create a fresh code, retire older ones for this email+purpose, and email it."""
    email = email.strip().lower()
    now = utcnow()

    wait = seconds_until_resend(db, email, purpose)
    if wait > 0:
        raise CodeThrottled(wait, f"Wait {wait} seconds before asking for a new code.")
    sent_last_hour = (
        db.query(EmailCode)
        .filter(
            EmailCode.email == email,
            EmailCode.purpose == purpose,
            EmailCode.created_at > now - timedelta(hours=1),
        )
        .count()
    )
    if sent_last_hour >= MAX_SENDS_PER_HOUR:
        raise CodeThrottled(3600, "Too many codes requested. Try again in an hour.")

    db.query(EmailCode).filter(
        EmailCode.email == email,
        EmailCode.purpose == purpose,
        EmailCode.consumed_at.is_(None),
    ).update({EmailCode.consumed_at: now}, synchronize_session=False)

    # A resend keeps the pending sign-up details from the previous code.
    if payload is None:
        previous = _latest(db, email, purpose)
        if previous is not None and previous.payload_json:
            payload = json.loads(previous.payload_json)

    code = f"{secrets.randbelow(1_000_000):06d}"
    db.add(EmailCode(
        email=email,
        purpose=purpose,
        code_hash=_hash(code),
        payload_json=json.dumps(payload) if payload else None,
        expires_at=now + CODE_TTL,
        created_at=now,
    ))
    db.commit()

    notifications.send_verification_code(
        email=email, code=code, purpose=purpose, ttl_minutes=int(CODE_TTL.total_seconds() // 60),
    )
    return code


def verify(db: Session, email: str, purpose: str, code: str) -> VerifyResult:
    """Check a submitted code against the newest live one. Burns it on success or after too many misses."""
    email = email.strip().lower()
    code = "".join(ch for ch in code if ch.isdigit())
    row = _latest(db, email, purpose)
    now = utcnow()

    if row is None or row.consumed_at is not None:
        reason = "locked" if row is not None and row.attempts >= MAX_ATTEMPTS else "missing"
        return VerifyResult(ok=False, reason=reason)
    if row.expires_at < now:
        return VerifyResult(ok=False, reason="expired")

    if len(code) == 6 and hmac.compare_digest(row.code_hash, _hash(code)):
        row.consumed_at = now
        db.commit()
        return VerifyResult(ok=True, row=row)

    row.attempts += 1
    if row.attempts >= MAX_ATTEMPTS:
        row.consumed_at = now
        db.commit()
        return VerifyResult(ok=False, reason="locked")
    db.commit()
    return VerifyResult(ok=False, reason="wrong", attempts_left=MAX_ATTEMPTS - row.attempts)


def failure_message(result: VerifyResult) -> str:
    if result.reason == "wrong":
        tries = "try" if result.attempts_left == 1 else "tries"
        return f"That code isn't right. {result.attempts_left} {tries} left."
    if result.reason == "expired":
        return "This code has expired. Send a new one."
    if result.reason == "locked":
        return "Too many wrong codes. Send a new one."
    return "There's no active code for this email. Send a new one."
