from app.models.audit import AuditEvent, AuditEventType
from app.models.chain import ApprovalChain, ApprovalStep, ApproverType, ChainStatus, StepStatus
from app.services import chain_engine
from app.services.chain_engine import ApproverSpec


def test_create_chain_activates_only_first_step(db_session, employees, document):
    chain = chain_engine.create_chain(
        db_session,
        document=document,
        initiator=employees["initiator"],
        approvers=[ApproverSpec(type=ApproverType.EMPLOYEE.value, employee_id=employees["approver1"].id), ApproverSpec(type=ApproverType.EMPLOYEE.value, employee_id=employees["approver2"].id)],
    )

    steps = (
        db_session.query(ApprovalStep)
        .filter(ApprovalStep.chain_id == chain.id)
        .order_by(ApprovalStep.step_order)
        .all()
    )
    assert steps[0].status == StepStatus.PENDING.value
    assert steps[0].token_hash is not None
    assert steps[1].status == StepStatus.NOT_STARTED.value
    assert steps[1].token_hash is None
    assert chain.current_step_order == 1


def test_approve_advances_to_next_step(db_session, employees, document):
    chain = chain_engine.create_chain(
        db_session,
        document=document,
        initiator=employees["initiator"],
        approvers=[ApproverSpec(type=ApproverType.EMPLOYEE.value, employee_id=employees["approver1"].id), ApproverSpec(type=ApproverType.EMPLOYEE.value, employee_id=employees["approver2"].id)],
    )
    step1 = (
        db_session.query(ApprovalStep)
        .filter(ApprovalStep.chain_id == chain.id, ApprovalStep.step_order == 1)
        .one()
    )
    chain_engine.approve_step(db_session, step1)

    db_session.refresh(chain)
    step2 = (
        db_session.query(ApprovalStep)
        .filter(ApprovalStep.chain_id == chain.id, ApprovalStep.step_order == 2)
        .one()
    )
    assert step1.status == StepStatus.APPROVED.value
    assert step1.approved_at is not None
    assert step1.rejected_at is None
    assert step2.status == StepStatus.PENDING.value
    assert step2.token_hash is not None
    assert chain.current_step_order == 2
    assert chain.status == ChainStatus.IN_PROGRESS.value


def test_approving_last_step_completes_chain(db_session, employees, document):
    chain = chain_engine.create_chain(
        db_session,
        document=document,
        initiator=employees["initiator"],
        approvers=[ApproverSpec(type=ApproverType.EMPLOYEE.value, employee_id=employees["approver1"].id)],
    )
    step1 = (
        db_session.query(ApprovalStep)
        .filter(ApprovalStep.chain_id == chain.id, ApprovalStep.step_order == 1)
        .one()
    )
    chain_engine.approve_step(db_session, step1)

    db_session.refresh(chain)
    assert chain.status == ChainStatus.APPROVED.value
    assert chain.current_step_order is None
    assert chain.completed_at is not None


def test_reject_halts_chain_and_leaves_later_steps_untouched(db_session, employees, document):
    chain = chain_engine.create_chain(
        db_session,
        document=document,
        initiator=employees["initiator"],
        approvers=[ApproverSpec(type=ApproverType.EMPLOYEE.value, employee_id=employees["approver1"].id), ApproverSpec(type=ApproverType.EMPLOYEE.value, employee_id=employees["approver2"].id)],
    )
    step1 = (
        db_session.query(ApprovalStep)
        .filter(ApprovalStep.chain_id == chain.id, ApprovalStep.step_order == 1)
        .one()
    )
    chain_engine.reject_step(db_session, step1, "not acceptable")

    db_session.refresh(chain)
    step2 = (
        db_session.query(ApprovalStep)
        .filter(ApprovalStep.chain_id == chain.id, ApprovalStep.step_order == 2)
        .one()
    )
    assert chain.status == ChainStatus.REJECTED.value
    assert chain.rejected_reason == "not acceptable"
    assert chain.rejected_by_employee_id == employees["approver1"].id
    assert step1.rejected_at is not None
    assert step1.approved_at is None
    assert step2.status == StepStatus.NOT_STARTED.value
    assert step2.token_hash is None


def test_token_invalid_after_use(db_session, employees, document):
    chain = chain_engine.create_chain(
        db_session,
        document=document,
        initiator=employees["initiator"],
        approvers=[ApproverSpec(type=ApproverType.EMPLOYEE.value, employee_id=employees["approver1"].id)],
    )
    step1 = (
        db_session.query(ApprovalStep)
        .filter(ApprovalStep.chain_id == chain.id, ApprovalStep.step_order == 1)
        .one()
    )
    assert chain_engine.is_token_valid(db_session, step1)

    chain_engine.approve_step(db_session, step1)
    db_session.refresh(step1)
    assert not chain_engine.is_token_valid(db_session, step1)


