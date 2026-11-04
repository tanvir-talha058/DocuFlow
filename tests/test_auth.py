import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models.employee import EmployeeCache
from app.services.password import hash_password


@pytest.fixture()
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


def test_signup_rejects_wrong_domain(client):
    resp = client.post(
        "/auth/signup",
        data={
            "display_name": "New Person", "email": "new.person@gmail.com",
            "password": "correcthorse", "confirm_password": "correcthorse",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "/auth/signup" in resp.headers["location"]
    assert "error" in resp.headers["location"]


def test_signup_rejects_password_mismatch(client):
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


def test_signup_creates_new_employee_and_logs_in(client, db_session):
    resp = client.post(
        "/auth/signup",
        data={
            "display_name": "New Person", "email": "new.person@upaybd.com",
            "password": "correcthorse", "confirm_password": "correcthorse",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"

    employee = (
        db_session.query(EmployeeCache)
        .filter(EmployeeCache.email == "new.person@upaybd.com")
        .one()
    )
    assert employee.password_hash is not None
    assert employee.entra_object_id.startswith("local-")


def test_signup_claims_existing_seeded_employee_without_password(client, db_session, employees):
    initiator = employees["initiator"]
    initiator.email = "initiator@upaybd.com"
    db_session.commit()
    assert initiator.password_hash is None

    resp = client.post(
        "/auth/signup",
        data={
            "display_name": "Initiator Person", "email": initiator.email,
            "password": "correcthorse", "confirm_password": "correcthorse",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"

    db_session.refresh(initiator)
    assert initiator.password_hash is not None
    # No duplicate row was created for the same email.
    assert (
        db_session.query(EmployeeCache).filter(EmployeeCache.email == initiator.email).count() == 1
    )


def test_signup_rejects_already_registered_email(client, db_session, employees):
    initiator = employees["initiator"]
    initiator.email = "initiator@upaybd.com"
    initiator.password_hash = hash_password("existingpass")
    db_session.commit()

    resp = client.post(
        "/auth/signup",
        data={
            "display_name": "Someone Else", "email": initiator.email,
            "password": "correcthorse", "confirm_password": "correcthorse",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "/auth/login" in resp.headers["location"]


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
