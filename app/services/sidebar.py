"""Data the new app-shell sidebar/topbar needs on every authenticated
employee page (not just the dashboard): the pending-approvals badge count
and the storage meter. Kept cheap — small aggregate queries only."""
from sqlalchemy.orm import Session

from app.config import settings
from app.models.chain import ApprovalChain, ApprovalStep, ApproverType, ChainStatus, StepStatus
from app.models.document import Document
from app.models.employee import EmployeeCache
from app.services import notification_center


def build_sidebar_context(db: Session, current_user: EmployeeCache) -> dict:
    pending_approvals_count = (
        db.query(ApprovalStep)
        .join(ApprovalChain, ApprovalChain.id == ApprovalStep.chain_id)
        .filter(
            ApprovalStep.approver_type == ApproverType.EMPLOYEE.value,
            ApprovalStep.approver_employee_id == current_user.id,
            ApprovalStep.status == StepStatus.PENDING.value,
            ApprovalChain.status == ChainStatus.IN_PROGRESS.value,
            ApprovalChain.current_step_order == ApprovalStep.step_order,
        )
        .count()
    )

    notifications_preview = notification_center.list_recent(db, current_user.id, limit=6)
    unread_notifications_count = notification_center.unread_count(db, current_user.id)

    sizes = (
        db.query(Document.size_bytes)
        .filter(Document.uploaded_by_employee_id == current_user.id)
        .all()
    )
    total_bytes = sum(row[0] for row in sizes)
    quota = settings.storage_quota_bytes
    storage_pct = min(100, round(total_bytes / quota * 100)) if quota else 0

    return {
        "pending_approvals_count": pending_approvals_count,
        "notifications_preview": notifications_preview,
        "unread_notifications_count": unread_notifications_count,
        "storage_used_bytes": total_bytes,
        "storage_quota_bytes": quota,
        "storage_pct": storage_pct,
    }
