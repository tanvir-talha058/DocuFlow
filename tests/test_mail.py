from app.config import settings
from app.services.mail import get_mail_client


def test_default_provider_is_fake_graph_client():
    assert settings.mail_provider == "fake"
    from app.services.graph_client_fake import FakeGraphClient

    assert isinstance(get_mail_client(), FakeGraphClient)


def test_smtp_provider_selects_smtp_client(monkeypatch):
    monkeypatch.setattr(settings, "mail_provider", "smtp")
    from app.services.smtp_client import SmtpMailClient

    assert isinstance(get_mail_client(), SmtpMailClient)


def test_smtp_client_sends_via_starttls_with_login(monkeypatch):
    import app.services.smtp_client as smtp_module

    sent = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout=None):
            sent["host"] = host
            sent["port"] = port

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def starttls(self):
            sent["starttls"] = True

        def login(self, username, password):
            sent["login"] = (username, password)

        def send_message(self, msg):
            sent["subject"] = msg["Subject"]
            sent["to"] = msg["To"]
            sent["from"] = msg["From"]

    monkeypatch.setattr(smtp_module.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "smtp_port", 587)
    monkeypatch.setattr(settings, "smtp_use_ssl", False)
    monkeypatch.setattr(settings, "smtp_use_tls", True)
    monkeypatch.setattr(settings, "smtp_username", "bot@example.com")
    monkeypatch.setattr(settings, "smtp_password", "secret")
    monkeypatch.setattr(settings, "smtp_from_email", "notifications@example.com")
    monkeypatch.setattr(settings, "smtp_from_name", "DocuFlow")

    smtp_module.SmtpMailClient().send_mail(
        to_email="approver@example.com", subject="Action needed", html_body="<p>Hi</p>"
    )

    assert sent["host"] == "smtp.example.com"
    assert sent["starttls"] is True
    assert sent["login"] == ("bot@example.com", "secret")
    assert sent["to"] == "approver@example.com"
    assert sent["subject"] == "Action needed"
    assert sent["from"] == "DocuFlow <notifications@example.com>"
