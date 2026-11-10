import time
import uuid
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.email_code import EmailCodePurpose
from app.models.employee import EmployeeCache
from app.services import email_codes
from app.services.auth import SESSION_USER_KEY
from app.services.password import hash_password, verify_password
from app.templating import templates

router = APIRouter(prefix="/auth", tags=["auth"])

PENDING_EMAIL_KEY = "pending_email"
PENDING_PURPOSE_KEY = "pending_purpose"
PENDING_SENT_AT_KEY = "pending_sent_at"


def _domain_ok(email: str) -> bool:
    return email.lower().endswith(f"@{settings.allowed_email_domain.lower()}")


def _redirect(path: str, **params: str) -> RedirectResponse:
    query = "&".join(f"{k}={quote_plus(v)}" for k, v in params.items() if v)
    return RedirectResponse(url=f"{path}?{query}" if query else path, status_code=303)


def _mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    return f"{local[:1]}{'•' * max(len(local) - 1, 3)}@{domain}"


def _password_problem(password: str, confirm_password: str) -> str | None:
    if len(password) < 8:
        return "Passwords must be at least 8 characters."
    if password != confirm_password:
        return "Passwords don't match."
    return None


def _start_pending(request: Request, email: str, purpose: str) -> None:
    request.session[PENDING_EMAIL_KEY] = email
    request.session[PENDING_PURPOSE_KEY] = purpose
    _mark_sent(request)


def _mark_sent(request: Request) -> None:
    request.session[PENDING_SENT_AT_KEY] = time.time()


def _session_resend_wait(request: Request) -> int:
    """Resend countdown from the session, identical whether or not the email has an account."""
    sent_at = request.session.get(PENDING_SENT_AT_KEY) or 0
    cooldown = email_codes.RESEND_COOLDOWN.total_seconds()
    return max(0, int(cooldown - (time.time() - sent_at) + 0.999))


def _pending_email(request: Request, purpose: str) -> str | None:
    if request.session.get(PENDING_PURPOSE_KEY) != purpose:
        return None
    return request.session.get(PENDING_EMAIL_KEY)


def _clear_pending(request: Request) -> None:
    request.session.pop(PENDING_EMAIL_KEY, None)
    request.session.pop(PENDING_PURPOSE_KEY, None)
    request.session.pop(PENDING_SENT_AT_KEY, None)


def _code_page_context(request: Request, email: str) -> dict:
    return {
        "request": request, "current_user": None,
        "masked_email": _mask_email(email),
        "resend_wait": _session_resend_wait(request),
        "error": request.query_params.get("error"),
        "notice": request.query_params.get("notice"),
    }


# ---------------------------------------------------------------- log in

@router.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request, "current_user": None,
            "error": request.query_params.get("error"),
            "success": request.query_params.get("success"),
        },
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
        return _redirect("/auth/login", error="Incorrect email or password")

    request.session[SESSION_USER_KEY] = employee.id
    return RedirectResponse(url="/", status_code=303)


# ---------------------------------------------------------------- sign up + email code

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
        return _redirect("/auth/signup", error="Name is required")
    if not _domain_ok(clean_email):
        return _redirect("/auth/signup", error=f"Use your @{settings.allowed_email_domain} work email")
    problem = _password_problem(password, confirm_password)
    if problem:
        return _redirect("/auth/signup", error=problem)

    employee = db.query(EmployeeCache).filter(EmployeeCache.email == clean_email).one_or_none()
    if employee is not None and employee.password_hash is not None:
        return _redirect("/auth/login", error="An account with this email already exists. Log in instead.")

    # No account yet: it's created only once the emailed code is confirmed.
    _start_pending(request, clean_email, EmailCodePurpose.SIGNUP)
    try:
        email_codes.issue(
            db, clean_email, EmailCodePurpose.SIGNUP,
            payload={"display_name": clean_name, "password_hash": hash_password(password)},
        )
    except email_codes.CodeThrottled as exc:
        return _redirect("/auth/verify", error=exc.message)
    return RedirectResponse(url="/auth/verify", status_code=303)


@router.get("/verify")
def verify_page(request: Request, db: Session = Depends(get_db)):
    email = _pending_email(request, EmailCodePurpose.SIGNUP)
    if email is None:
        return RedirectResponse(url="/auth/signup", status_code=303)
    return templates.TemplateResponse(
        "verify_email.html", _code_page_context(request, email),
    )


