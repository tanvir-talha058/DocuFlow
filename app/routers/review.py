from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.chain import ApprovalChain, ApprovalStep, ApproverType
from app.models.customer import Customer
from app.models.document import Document
from app.models.employee import EmployeeCache
from app.services import chain_engine
from app.services.customer_auth import get_logged_in_customer, log_in_customer
from app.services.password import hash_password, verify_password
from app.templating import templates

router = APIRouter(prefix="/review", tags=["review"])


def _invalid_page(request: Request):
    return templates.TemplateResponse(
        "review_invalid.html", {"request": request, "current_user": None}
    )


def _chain_context(db: Session, step):
    chain = db.get(ApprovalChain, step.chain_id)
    document = db.get(Document, chain.document_id)
    initiator = db.get(EmployeeCache, chain.initiator_employee_id)
    return chain, document, initiator


_PREVIEWABLE_PREFIXES = ("image/",)
_PREVIEWABLE_TYPES = {"application/pdf"}


def _review_extras(db: Session, chain: ApprovalChain, step: ApprovalStep, document: Document) -> dict:
    """Context the interactive review page needs: the step tracker, who's next, and preview support."""
    steps = (
        db.query(ApprovalStep)
        .filter(ApprovalStep.chain_id == chain.id)
        .order_by(ApprovalStep.step_order)
        .all()
    )
    overview = []
    for s in steps:
        who = chain_engine.resolve_approver(db, s)
        overview.append({
            "order": s.step_order,
            "name": who.display_name if who else "Unknown",
            "status": s.status,
            "is_you": s.id == step.id,
        })
    next_step = next((o for o in overview if o["order"] > step.step_order), None)
    content_type = (document.content_type or "").lower()
    return {
        "steps_overview": overview,
        "next_approver_name": next_step["name"] if next_step else None,
        "can_preview": content_type in _PREVIEWABLE_TYPES or content_type.startswith(_PREVIEWABLE_PREFIXES),
        "is_image": content_type.startswith("image/"),
    }


@router.get("/{token}")
def review_page(token: str, request: Request, db: Session = Depends(get_db), error: str | None = None):
    step = chain_engine.get_step_by_token(db, token)
    if step is None or not chain_engine.is_token_valid(db, step):
        return _invalid_page(request)

    chain, document, initiator = _chain_context(db, step)

    if step.approver_type == ApproverType.EMPLOYEE.value:
        chain_engine.mark_step_viewed(db, step)
        return templates.TemplateResponse(
            "review.html",
            {
                "request": request, "current_user": None, "step": step,
                "document": document, "initiator": initiator, "token": token, "chain": chain,
                "error": error, **_review_extras(db, chain, step, document),
            },
        )

    # Customer step: gate behind account setup / login before showing the document.
    customer = db.get(Customer, step.approver_customer_id)
    if customer.password_hash is None:
        return templates.TemplateResponse(
            "customer_setup.html",
            {
                "request": request, "current_user": None, "token": token, "customer": customer,
                "error": error, "document": document, "initiator": initiator,
            },
        )

    logged_in = get_logged_in_customer(request, db)
    if logged_in is None or logged_in.id != customer.id:
        return templates.TemplateResponse(
            "customer_login.html",
            {
                "request": request, "current_user": None, "token": token, "customer": customer,
                "error": error, "document": document, "initiator": initiator,
            },
        )

    chain_engine.mark_step_viewed(db, step)
    return templates.TemplateResponse(
        "review_sign.html",
        {
            "request": request, "current_user": None, "step": step,
            "document": document, "initiator": initiator, "token": token, "customer": customer,
            "chain": chain, "error": error, **_review_extras(db, chain, step, document),
        },
    )


@router.post("/{token}/customer-setup")
def customer_setup(
    token: str, request: Request, password: str = Form(...), confirm_password: str = Form(...),
    db: Session = Depends(get_db),
):
    step = chain_engine.get_step_by_token(db, token)
    if step is None or not chain_engine.is_token_valid(db, step) or step.approver_type != ApproverType.CUSTOMER.value:
        return _invalid_page(request)

    customer = db.get(Customer, step.approver_customer_id)
    if customer.password_hash is not None:
        return RedirectResponse(url=f"/review/{token}", status_code=303)
    if len(password) < 8 or password != confirm_password:
        return RedirectResponse(
            url=f"/review/{token}?error=Passwords+must+match+and+be+at+least+8+characters",
            status_code=303,
        )

    customer.password_hash = hash_password(password)
    db.commit()
    log_in_customer(request, customer)
    return RedirectResponse(url=f"/review/{token}", status_code=303)


@router.post("/{token}/customer-login")
def customer_login(
    token: str, request: Request, password: str = Form(...), db: Session = Depends(get_db)
):
    step = chain_engine.get_step_by_token(db, token)
    if step is None or not chain_engine.is_token_valid(db, step) or step.approver_type != ApproverType.CUSTOMER.value:
        return _invalid_page(request)

    customer = db.get(Customer, step.approver_customer_id)
    if customer.password_hash is None or not verify_password(password, customer.password_hash):
        return RedirectResponse(url=f"/review/{token}?error=Incorrect+password", status_code=303)

    log_in_customer(request, customer)
    return RedirectResponse(url=f"/review/{token}", status_code=303)


def _require_matching_customer(request: Request, step, db: Session) -> bool:
    if step.approver_type != ApproverType.CUSTOMER.value:
        return True
    customer = get_logged_in_customer(request, db)
    return customer is not None and customer.id == step.approver_customer_id


@router.post("/{token}/approve")
def approve(
    token: str, request: Request, db: Session = Depends(get_db),
    signature_data_url: str | None = Form(None),
):
    step = chain_engine.get_step_by_token(db, token)
    if step is None or not chain_engine.is_token_valid(db, step):
        return _invalid_page(request)
    if not _require_matching_customer(request, step, db):
        return _invalid_page(request)
    if step.approver_type == ApproverType.CUSTOMER.value and not signature_data_url:
        return RedirectResponse(url=f"/review/{token}?error=Please+sign+before+approving", status_code=303)

    chain_engine.approve_step(db, step, signature_data_url=signature_data_url)
    return RedirectResponse(url=f"/review/{token}/done", status_code=303)


@router.post("/{token}/reject")
def reject(token: str, request: Request, reason: str = Form(...), db: Session = Depends(get_db)):
    step = chain_engine.get_step_by_token(db, token)
    if step is None or not chain_engine.is_token_valid(db, step):
        return _invalid_page(request)
    if not _require_matching_customer(request, step, db):
        return _invalid_page(request)

    chain_engine.reject_step(db, step, reason)
    return RedirectResponse(url=f"/review/{token}/done", status_code=303)


@router.get("/{token}/done")
def done(token: str, request: Request, db: Session = Depends(get_db)):
    step = chain_engine.get_step_by_token(db, token)
    if step is None:
        return _invalid_page(request)
    chain = db.get(ApprovalChain, step.chain_id)
    return templates.TemplateResponse(
        "review_done.html",
        {"request": request, "current_user": None, "step": step, "chain_complete": chain.status != "IN_PROGRESS"},
    )
