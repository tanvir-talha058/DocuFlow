"""Fake Graph client for local dev/tests: no network calls, no real Azure tenant.

search_users() reads from a fixed in-memory seed list (same shape Graph would
return). send_mail() appends to dev_outbox.json so you can inspect what would
have been emailed.
"""

import json
from pathlib import Path

FAKE_DIRECTORY = [
    {"id": "fake-001", "displayName": "Alice Rahman", "mail": "alice@example.com", "jobTitle": "Finance Manager", "department": "Finance"},
    {"id": "fake-002", "displayName": "Bilal Hossain", "mail": "bilal@example.com", "jobTitle": "Engineering Lead", "department": "Engineering"},
    {"id": "fake-003", "displayName": "Chitra Das", "mail": "chitra@example.com", "jobTitle": "Legal Counsel", "department": "Legal"},
    {"id": "fake-004", "displayName": "Dawood Karim", "mail": "dawood@example.com", "jobTitle": "CEO", "department": "Executive"},
]

DEV_OUTBOX_PATH = Path("dev_outbox.json")


class FakeGraphClient:
    def search_users(self, query: str) -> list[dict]:
        q = query.lower()
        return [
            u
            for u in FAKE_DIRECTORY
            if q in u["displayName"].lower() or q in u["mail"].lower()
        ]

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