@router.post("/verify")
def verify_submit(request: Request, code: str = Form(...), db: Session = Depends(get_db)):
    email = _pending_email(request, EmailCodePurpose.SIGNUP)
    if email is None:
        return RedirectResponse(url="/auth/signup", status_code=303)

    result = email_codes.verify(db, email, EmailCodePurpose.SIGNUP, code)
    if not result.ok:
        return _redirect("/auth/verify", error=email_codes.failure_message(result))

    payload = result.payload
    employee = db.query(EmployeeCache).filter(EmployeeCache.email == email).one_or_none()
    if employee is not None and employee.password_hash is not None:
        _clear_pending(request)
        return _redirect("/auth/login", error="An account with this email already exists. Log in instead.")

    if employee is None:
        employee = EmployeeCache(
            entra_object_id=f"local-{uuid.uuid4()}",
            display_name=payload["display_name"],
            email=email,
        )
        db.add(employee)
    else:
        # A seeded/pre-existing directory record with no password yet — claim it.
        employee.display_name = payload["display_name"]

    employee.password_hash = payload["password_hash"]
    db.commit()

    _clear_pending(request)
    request.session[SESSION_USER_KEY] = employee.id
    return RedirectResponse(url="/", status_code=303)


@router.post("/verify/resend")
def verify_resend(request: Request, db: Session = Depends(get_db)):
    email = _pending_email(request, EmailCodePurpose.SIGNUP)
    if email is None:
        return RedirectResponse(url="/auth/signup", status_code=303)
    try:
        email_codes.issue(db, email, EmailCodePurpose.SIGNUP)
    except email_codes.CodeThrottled as exc:
        return _redirect("/auth/verify", error=exc.message)
    _mark_sent(request)
    return _redirect("/auth/verify", notice="We sent a new code. Earlier codes no longer work.")


# ---------------------------------------------------------------- forgot / reset password

_RESET_SENT = "If an account exists for that email, we've sent a 6-digit code to it."


def _send_reset_code_if_account(db: Session, email: str) -> None:
    """Silently does nothing for unknown emails so the form can't reveal who has an account."""
    employee = db.query(EmployeeCache).filter(EmployeeCache.email == email).one_or_none()
    if employee is None or employee.password_hash is None:
        return
    try:
        email_codes.issue(db, email, EmailCodePurpose.RESET)
    except email_codes.CodeThrottled:
        pass


@router.get("/forgot")
def forgot_page(request: Request):
    return templates.TemplateResponse(
        "forgot_password.html",
        {"request": request, "current_user": None, "error": request.query_params.get("error")},
    )


@router.post("/forgot")
def forgot_submit(request: Request, email: str = Form(...), db: Session = Depends(get_db)):
    clean_email = email.strip().lower()
    if "@" not in clean_email:
        return _redirect("/auth/forgot", error="Enter the email you log in with.")
    _send_reset_code_if_account(db, clean_email)
    _start_pending(request, clean_email, EmailCodePurpose.RESET)
    return _redirect("/auth/reset", notice=_RESET_SENT)


@router.get("/reset")
def reset_page(request: Request, db: Session = Depends(get_db)):
    email = _pending_email(request, EmailCodePurpose.RESET)
    if email is None:
        return RedirectResponse(url="/auth/forgot", status_code=303)
    return templates.TemplateResponse(
        "reset_password.html", _code_page_context(request, email),
    )


@router.post("/reset")
def reset_submit(
    request: Request,
    code: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
):
    email = _pending_email(request, EmailCodePurpose.RESET)
    if email is None:
        return RedirectResponse(url="/auth/forgot", status_code=303)

    # Check the new password first so a typo doesn't spend a code attempt.
    problem = _password_problem(password, confirm_password)
    if problem:
        return _redirect("/auth/reset", error=problem)

    result = email_codes.verify(db, email, EmailCodePurpose.RESET, code)
    if not result.ok:
        # "missing" would reveal that no account exists for this email.
        if result.reason == "missing":
            result.reason, result.attempts_left = "wrong", email_codes.MAX_ATTEMPTS - 1
        return _redirect("/auth/reset", error=email_codes.failure_message(result))

    employee = db.query(EmployeeCache).filter(EmployeeCache.email == email).one_or_none()
    if employee is None:
        _clear_pending(request)
        return _redirect("/auth/forgot", error="We couldn't reset that account. Try again.")

    employee.password_hash = hash_password(password)
    db.commit()
    _clear_pending(request)
    request.session.pop(SESSION_USER_KEY, None)
    return _redirect("/auth/login", success="Password updated. Log in with your new password.")


@router.post("/reset/resend")
def reset_resend(request: Request, db: Session = Depends(get_db)):
    email = _pending_email(request, EmailCodePurpose.RESET)
    if email is None:
        return RedirectResponse(url="/auth/forgot", status_code=303)
    wait = _session_resend_wait(request)
    if wait > 0:
        return _redirect("/auth/reset", error=f"Wait {wait} seconds before asking for a new code.")
    _send_reset_code_if_account(db, email)
    _mark_sent(request)
    return _redirect("/auth/reset", notice="If an account exists, we've sent a new code. Earlier codes no longer work.")


@router.get("/logout")
def logout(request: Request):
    request.session.pop(SESSION_USER_KEY, None)
    return RedirectResponse(url="/auth/login", status_code=303)
