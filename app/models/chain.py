import enum
import uuid
from datetime import datetime

from app.timeutil import utcnow

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())



class ChainStatus(str, enum.Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class StepStatus(str, enum.Enum):
    NOT_STARTED = "NOT_STARTED"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ApproverType(str, enum.Enum):
    EMPLOYEE = "EMPLOYEE"
    CUSTOMER = "CUSTOMER"


class ApprovalChain(Base):
    __tablename__ = "approval_chains"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id"))
    initiator_employee_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("employee_cache.id")
    )
    status: Mapped[str] = mapped_column(String(20), default=ChainStatus.PENDING.value)
    current_step_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    message: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rejected_reason: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    rejected_by_employee_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("employee_cache.id"), nullable=True
    )
    rejected_by_customer_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("customers.id"), nullable=True
    )


class ApprovalStep(Base):
    __tablename__ = "approval_steps"
    __table_args__ = (UniqueConstraint("chain_id", "step_order"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    chain_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("approval_chains.id"), index=True
    )
    step_order: Mapped[int] = mapped_column(Integer)
    approver_type: Mapped[str] = mapped_column(String(10), default=ApproverType.EMPLOYEE.value)
    approver_employee_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("employee_cache.id"), nullable=True
    )
    approver_customer_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("customers.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default=StepStatus.NOT_STARTED.value)
    token_hash: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    token_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    first_viewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_viewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    view_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(String(2000), nullable=True)
