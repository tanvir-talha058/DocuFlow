import uuid
from datetime import datetime

from app.timeutil import utcnow

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())



class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    original_filename: Mapped[str] = mapped_column(String(500))
    stored_path: Mapped[str] = mapped_column(String(1000))
    content_type: Mapped[str] = mapped_column(String(255))
    size_bytes: Mapped[int] = mapped_column(Integer)
    uploaded_by_employee_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("employee_cache.id")
    )
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    # Progressively re-stamped copy, updated each time a step signs a PDF.
    # Null until the first signature; downloads prefer this over stored_path.
    signed_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
