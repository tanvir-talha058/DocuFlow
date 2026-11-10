"""Fake mail client for local dev/tests: no network calls, no real mail
server. send_mail() appends to dev_outbox.json so you can inspect what would
have been emailed. Selected via MAIL_PROVIDER=fake (the default)."""

import json
from pathlib import Path

DEV_OUTBOX_PATH = Path("dev_outbox.json")


class FakeMailClient:
    def send_mail(self, to_email: str, subject: str, html_body: str) -> None:
        entry = {"to": to_email, "subject": subject, "html_body": html_body}
        outbox = []
        if DEV_OUTBOX_PATH.exists():
            try:
                outbox = json.loads(DEV_OUTBOX_PATH.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                outbox = []
        outbox.append(entry)
        DEV_OUTBOX_PATH.write_text(json.dumps(outbox, indent=2), encoding="utf-8")
