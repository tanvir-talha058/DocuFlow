import uuid
from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.timeutil import utcnow


def _uuid() -> str:
    return str(uuid.uuid4())


class Customer(Base):
    """An external signer, outside the org's Entra ID directory.

    Created (with no password) the moment an initiator names them as an
    approver; they set their password via the emailed review link the first
    time they open it, then log in with it on later visits.
    """

    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
