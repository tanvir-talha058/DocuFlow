from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.employee import EmployeeCache
from app.models.notification import Notification
from app.services import notification_center, sidebar
from app.services.auth import get_current_user
from app.templating import templates

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
def notifications_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: EmployeeCache = Depends(get_current_user),
):
    items = (
        db.query(Notification)
        .filter(Notification.employee_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(50)
        .all()
    )
    return templates.TemplateResponse(
        "notifications.html",
        {
            "request": request, "current_user": current_user, "items": items,
            **sidebar.build_sidebar_context(db, current_user),
        },
    )


@router.post("/mark-all-read")
def mark_all_read(
    request: Request,
    db: Session = Depends(get_db),
    current_user: EmployeeCache = Depends(get_current_user),
):
    notification_center.mark_all_read(db, current_user.id)
    next_url = request.query_params.get("next") or "/notifications"
    return RedirectResponse(url=next_url, status_code=303)


@router.get("/{notification_id}/open")
def open_notification(
    notification_id: str,
    db: Session = Depends(get_db),
    current_user: EmployeeCache = Depends(get_current_user),
):
    """Mark a notification read, then send the user on to whatever it links to."""
    notification = db.get(Notification, notification_id)
    if notification is None or notification.employee_id != current_user.id:
        raise HTTPException(status_code=404, detail="Notification not found")

    notification_center.mark_read(db, current_user.id, notification_id)
    return RedirectResponse(url=notification.link or "/", status_code=303)
