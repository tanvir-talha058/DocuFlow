from jinja2 import Environment, FileSystemLoader

from app.config import settings
from app.services.mail import get_mail_client

_env = Environment(loader=FileSystemLoader("app/templates/emails"))


def _render(template_name: str, **context) -> str:
    return _env.get_template(template_name).render(**context)


def send_approval_request(
    *, approver_email: str, approver_name: str, initiator_name: str,
    document_filename: str, step_order: int, total_steps: int, review_token: str,
    title: str | None = None, message: str | None = None,
) -> None:
    review_url = f"{settings.base_url}/review/{review_token}"
    display_title = title or document_filename
    html = _render(
        "approval_request.html",
        approver_name=approver_name,
        initiator_name=initiator_name,
        document_filename=document_filename,
        display_title=display_title,
        message=message,
        step_order=step_order,
        total_steps=total_steps,
        review_url=review_url,
        ttl_hours=settings.approval_token_ttl_hours,
    )
    get_mail_client().send_mail(
        to_email=approver_email,
        subject=f"Action needed: review \"{display_title}\"",
        html_body=html,
    )


def send_rejected_notice(
    *, initiator_email: str, initiator_name: str, document_filename: str,
    rejector_name: str, step_order: int, reason: str, chain_id: str,
) -> None:
    chain_url = f"{settings.base_url}/chains/{chain_id}"
    html = _render(
        "rejected_notice.html",
        initiator_name=initiator_name,
        document_filename=document_filename,
        rejector_name=rejector_name,
        step_order=step_order,
        reason=reason,
        chain_url=chain_url,
    )
    get_mail_client().send_mail(
        to_email=initiator_email,
        subject=f"Rejected: \"{document_filename}\"",
        html_body=html,
    )


def send_completed_notice(
    *, initiator_email: str, initiator_name: str, document_filename: str,
    total_steps: int, chain_id: str,
) -> None:
    chain_url = f"{settings.base_url}/chains/{chain_id}"
    html = _render(
        "completed_notice.html",
        initiator_name=initiator_name,
        document_filename=document_filename,
        total_steps=total_steps,
        chain_url=chain_url,
    )
    get_mail_client().send_mail(
        to_email=initiator_email,
        subject=f"Approved: \"{document_filename}\"",
        html_body=html,
    )
