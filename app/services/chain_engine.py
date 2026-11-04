from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.audit import AuditEvent, AuditEventType
from app.models.chain import ApprovalChain, ApprovalStep, ApproverType, ChainStatus, StepStatus
from app.models.customer import Customer
from app.models.document import Document
from app.models.employee import EmployeeCache
from app.models.signature import SignatureRecord
from app.services import notifications, pdf_signing
from app.services.tokens import generate_token, hash_token
from app.timeutil import utcnow as _now


@dataclass
class ApproverSpec:
    """One ordered approver, named when a chain is created."""

    type: str  # ApproverType.EMPLOYEE or ApproverType.CUSTOMER
    employee_id: str | None = None
    customer_email: str | None = None
    customer_name: str | None = None


def _audit(db: Session, *, chain_id: str, event_type: AuditEventType, step_id: str | None = None,
           actor_employee_id: str | None = None, detail: str | None = None) -> None:
    db.add(
        AuditEvent(
            chain_id=chain_id,
            step_id=step_id,
            event_type=event_type.value,
            actor_employee_id=actor_employee_id,
            detail=detail,
        )
    )


def _get_or_create_customer(db: Session, email: str, display_name: str) -> Customer:
    existing = db.query(Customer).filter(Customer.email == email).one_or_none()
    if existing:
        return existing
    customer = Customer(email=email, display_name=display_name)
    db.add(customer)
    db.flush()
    return customer


def resolve_approver(db: Session, step: ApprovalStep):
    """Return the EmployeeCache or Customer this step's approver is, regardless of type."""
    if step.approver_type == ApproverType.CUSTOMER.value:
        return db.get(Customer, step.approver_customer_id)
    return db.get(EmployeeCache, step.approver_employee_id)


def create_chain(
    db: Session, *, document: Document, initiator: EmployeeCache, approvers: list[ApproverSpec],
    title: str | None = None, message: str | None = None,
) -> ApprovalChain:
    """Create the chain + ordered steps and activate step 1 (token + email)."""
    chain = ApprovalChain(
        document_id=document.id,
        initiator_employee_id=initiator.id,
        status=ChainStatus.IN_PROGRESS.value,
        current_step_order=1,
        title=title or None,
        message=message or None,
    )
    db.add(chain)
    db.flush()

    for order, spec in enumerate(approvers, start=1):
        step = ApprovalStep(
            chain_id=chain.id,
            step_order=order,
            approver_type=spec.type,
            status=StepStatus.NOT_STARTED.value,
        )
        if spec.type == ApproverType.CUSTOMER.value:
            customer = _get_or_create_customer(db, spec.customer_email, spec.customer_name)
            step.approver_customer_id = customer.id
        else:
            step.approver_employee_id = spec.employee_id
        db.add(step)
    db.flush()

    _audit(db, chain_id=chain.id, event_type=AuditEventType.CHAIN_CREATED,
           actor_employee_id=initiator.id, detail=f"{len(approvers)} approvers")

    first_step = (
        db.query(ApprovalStep)
        .filter(ApprovalStep.chain_id == chain.id, ApprovalStep.step_order == 1)
        .one()
    )
    _activate_step(db, chain=chain, step=first_step)
    db.commit()
    return chain


def _total_steps(db: Session, chain_id: str) -> int:
    return db.query(ApprovalStep).filter(ApprovalStep.chain_id == chain_id).count()


def _refresh_token(step: ApprovalStep) -> str:
    """Mint a new token for a step and mark it the live pending step. Returns the raw token."""
    raw_token, token_hash, expires_at = generate_token()
    step.status = StepStatus.PENDING.value
    step.token_hash = token_hash
    step.token_expires_at = expires_at
    return raw_token


