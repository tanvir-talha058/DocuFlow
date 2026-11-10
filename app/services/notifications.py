from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import settings
from app.services.mail import get_mail_client

# Autoescape matters here: chain titles, messages and rejection reasons are
# user-supplied and get interpolated straight into the email HTML.
_env = Environment(
    loader=FileSystemLoader("app/templates/emails"),
    autoescape=select_autoescape(["html"]),
)


def _render(template_name: str, **context) -> str:
    context.setdefault("server_url", settings.base_url.rstrip("/"))
    return _env.get_template(template_name).render(**context)


def send_approval_request(
    *, approver_email: str, approver_name: str, initiator_name: str,
    document_filename: str, step_order: int, total_steps: int, review_token: str,
    title: str | None = None, message: str | None = None, chain_id: str | None = None,
) -> None:
    review_url = f"{settings.base_url}/review/{review_token}"
    chain_url = f"{settings.base_url}/chains/{chain_id}" if chain_id else f"{settings.base_url}/"
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
        chain_url=chain_url,
        ttl_hours=settings.approval_token_ttl_hours,
    )
    get_mail_client().send_mail(
        to_email=approver_email,
        subject=f"Action required: please review \"{display_title}\"",
        html_body=html,
    )


def send_rejected_notice(
    *, initiator_email: str, initiator_name: str, document_filename: str,
    rejector_name: str, step_order: int, reason: str, chain_id: str,
    title: str | None = None,
) -> None:
    chain_url = f"{settings.base_url}/chains/{chain_id}"
    display_title = title or document_filename
    html = _render(
        "rejected_notice.html",
        initiator_name=initiator_name,
        document_filename=document_filename,
        display_title=display_title,
        rejector_name=rejector_name,
        step_order=step_order,
        reason=reason,
        chain_url=chain_url,
    )
    get_mail_client().send_mail(
        to_email=initiator_email,
        subject=f"Rejected: \"{display_title}\"",
        html_body=html,
    )


def send_verification_code(*, email: str, code: str, purpose: str, ttl_minutes: int) -> None:
    html = _render(
        "verification_code.html", email=email, code=code, purpose=purpose, ttl_minutes=ttl_minutes,
    )
    subject = (
        f"{code} is your DocuFlow password reset code" if purpose == "reset"
        else f"{code} is your DocuFlow verification code"
    )
    get_mail_client().send_mail(to_email=email, subject=subject, html_body=html)


def send_completed_notice(
    *, initiator_email: str, initiator_name: str, document_filename: str,
    total_steps: int, chain_id: str, title: str | None = None,
) -> None:
    chain_url = f"{settings.base_url}/chains/{chain_id}"
    display_title = title or document_filename
    html = _render(
        "completed_notice.html",
        initiator_name=initiator_name,
        document_filename=document_filename,
        display_title=display_title,
        total_steps=total_steps,
        chain_url=chain_url,
    )
    get_mail_client().send_mail(
        to_email=initiator_email,
        subject=f"Approved: \"{display_title}\"",
        html_body=html,
    )
