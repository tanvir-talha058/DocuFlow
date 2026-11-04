import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.timeutil import utcnow


def _uuid() -> str:
    return str(uuid.uuid4())


class SignatureRecord(Base):
    """The captured signature image for one ApprovalStep's approval."""

    __tablename__ = "signature_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    step_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("approval_steps.id"), unique=True, index=True
    )
    image_data_url: Mapped[str] = mapped_column(Text)
    signed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
