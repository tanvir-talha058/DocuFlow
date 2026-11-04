import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.employee import EmployeeCache
from app.services.auth import SESSION_USER_KEY
from app.services.password import hash_password, verify_password
from app.templating import templates

router = APIRouter(prefix="/auth", tags=["auth"])


def _domain_ok(email: str) -> bool:
    return email.lower().endswith(f"@{settings.allowed_email_domain.lower()}")


@router.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "current_user": None, "error": request.query_params.get("error")},
    )


@router.post("/login")
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    employee = (
        db.query(EmployeeCache).filter(EmployeeCache.email == email.strip().lower()).one_or_none()
    )
    if employee is None or employee.password_hash is None or not verify_password(password, employee.password_hash):
        return RedirectResponse(url="/auth/login?error=Incorrect+email+or+password", status_code=303)

    request.session[SESSION_USER_KEY] = employee.id
    return RedirectResponse(url="/", status_code=303)


@router.get("/signup")
def signup_page(request: Request):
    return templates.TemplateResponse(
        "signup.html",
        {
            "request": request, "current_user": None,
            "error": request.query_params.get("error"),
            "domain": settings.allowed_email_domain,
        },
    )


@router.post("/signup")
def signup(
    request: Request,
    display_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
):
    clean_name = display_name.strip()
    clean_email = email.strip().lower()

    if not clean_name:
        return RedirectResponse(url="/auth/signup?error=Name+is+required", status_code=303)
    if not _domain_ok(clean_email):
        return RedirectResponse(
            url=f"/auth/signup?error=Use+your+%40{settings.allowed_email_domain}+work+email",
            status_code=303,
        )
    if len(password) < 8 or password != confirm_password:
        return RedirectResponse(
            url="/auth/signup?error=Passwords+must+match+and+be+at+least+8+characters",
            status_code=303,
        )

    employee = db.query(EmployeeCache).filter(EmployeeCache.email == clean_email).one_or_none()
    if employee is not None and employee.password_hash is not None:
        return RedirectResponse(
            url="/auth/login?error=An+account+with+this+email+already+exists.+Log+in+instead.",
            status_code=303,
        )

    if employee is None:
        employee = EmployeeCache(
            entra_object_id=f"local-{uuid.uuid4()}",
            display_name=clean_name,
            email=clean_email,
        )
        db.add(employee)
    else:
        # A seeded/pre-existing directory record with no password yet — claim it.
        employee.display_name = clean_name

    employee.password_hash = hash_password(password)
    db.commit()

    request.session[SESSION_USER_KEY] = employee.id
    return RedirectResponse(url="/", status_code=303)


@router.get("/callback")
def callback():
    # Phase 2: handle MSAL authorization-code redirect here.
    raise HTTPException(status_code=501, detail="Real Azure AD login not configured yet")


@router.get("/logout")
def logout(request: Request):
    request.session.pop(SESSION_USER_KEY, None)
    return RedirectResponse(url="/auth/login", status_code=303)
