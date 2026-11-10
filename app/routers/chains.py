from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, Form
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.audit import AuditEvent
from app.models.chain import ApprovalChain, ApprovalStep, ApproverType, ChainStatus, StepStatus
from app.models.customer import Customer
from app.models.document import Document
from app.models.employee import EmployeeCache
from app.services import activity, chain_engine, sidebar
from app.services.auth import get_current_user, get_current_user_optional
from app.services.chain_engine import ApproverSpec
from app.services.storage import get_storage
from app.templating import templates
from app.timeutil import utcnow

router = APIRouter(tags=["chains"])


@router.get("/chains/new")
def new_chain_form(
    request: Request,
    db: Session = Depends(get_db),
    current_user: EmployeeCache = Depends(get_current_user),
):
    return templates.TemplateResponse(
        "chain_new.html",
        {"request": request, "current_user": current_user, **sidebar.build_sidebar_context(db, current_user)},
    )


@router.post("/chains")
def create_chain(
    file: UploadFile,
    approver_type: list[str] = Form(...),
    approver_employee_id: list[str] = Form(...),
    approver_customer_email: list[str] = Form(...),
    approver_customer_name: list[str] = Form(...),
    title: str | None = Form(None),
    message: str | None = Form(None),
    db: Session = Depends(get_db),
    current_user: EmployeeCache = Depends(get_current_user),
):
    rows = list(zip(approver_type, approver_employee_id, approver_customer_email, approver_customer_name))
    specs: list[ApproverSpec] = []
    for a_type, employee_id, customer_email, customer_name in rows:
        if a_type == ApproverType.CUSTOMER.value:
            if not customer_email:
                continue
            specs.append(ApproverSpec(
                type=ApproverType.CUSTOMER.value,
                customer_email=customer_email.strip(),
                customer_name=customer_name.strip() or customer_email.strip(),
            ))
        else:
            if not employee_id:
                continue
            if db.get(EmployeeCache, employee_id) is None:
                raise HTTPException(status_code=400, detail=f"Unknown approver: {employee_id}")
            specs.append(ApproverSpec(type=ApproverType.EMPLOYEE.value, employee_id=employee_id))

    if not specs:
        raise HTTPException(status_code=400, detail="At least one approver is required")

    storage = get_storage()
    stored_path = storage.save(file.filename, file.file)

    document = Document(
        original_filename=file.filename,
        stored_path=stored_path,
        content_type=file.content_type or "application/octet-stream",
        size_bytes=file.size or 0,
        uploaded_by_employee_id=current_user.id,
    )
    db.add(document)
    db.flush()

    chain = chain_engine.create_chain(
        db, document=document, initiator=current_user, approvers=specs,
        title=(title or "").strip() or None,
        message=(message or "").strip() or None,
    )
    return RedirectResponse(url=f"/chains/{chain.id}", status_code=303)


@router.get("/chains/{chain_id}")
def chain_detail(
    chain_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: EmployeeCache = Depends(get_current_user),
):
    chain = db.get(ApprovalChain, chain_id)
    if chain is None:
        raise HTTPException(status_code=404, detail="Chain not found")

    document = db.get(Document, chain.document_id)
    steps = (
        db.query(ApprovalStep)
        .filter(ApprovalStep.chain_id == chain.id)
        .order_by(ApprovalStep.step_order)
        .all()
    )
    steps_with_approvers = [(s, chain_engine.resolve_approver(db, s)) for s in steps]
    step_approver_names = {s.id: approver.display_name for s, approver in steps_with_approvers}
    audit_events = (
        db.query(AuditEvent)
        .filter(AuditEvent.chain_id == chain.id)
        .order_by(AuditEvent.created_at)
        .all()
    )
    timeline = [
        {
            "event": event,
            "approver_name": step_approver_names.get(event.step_id),
            "label": activity.event_label(event.event_type),
            "tone": activity.event_tone(event.event_type),
        }
        for event in audit_events
    ]
    rejector_name = None
    if chain.rejected_by_employee_id:
        rejector = db.get(EmployeeCache, chain.rejected_by_employee_id)
        rejector_name = rejector.display_name if rejector else None
    elif chain.rejected_by_customer_id:
        rejector = db.get(Customer, chain.rejected_by_customer_id)
        rejector_name = rejector.display_name if rejector else None

    return templates.TemplateResponse(
        "chain_detail.html",
        {
            "request": request,
            "current_user": current_user,
            "chain": chain,
            "document": document,
            "steps": steps_with_approvers,
            "audit_events": audit_events,
            "timeline": timeline,
            "rejector_name": rejector_name,
            "is_initiator": chain.initiator_employee_id == current_user.id,
            "reminded": request.query_params.get("reminded"),
            "remind_error": request.query_params.get("remind_error"),
            **sidebar.build_sidebar_context(db, current_user),
        },
    )


REMINDER_COOLDOWN_MINUTES = 60