def _activate_step(db: Session, *, chain: ApprovalChain, step: ApprovalStep) -> None:
    raw_token = _refresh_token(step)
    step.notified_at = _now()
    db.flush()

    approver = resolve_approver(db, step)
    initiator = db.get(EmployeeCache, chain.initiator_employee_id)
    document = db.get(Document, chain.document_id)
    total = _total_steps(db, chain.id)

    _audit(db, chain_id=chain.id, step_id=step.id, event_type=AuditEventType.EMAIL_SENT,
           detail=f"notified {approver.email} for step {step.step_order}")

    notifications.send_approval_request(
        approver_email=approver.email,
        approver_name=approver.display_name,
        initiator_name=initiator.display_name,
        document_filename=document.original_filename,
        step_order=step.step_order,
        total_steps=total,
        review_token=raw_token,
        title=chain.title,
        message=chain.message,
    )


def reissue_token(db: Session, step: ApprovalStep) -> str:
    """Mint a fresh token for a step a logged-in employee already owns, so they
    can resume review in-app without their original email. No new notification,
    no new audit event — this isn't a new ask, just a fresh door to the same one."""
    raw_token = _refresh_token(step)
    db.commit()
    return raw_token


def resend_reminder(db: Session, step: ApprovalStep) -> None:
    """Nudge the current approver with a fresh link, at the sender's request."""
    raw_token = _refresh_token(step)
    step.notified_at = _now()
    db.flush()

    chain = db.get(ApprovalChain, step.chain_id)
    approver = resolve_approver(db, step)
    initiator = db.get(EmployeeCache, chain.initiator_employee_id)
    document = db.get(Document, chain.document_id)
    total = _total_steps(db, chain.id)

    _audit(db, chain_id=chain.id, step_id=step.id, event_type=AuditEventType.REMINDER_SENT,
           detail=f"reminder sent to {approver.email} for step {step.step_order}")

    notifications.send_approval_request(
        approver_email=approver.email,
        approver_name=approver.display_name,
        initiator_name=initiator.display_name,
        document_filename=document.original_filename,
        step_order=step.step_order,
        total_steps=total,
        review_token=raw_token,
        title=chain.title,
        message=chain.message,
    )
    db.commit()


def get_step_by_token(db: Session, raw_token: str) -> ApprovalStep | None:
    token_hash = hash_token(raw_token)
    return db.query(ApprovalStep).filter(ApprovalStep.token_hash == token_hash).one_or_none()


def mark_step_viewed(db: Session, step: ApprovalStep) -> None:
    """Record every time an approver opens their review page.

    Only the first call for a given step writes an audit event (so repeat
    visits don't spam the audit trail), but every call updates the running
    last-viewed timestamp and view count.
    """
    is_first_view = step.first_viewed_at is None
    now = _now()
    if is_first_view:
        step.first_viewed_at = now
    step.last_viewed_at = now
    step.view_count += 1
    db.flush()
    if is_first_view:
        _audit(db, chain_id=step.chain_id, step_id=step.id, event_type=AuditEventType.STEP_VIEWED)
    db.commit()


def is_token_valid(db: Session, step: ApprovalStep) -> bool:
    if step.status != StepStatus.PENDING.value:
        return False
    if step.token_used_at is not None:
        return False
    if step.token_expires_at is None or step.token_expires_at < _now():
        return False
    chain = db.get(ApprovalChain, step.chain_id)
    if chain.status != ChainStatus.IN_PROGRESS.value:
        return False
    if chain.current_step_order != step.step_order:
        return False
    return True


