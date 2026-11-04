"""Plain SMTP mail delivery — an alternative to Microsoft Graph's sendMail
for orgs that just want to point at an SMTP relay (Office 365 SMTP AUTH,
Gmail/Workspace SMTP, SendGrid/Mailgun SMTP, an internal relay, etc.).
Selected via MAIL_PROVIDER=smtp; stdlib only, no extra dependency."""

import smtplib
from email.message import EmailMessage

from app.config import settings


class SmtpMailClient:
    def send_mail(self, to_email: str, subject: str, html_body: str) -> None:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = (
            f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
            if settings.smtp_from_name else settings.smtp_from_email
        )
        msg["To"] = to_email
        msg.set_content("This message requires an HTML-capable email client.")
        msg.add_alternative(html_body, subtype="html")

        if settings.smtp_use_ssl:
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15) as server:
                self._login_and_send(server, msg)
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
                if settings.smtp_use_tls:
                    server.starttls()
                self._login_and_send(server, msg)

    @staticmethod
    def _login_and_send(server: smtplib.SMTP, msg: EmailMessage) -> None:
        if settings.smtp_username:
            server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(msg)
