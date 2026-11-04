"""Initiator authentication.

Employees sign up and log in with a work email (restricted to
`settings.allowed_email_domain`) and a password — see `app/routers/auth.py`.
This stands in for a future Azure AD/Entra SSO integration, behind the same
`get_current_user` dependency shape, so swapping it in later doesn't change
any route that depends on `get_current_user`.
"""

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.employee import EmployeeCache

SESSION_USER_KEY = "employee_id"


def get_current_user(request: Request, db: Session = Depends(get_db)) -> EmployeeCache:
    employee_id = request.session.get(SESSION_USER_KEY)
    if not employee_id:
        raise HTTPException(status_code=401, detail="Not logged in")
    employee = db.get(EmployeeCache, employee_id)
    if employee is None:
        raise HTTPException(status_code=401, detail="Not logged in")
    return employee


def get_current_user_optional(
    request: Request, db: Session = Depends(get_db)
) -> EmployeeCache | None:
    employee_id = request.session.get(SESSION_USER_KEY)
    if not employee_id:
        return None
    return db.get(EmployeeCache, employee_id)
