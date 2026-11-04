"""Microsoft Graph client wrapper.

Isolates all calls to Microsoft Graph so the rest of the app depends on a
small interface (search_users, send_mail) rather than Graph/MSAL details.
`FakeGraphClient` (graph_client_fake.py) implements the same interface for
local dev/tests without a real Azure tenant.
"""

from typing import Protocol

import httpx
import msal

from app.config import settings

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"


class EmployeeRecord(Protocol):
    entra_object_id: str
    display_name: str
    email: str
    job_title: str | None
    department: str | None


class GraphClient:
    """Real Microsoft Graph client using app-only (client credentials) auth."""

    def __init__(self):
        self._app = msal.ConfidentialClientApplication(
            client_id=settings.azure_client_id,
            client_credential=settings.azure_client_secret,
            authority=f"https://login.microsoftonline.com/{settings.azure_tenant_id}",
        )

    def _get_app_token(self) -> str:
        result = self._app.acquire_token_for_client(
            scopes=["https://graph.microsoft.com/.default"]
        )
        if "access_token" not in result:
            raise RuntimeError(f"Failed to acquire Graph token: {result.get('error_description')}")
        return result["access_token"]

    def search_users(self, query: str) -> list[dict]:
        token = self._get_app_token()
        headers = {"Authorization": f"Bearer {token}"}
        filter_expr = (
            f"startswith(displayName,'{query}') or startswith(mail,'{query}')"
        )
        params = {
            "$filter": filter_expr,
            "$select": "id,displayName,mail,jobTitle,department",
            "$top": "10",
        }
        resp = httpx.get(f"{GRAPH_BASE_URL}/users", headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json().get("value", [])

    def send_mail(self, to_email: str, subject: str, html_body: str) -> None:
        token = self._get_app_token()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        payload = {
            "message": {
                "subject": subject,
                "body": {"contentType": "HTML", "content": html_body},
                "toRecipients": [{"emailAddress": {"address": to_email}}],
            },
            "saveToSentItems": "true",
        }
        mailbox = settings.notifications_mailbox
        resp = httpx.post(
            f"{GRAPH_BASE_URL}/users/{mailbox}/sendMail",
            headers=headers,
            json=payload,
            timeout=10,
        )
        resp.raise_for_status()


def get_graph_client():
    if settings.use_fake_graph:
        from app.services.graph_client_fake import FakeGraphClient

        return FakeGraphClient()
    return GraphClient()
