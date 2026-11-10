from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models.email_code import EmailCode
from app.models.employee import EmployeeCache
from app.services import email_codes
from app.services.password import hash_password, verify_password
from app.timeutil import utcnow


@pytest.fixture()
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
def sent_codes(monkeypatch):
    """Capture verification codes instead of emailing them: list of (email, code, purpose)."""
    sent = []

    def fake_send(*, email, code, purpose, ttl_minutes):
        sent.append((email, code, purpose))

    monkeypatch.setattr(email_codes.notifications, "send_verification_code", fake_send)
    return sent


def _signup(client, email="new.person@upaybd.com", name="New Person", password="correcthorse"):
    return client.post(
        "/auth/signup",
        data={"display_name": name, "email": email, "password": password, "confirm_password": password},
        follow_redirects=False,
    )


def _wrong(code: str) -> str:
    return f"{(int(code) + 1) % 1_000_000:06d}"


# ---------------------------------------------------------------- sign up

def test_signup_rejects_wrong_domain(client, sent_codes):
    resp = _signup(client, email="new.person@gmail.com")
    assert resp.status_code == 303
    assert "/auth/signup" in resp.headers["location"]
    assert "error" in resp.headers["location"]
    assert sent_codes == []


def test_signup_rejects_password_mismatch(client, sent_codes):
    resp = client.post(
        "/auth/signup",
        data={
            "display_name": "New Person", "email": "new.person@upaybd.com",
            "password": "correcthorse", "confirm_password": "different",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "/auth/signup" in resp.headers["location"]
    assert sent_codes == []


def test_signup_emails_code_and_creates_nothing_until_verified(client, db_session, sent_codes):
    resp = _signup(client)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/auth/verify"
    assert len(sent_codes) == 1 and sent_codes[0][0] == "new.person@upaybd.com"
    assert db_session.query(EmployeeCache).filter_by(email="new.person@upaybd.com").count() == 0

    page = client.get("/auth/verify")
    assert page.status_code == 200
    assert "n•••" in page.text  # masked email shown


def test_verify_with_correct_code_creates_employee_and_logs_in(client, db_session, sent_codes):
    _signup(client)
    code = sent_codes[-1][1]

    resp = client.post("/auth/verify", data={"code": code}, follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"

    employee = db_session.query(EmployeeCache).filter_by(email="new.person@upaybd.com").one()
    assert verify_password("correcthorse", employee.password_hash)
    assert employee.entra_object_id.startswith("local-")
    # Code is single use.
    again = client.post("/auth/verify", data={"code": code}, follow_redirects=False)
    assert again.headers["location"] == "/auth/signup"


def test_verify_wrong_code_counts_down_then_locks(client, db_session, sent_codes):
    _signup(client)
    bad = _wrong(sent_codes[-1][1])

    resp = client.post("/auth/verify", data={"code": bad}, follow_redirects=False)
    assert "4+tries+left" in resp.headers["location"]
    for _ in range(4):
        resp = client.post("/auth/verify", data={"code": bad}, follow_redirects=False)
    assert "Too+many+wrong+codes" in resp.headers["location"]

    # Even the right code no longer works once locked.
    resp = client.post("/auth/verify", data={"code": sent_codes[-1][1]}, follow_redirects=False)
    assert "error" in resp.headers["location"]
    assert db_session.query(EmployeeCache).filter_by(email="new.person@upaybd.com").count() == 0


def test_verify_expired_code_is_rejected(client, db_session, sent_codes):
    _signup(client)
    row = db_session.query(EmailCode).one()
    row.expires_at = utcnow() - timedelta(seconds=1)
    db_session.commit()

    resp = client.post("/auth/verify", data={"code": sent_codes[-1][1]}, follow_redirects=False)
    assert "expired" in resp.headers["location"]


def test_resend_blocked_during_cooldown_then_allowed(client, db_session, sent_codes):
    _signup(client)
    resp = client.post("/auth/verify/resend", follow_redirects=False)
    assert "Wait" in resp.headers["location"]
    assert len(sent_codes) == 1

    row = db_session.query(EmailCode).one()
    row.created_at = utcnow() - timedelta(minutes=2)
    db_session.commit()

    resp = client.post("/auth/verify/resend", follow_redirects=False)
    assert "notice" in resp.headers["location"]
    assert len(sent_codes) == 2
    old_code, new_code = sent_codes[0][1], sent_codes[1][1]
    if old_code != new_code:
        resp = client.post("/auth/verify", data={"code": old_code}, follow_redirects=False)
        assert "error" in resp.headers["location"]
    # The new code still carries the pending sign-up details.
    resp = client.post("/auth/verify", data={"code": new_code}, follow_redirects=False)
    assert resp.headers["location"] == "/"
    assert db_session.query(EmployeeCache).filter_by(email="new.person@upaybd.com").one().display_name == "New Person"


def test_signup_claims_existing_seeded_employee_without_password(client, db_session, employees, sent_codes):
    initiator = employees["initiator"]
    initiator.email = "initiator@upaybd.com"
    db_session.commit()
    assert initiator.password_hash is None

    _signup(client, email=initiator.email, name="Initiator Person")
    resp = client.post("/auth/verify", data={"code": sent_codes[-1][1]}, follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"

    db_session.refresh(initiator)
    assert initiator.password_hash is not None
    assert db_session.query(EmployeeCache).filter(EmployeeCache.email == initiator.email).count() == 1


def test_signup_rejects_already_registered_email(client, db_session, employees, sent_codes):
    initiator = employees["initiator"]
    initiator.email = "initiator@upaybd.com"
    initiator.password_hash = hash_password("existingpass")
    db_session.commit()

    resp = _signup(client, email=initiator.email, name="Someone Else")
    assert resp.status_code == 303
    assert "/auth/login" in resp.headers["location"]
    assert sent_codes == []


def test_verify_page_without_pending_signup_redirects(client):
    resp = client.get("/auth/verify", follow_redirects=False)
    assert resp.headers["location"] == "/auth/signup"


# ---------------------------------------------------------------- log in

def test_login_succeeds_with_correct_password(client, db_session, employees):
    initiator = employees["initiator"]
    initiator.password_hash = hash_password("correcthorse")
    db_session.commit()

    resp = client.post(
        "/auth/login",
        data={"email": initiator.email, "password": "correcthorse"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"


def test_login_fails_with_wrong_password(client, db_session, employees):
    initiator = employees["initiator"]
    initiator.password_hash = hash_password("correcthorse")
    db_session.commit()

    resp = client.post(
        "/auth/login",
        data={"email": initiator.email, "password": "wrongpassword"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "/auth/login" in resp.headers["location"]
    assert "error" in resp.headers["location"]


def test_login_page_has_password_toggle_and_forgot_link(client):
    page = client.get("/auth/login")
    assert 'data-password-toggle="password"' in page.text
    assert 'href="/auth/forgot"' in page.text


# ---------------------------------------------------------------- forgot / reset

@pytest.fixture()
def registered(db_session, employees):
    emp = employees["initiator"]
    emp.email = "initiator@upaybd.com"
    emp.password_hash = hash_password("oldpassword")
    db_session.commit()
    return emp


def test_forgot_same_response_for_unknown_email_and_sends_nothing(client, registered, sent_codes):
    known = client.post("/auth/forgot", data={"email": registered.email}, follow_redirects=False)
    unknown_client = TestClient(app)
    unknown = unknown_client.post("/auth/forgot", data={"email": "nobody@upaybd.com"}, follow_redirects=False)

    assert known.headers["location"] == unknown.headers["location"]
    assert [s[0] for s in sent_codes] == [registered.email]

    # The reset page looks the same for both (same resend countdown, no account hint).
    assert "Send a new code in" in client.get("/auth/reset").text
    assert "Send a new code in" in unknown_client.get("/auth/reset").text
    wrong = unknown_client.post(
        "/auth/reset",
        data={"code": "123456", "password": "newpassword1", "confirm_password": "newpassword1"},
        follow_redirects=False,
    )
    assert "isn%27t+right" in wrong.headers["location"]


def test_reset_changes_password(client, db_session, registered, sent_codes):
    client.post("/auth/forgot", data={"email": registered.email}, follow_redirects=False)
    code = sent_codes[-1][1]

    resp = client.post(
        "/auth/reset",
        data={"code": code, "password": "brandnewpass", "confirm_password": "brandnewpass"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"].startswith("/auth/login?success=")

    db_session.refresh(registered)
    assert verify_password("brandnewpass", registered.password_hash)
    old = client.post("/auth/login", data={"email": registered.email, "password": "oldpassword"}, follow_redirects=False)
    assert "error" in old.headers["location"]
    new = client.post("/auth/login", data={"email": registered.email, "password": "brandnewpass"}, follow_redirects=False)
    assert new.headers["location"] == "/"


def test_reset_password_mismatch_does_not_spend_attempt(client, db_session, registered, sent_codes):
    client.post("/auth/forgot", data={"email": registered.email}, follow_redirects=False)
    resp = client.post(
        "/auth/reset",
        data={"code": sent_codes[-1][1], "password": "brandnewpass", "confirm_password": "different1"},
        follow_redirects=False,
    )
    assert "match" in resp.headers["location"]
    assert db_session.query(EmailCode).one().attempts == 0
    assert db_session.query(EmailCode).one().consumed_at is None