def test_out_of_order_token_invalid(db_session, employees, document):
    """A valid-looking step whose chain has already moved past it must be rejected."""
    chain = chain_engine.create_chain(
        db_session,
        document=document,
        initiator=employees["initiator"],
        approvers=[ApproverSpec(type=ApproverType.EMPLOYEE.value, employee_id=employees["approver1"].id), ApproverSpec(type=ApproverType.EMPLOYEE.value, employee_id=employees["approver2"].id)],
    )
    step1 = (
        db_session.query(ApprovalStep)
        .filter(ApprovalStep.chain_id == chain.id, ApprovalStep.step_order == 1)
        .one()
    )
    # Manually force chain forward without going through step1, simulating a stale link.
    chain.current_step_order = 2
    db_session.commit()

    assert not chain_engine.is_token_valid(db_session, step1)


def test_create_chain_stores_title_and_message(db_session, employees, document):
    chain = chain_engine.create_chain(
        db_session,
        document=document,
        initiator=employees["initiator"],
        approvers=[ApproverSpec(type=ApproverType.EMPLOYEE.value, employee_id=employees["approver1"].id)],
        title="Q3 Vendor Agreement",
        message="Please review before Friday.",
    )
    assert chain.title == "Q3 Vendor Agreement"
    assert chain.message == "Please review before Friday."


def test_create_chain_without_title_or_message_leaves_them_none(db_session, employees, document):
    chain = chain_engine.create_chain(
        db_session,
        document=document,
        initiator=employees["initiator"],
        approvers=[ApproverSpec(type=ApproverType.EMPLOYEE.value, employee_id=employees["approver1"].id)],
    )
    assert chain.title is None
    assert chain.message is None


def test_mark_step_viewed_sets_timestamp_once(db_session, employees, document):
    chain = chain_engine.create_chain(
        db_session,
        document=document,
        initiator=employees["initiator"],
        approvers=[ApproverSpec(type=ApproverType.EMPLOYEE.value, employee_id=employees["approver1"].id)],
    )
    step1 = (
        db_session.query(ApprovalStep)
        .filter(ApprovalStep.chain_id == chain.id, ApprovalStep.step_order == 1)
        .one()
    )
    assert step1.first_viewed_at is None

    chain_engine.mark_step_viewed(db_session, step1)
    db_session.refresh(step1)
    first_seen = step1.first_viewed_at
    assert first_seen is not None
    assert step1.last_viewed_at == first_seen
    assert step1.view_count == 1

    viewed_events = (
        db_session.query(AuditEvent)
        .filter(AuditEvent.step_id == step1.id, AuditEvent.event_type == AuditEventType.STEP_VIEWED.value)
        .all()
    )
    assert len(viewed_events) == 1

    # Calling it again must not move first_viewed_at or write a second audit
    # event, but should still bump the repeat-view count.
    chain_engine.mark_step_viewed(db_session, step1)
    db_session.refresh(step1)
    assert step1.first_viewed_at == first_seen
    assert step1.view_count == 2
    viewed_events = (
        db_session.query(AuditEvent)
        .filter(AuditEvent.step_id == step1.id, AuditEvent.event_type == AuditEventType.STEP_VIEWED.value)
        .all()
    )
    assert len(viewed_events) == 1


def test_reissue_token_mints_fresh_token_without_new_email_or_audit_event(db_session, employees, document):
    chain = chain_engine.create_chain(
        db_session,
        document=document,
        initiator=employees["initiator"],
        approvers=[ApproverSpec(type=ApproverType.EMPLOYEE.value, employee_id=employees["approver1"].id)],
    )
    step1 = (
        db_session.query(ApprovalStep)
        .filter(ApprovalStep.chain_id == chain.id, ApprovalStep.step_order == 1)
        .one()
    )
    original_hash = step1.token_hash
    email_events_before = (
        db_session.query(AuditEvent)
        .filter(AuditEvent.chain_id == chain.id, AuditEvent.event_type == AuditEventType.EMAIL_SENT.value)
        .count()
    )

    new_raw_token = chain_engine.reissue_token(db_session, step1)

    db_session.refresh(step1)
    assert step1.token_hash != original_hash
    assert step1.status == StepStatus.PENDING.value
    assert chain_engine.get_step_by_token(db_session, new_raw_token).id == step1.id

    email_events_after = (
        db_session.query(AuditEvent)
        .filter(AuditEvent.chain_id == chain.id, AuditEvent.event_type == AuditEventType.EMAIL_SENT.value)
        .count()
    )
    assert email_events_after == email_events_before  # no new notification for an in-app resume


def test_resend_reminder_mints_token_and_logs_audit_event(db_session, employees, document):
    chain = chain_engine.create_chain(
        db_session,
        document=document,
        initiator=employees["initiator"],
        approvers=[ApproverSpec(type=ApproverType.EMPLOYEE.value, employee_id=employees["approver1"].id)],
    )
    step1 = (
        db_session.query(ApprovalStep)
        .filter(ApprovalStep.chain_id == chain.id, ApprovalStep.step_order == 1)
        .one()
    )
    original_hash = step1.token_hash

    chain_engine.resend_reminder(db_session, step1)

    db_session.refresh(step1)
    assert step1.token_hash != original_hash
    reminder_events = (
        db_session.query(AuditEvent)
        .filter(
            AuditEvent.chain_id == chain.id,
            AuditEvent.event_type == AuditEventType.REMINDER_SENT.value,
            AuditEvent.detail.like("reminder%"),
        )
        .all()
    )
    assert len(reminder_events) == 1
