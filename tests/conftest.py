import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
import app.models  # noqa: F401  (import side effect: registers all models)
from app.models.document import Document
from app.models.employee import EmployeeCache


@pytest.fixture()
def db_session():
    # StaticPool keeps every connection (including the worker thread FastAPI's
    # TestClient runs sync routes on) pointed at the same :memory: database —
    # without it each thread gets its own empty SQLite :memory: database.
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def employees(db_session):
    initiator = EmployeeCache(
        entra_object_id="e-initiator", display_name="Initiator Person", email="initiator@example.com"
    )
    approver1 = EmployeeCache(
        entra_object_id="e-approver1", display_name="Approver One", email="approver1@example.com"
    )
    approver2 = EmployeeCache(
        entra_object_id="e-approver2", display_name="Approver Two", email="approver2@example.com"
    )
    db_session.add_all([initiator, approver1, approver2])
    db_session.commit()
    return {"initiator": initiator, "approver1": approver1, "approver2": approver2}


@pytest.fixture()
def document(db_session, employees):
    doc = Document(
        original_filename="test.txt",
        stored_path="/tmp/test.txt",
        content_type="text/plain",
        size_bytes=10,
        uploaded_by_employee_id=employees["initiator"].id,
    )
    db_session.add(doc)
    db_session.commit()
    return doc


@pytest.fixture(autouse=True)
def fake_mail(monkeypatch):
    """Use a tmp outbox path isolated per test run to avoid cross-test pollution."""
    import pathlib

    import app.services.mail_fake as fake_module

    monkeypatch.setattr(fake_module, "DEV_OUTBOX_PATH", pathlib.Path("test_dev_outbox.json"))
    yield
    fake_module.DEV_OUTBOX_PATH.unlink(missing_ok=True)
