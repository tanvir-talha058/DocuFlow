import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.timeutil import utcnow


def _uuid() -> str:
    return str(uuid.uuid4())


class EmailCodePurpose:
    SIGNUP = "signup"
    RESET = "reset"


class EmailCode(Base):
    """A short-lived 6-digit code emailed to prove someone owns an inbox.

    Used for first-time sign-up (the account is only created once the code is
    verified; the pending name + password hash wait in `payload_json`) and for
    password resets. Only an HMAC of the code is stored.
    """

    __tablename__ = "email_codes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), index=True)
    purpose: Mapped[str] = mapped_column(String(10))
    code_hash: Mapped[str] = mapped_column(String(64))
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
