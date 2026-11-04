import enum
import uuid
from datetime import datetime

from app.timeutil import utcnow

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())



class AuditEventType(str, enum.Enum):
    CHAIN_CREATED = "CHAIN_CREATED"
    EMAIL_SENT = "EMAIL_SENT"
    STEP_APPROVED = "STEP_APPROVED"
    STEP_REJECTED = "STEP_REJECTED"
    STEP_VIEWED = "STEP_VIEWED"
    REMINDER_SENT = "REMINDER_SENT"
    CHAIN_COMPLETED = "CHAIN_COMPLETED"
    CHAIN_REJECTED = "CHAIN_REJECTED"
    TOKEN_INVALIDATED = "TOKEN_INVALIDATED"


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    chain_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("approval_chains.id"), index=True
    )
    step_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("approval_steps.id"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(30))
    actor_employee_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("employee_cache.id"), nullable=True
    )
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
