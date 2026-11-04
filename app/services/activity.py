"""Shared display mapping for AuditEventType, used by the chain detail
timeline and the dashboard's recent-activity feed."""

EVENT_TONE = {
    "CHAIN_CREATED": "neutral",
    "EMAIL_SENT": "sent",
    "REMINDER_SENT": "sent",
    "STEP_VIEWED": "seen",
    "STEP_APPROVED": "approved",
    "STEP_REJECTED": "rejected",
    "CHAIN_COMPLETED": "approved",
    "CHAIN_REJECTED": "rejected",
    "TOKEN_INVALIDATED": "neutral",
}

EVENT_LABEL = {
    "CHAIN_CREATED": "Chain created",
    "EMAIL_SENT": "Sent",
    "REMINDER_SENT": "Reminder sent",
    "STEP_VIEWED": "Opened",
    "STEP_APPROVED": "Approved",
    "STEP_REJECTED": "Rejected",
    "CHAIN_COMPLETED": "Completed",
    "CHAIN_REJECTED": "Chain rejected",
    "TOKEN_INVALIDATED": "Link invalidated",
}


def event_label(event_type: str) -> str:
    return EVENT_LABEL.get(event_type, event_type.replace("_", " ").title())


def event_tone(event_type: str) -> str:
    return EVENT_TONE.get(event_type, "neutral")
