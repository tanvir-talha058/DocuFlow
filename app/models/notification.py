import enum
import uuid
from datetime import datetime

from app.timeutil import utcnow

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class NotificationType(str, enum.Enum):
    APPROVAL_REQUESTED = "APPROVAL_REQUESTED"
    CHAIN_APPROVED = "CHAIN_APPROVED"
    CHAIN_REJECTED = "CHAIN_REJECTED"


class Notification(Base):
    """In-app notification for an employee, independent of the email sent
    for the same event (see app.services.notifications)."""

    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    employee_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("employee_cache.id"), index=True
    )
    chain_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("approval_chains.id"), nullable=True
    )
    type: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str | None] = mapped_column(String(500), nullable=True)
    link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