def _stamp_if_possible(db: Session, *, chain: ApprovalChain, step: ApprovalStep, signer_label: str) -> None:
    document = db.get(Document, chain.document_id)
    source_path = document.signed_path or document.stored_path
    if not pdf_signing.can_stamp(document.content_type, document.original_filename):
        return

    prior_signatures = (
        db.query(SignatureRecord)
        .join(ApprovalStep, ApprovalStep.id == SignatureRecord.step_id)
        .filter(ApprovalStep.chain_id == chain.id)
        .count()
    )
    signature = db.query(SignatureRecord).filter(SignatureRecord.step_id == step.id).one()

    output_path = str(Path(document.stored_path).with_name(f"{document.id}_signed.pdf"))
    pdf_signing.stamp_signature(
        source_path=source_path,
        output_path=output_path,
        signature_data_url=signature.image_data_url,
        signer_label=f"{signer_label}, step {step.step_order}",
        slot_index=prior_signatures,
    )
    document.signed_path = output_path
    db.flush()


def approve_step(db: Session, step: ApprovalStep, *, signature_data_url: str | None = None) -> None:
    chain = db.get(ApprovalChain, step.chain_id)
    approver = resolve_approver(db, step)

    now = _now()
    step.status = StepStatus.APPROVED.value
    step.decided_at = now
    step.approved_at = now
    step.token_used_at = now
    db.flush()

    if signature_data_url:
        db.add(SignatureRecord(step_id=step.id, image_data_url=signature_data_url))
        db.flush()
        _stamp_if_possible(db, chain=chain, step=step, signer_label=approver.display_name)

    _audit(
        db, chain_id=chain.id, step_id=step.id, event_type=AuditEventType.STEP_APPROVED,
        actor_employee_id=step.approver_employee_id,
        detail=None if step.approver_type == ApproverType.EMPLOYEE.value else f"signed by {approver.email}",
    )

    next_step = (
        db.query(ApprovalStep)
        .filter(ApprovalStep.chain_id == chain.id, ApprovalStep.step_order == step.step_order + 1)
        .one_or_none()
    )
    if next_step is not None:
        chain.current_step_order = next_step.step_order
        db.flush()
        _activate_step(db, chain=chain, step=next_step)
    else:
        chain.status = ChainStatus.APPROVED.value
        chain.current_step_order = None
        chain.completed_at = _now()
        db.flush()
        _audit(db, chain_id=chain.id, event_type=AuditEventType.CHAIN_COMPLETED)

        initiator = db.get(EmployeeCache, chain.initiator_employee_id)
        document = db.get(Document, chain.document_id)
        if initiator.notify_on_decision:
            notifications.send_completed_notice(
                initiator_email=initiator.email,
                initiator_name=initiator.display_name,
                document_filename=document.original_filename,
                total_steps=_total_steps(db, chain.id),
                chain_id=chain.id,
            )

    db.commit()


def reject_step(db: Session, step: ApprovalStep, reason: str) -> None:
    chain = db.get(ApprovalChain, step.chain_id)
    rejector = resolve_approver(db, step)

    now = _now()
    step.status = StepStatus.REJECTED.value
    step.decided_at = now
    step.rejected_at = now
    step.token_used_at = now
    step.decision_reason = reason
    db.flush()

    chain.status = ChainStatus.REJECTED.value
    chain.rejected_reason = reason
    if step.approver_type == ApproverType.CUSTOMER.value:
        chain.rejected_by_customer_id = step.approver_customer_id
    else:
        chain.rejected_by_employee_id = step.approver_employee_id
    chain.current_step_order = None
    db.flush()

    _audit(db, chain_id=chain.id, step_id=step.id, event_type=AuditEventType.STEP_REJECTED,
           actor_employee_id=step.approver_employee_id, detail=reason)
    _audit(db, chain_id=chain.id, event_type=AuditEventType.CHAIN_REJECTED, detail=reason)

    initiator = db.get(EmployeeCache, chain.initiator_employee_id)
    document = db.get(Document, chain.document_id)
    if initiator.notify_on_decision:
        notifications.send_rejected_notice(
            initiator_email=initiator.email,
            initiator_name=initiator.display_name,
            document_filename=document.original_filename,
            rejector_name=rejector.display_name,
            step_order=step.step_order,
            reason=reason,
            chain_id=chain.id,
        )

    db.commit()
