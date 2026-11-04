"""Mail delivery provider selection, independent of the Graph directory
lookup (app.services.directory / graph_client.search_users). Notifications
should call get_mail_client() rather than reaching into graph_client
directly, so switching providers is a config change, not a code change."""

from typing import Protocol

from app.config import settings


class MailClient(Protocol):
    def send_mail(self, to_email: str, subject: str, html_body: str) -> None: ...


def get_mail_client() -> MailClient:
    provider = settings.mail_provider

    if provider == "smtp":
        from app.services.smtp_client import SmtpMailClient

        return SmtpMailClient()

    if provider == "graph":
        from app.services.graph_client import GraphClient

        return GraphClient()

    from app.services.graph_client_fake import FakeGraphClient

    return FakeGraphClient()
