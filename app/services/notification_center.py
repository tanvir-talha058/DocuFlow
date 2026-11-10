"""In-app notifications (bell icon), independent of the emails sent for the
same events (see app.services.notifications). Call notify() at the same
points chain_engine already sends an email, so the two stay in sync."""

from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.timeutil import utcnow


def notify(
    db: Session, *, employee_id: str, type: str, title: str,
    body: str | None = None, link: str | None = None, chain_id: str | None = None,
) -> None:
    db.add(
        Notification(
            employee_id=employee_id, chain_id=chain_id, type=type,
            title=title, body=body, link=link,
        )
    )


def unread_count(db: Session, employee_id: str) -> int:
    return (
        db.query(Notification)
        .filter(Notification.employee_id == employee_id, Notification.read_at.is_(None))
        .count()
    )


def list_recent(db: Session, employee_id: str, limit: int = 8) -> list[Notification]:
    return (
        db.query(Notification)
        .filter(Notification.employee_id == employee_id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
        .all()
    )


def mark_read(db: Session, employee_id: str, notification_id: str) -> None:
    notification = db.get(Notification, notification_id)
    if notification is not None and notification.employee_id == employee_id and notification.read_at is None:
        notification.read_at = utcnow()
        db.commit()


def mark_all_read(db: Session, employee_id: str) -> None:
    db.query(Notification).filter(
        Notification.employee_id == employee_id, Notification.read_at.is_(None)
    ).update({"read_at": utcnow()})
    db.commit()
