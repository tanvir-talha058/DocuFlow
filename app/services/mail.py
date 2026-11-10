"""Mail delivery provider selection. Call get_mail_client() rather than
reaching into a specific client directly, so switching providers is a
config change (MAIL_PROVIDER), not a code change."""

from typing import Protocol

from app.config import settings


class MailClient(Protocol):
    def send_mail(self, to_email: str, subject: str, html_body: str) -> None: ...


def get_mail_client() -> MailClient:
    if settings.mail_provider == "smtp":
        from app.services.smtp_client import SmtpMailClient

        return SmtpMailClient()

    from app.services.mail_fake import FakeMailClient

    return FakeMailClient()