@router.post("/chains/{chain_id}/remind")
def send_reminder(
    chain_id: str,
    db: Session = Depends(get_db),
    current_user: EmployeeCache = Depends(get_current_user),
):
    """Let the chain's initiator nudge the current approver with a fresh link."""
    chain = db.get(ApprovalChain, chain_id)
    if chain is None or chain.initiator_employee_id != current_user.id:
        raise HTTPException(status_code=404, detail="Chain not found")
    if chain.status != ChainStatus.IN_PROGRESS.value:
        return RedirectResponse(
            url=f"/chains/{chain_id}?remind_error=This+chain+has+no+pending+step+to+remind", status_code=303
        )

    step = (
        db.query(ApprovalStep)
        .filter(ApprovalStep.chain_id == chain_id, ApprovalStep.step_order == chain.current_step_order)
        .one_or_none()
    )
    if step is None:
        return RedirectResponse(
            url=f"/chains/{chain_id}?remind_error=This+chain+has+no+pending+step+to+remind", status_code=303
        )

    if step.notified_at and utcnow() - step.notified_at < timedelta(minutes=REMINDER_COOLDOWN_MINUTES):
        return RedirectResponse(
            url=f"/chains/{chain_id}?remind_error=A+reminder+was+already+sent+recently.+Try+again+later.",
            status_code=303,
        )

    chain_engine.resend_reminder(db, step)
    return RedirectResponse(url=f"/chains/{chain_id}?reminded=1", status_code=303)


@router.get("/chains/{chain_id}/resume-review")
def resume_review(
    chain_id: str,
    db: Session = Depends(get_db),
    current_user: EmployeeCache = Depends(get_current_user),
):
    """Let a logged-in employee jump straight to their pending review, without
    needing their original emailed link."""
    chain = db.get(ApprovalChain, chain_id)
    if chain is None or chain.status != ChainStatus.IN_PROGRESS.value:
        raise HTTPException(status_code=404, detail="No pending review found")

    step = (
        db.query(ApprovalStep)
        .filter(
            ApprovalStep.chain_id == chain_id,
            ApprovalStep.approver_type == ApproverType.EMPLOYEE.value,
            ApprovalStep.approver_employee_id == current_user.id,
            ApprovalStep.status == StepStatus.PENDING.value,
            ApprovalStep.step_order == chain.current_step_order,
        )
        .one_or_none()
    )
    if step is None:
        raise HTTPException(status_code=404, detail="No pending review found")

    raw_token = chain_engine.reissue_token(db, step)
    return RedirectResponse(url=f"/review/{raw_token}", status_code=303)


@router.get("/documents/{document_id}/download")
def download_document(
    document_id: str,
    token: str | None = None,
    db: Session = Depends(get_db),
    current_user: EmployeeCache | None = Depends(get_current_user_optional),
):
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    chain = db.query(ApprovalChain).filter(ApprovalChain.document_id == document_id).one_or_none()

    authorized = False
    if token and chain is not None:
        step = chain_engine.get_step_by_token(db, token)
        authorized = step is not None and step.chain_id == chain.id
    if not authorized and current_user is not None and chain is not None:
        is_initiator = chain.initiator_employee_id == current_user.id
        is_approver = (
            db.query(ApprovalStep)
            .filter(
                ApprovalStep.chain_id == chain.id,
                ApprovalStep.approver_employee_id == current_user.id,
            )
            .count()
            > 0
        )
        authorized = is_initiator or is_approver
    # Customers reach a document only via their step's token (handled above);
    # there's no separate customer-session download path for v1.

    if not authorized:
        raise HTTPException(status_code=403, detail="Not authorized")

    return FileResponse(
        path=document.signed_path or document.stored_path,
        filename=document.original_filename,
        media_type=document.content_type,
    )


@router.get("/chains/{chain_id}/certificate/download")
def download_certificate(
    chain_id: str,
    token: str | None = None,
    db: Session = Depends(get_db),
    current_user: EmployeeCache | None = Depends(get_current_user_optional),
):
    chain = db.get(ApprovalChain, chain_id)
    if chain is None or not chain.certificate_path:
        raise HTTPException(status_code=404, detail="Certificate not found")

    authorized = False
    if token:
        step = chain_engine.get_step_by_token(db, token)
        authorized = step is not None and step.chain_id == chain.id
    if not authorized and current_user is not None:
        is_initiator = chain.initiator_employee_id == current_user.id
        is_approver = (
            db.query(ApprovalStep)
            .filter(
                ApprovalStep.chain_id == chain.id,
                ApprovalStep.approver_employee_id == current_user.id,
            )
            .count()
            > 0
        )
        authorized = is_initiator or is_approver

    if not authorized:
        raise HTTPException(status_code=403, detail="Not authorized")

    document = db.get(Document, chain.document_id)
    base_name = (chain.title or document.original_filename).rsplit(".", 1)[0]
    return FileResponse(
        path=chain.certificate_path,
        filename=f"{base_name} - Certificate of Completion.pdf",
        media_type="application/pdf",
    )
