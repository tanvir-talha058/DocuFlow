import uuid
from datetime import datetime

from app.timeutil import utcnow

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())



class EmployeeCache(Base):
    """Local mirror of an Entra ID (Azure AD) user, refreshed on search/login."""

    __tablename__ = "employee_cache"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    entra_object_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    job_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    department: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    # User-editable preferences (Settings page), not synced from Entra.
    theme_preference: Mapped[str] = mapped_column(String(10), default="system", server_default="system")
    notify_on_decision: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")

    # Local email+password account, used until real Azure AD/Entra SSO is
    # wired up. Null until the employee signs up.
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
