"""Seed EmployeeCache with the fake directory used by FakeGraphClient, for local dev.

Run with: python -m scripts.seed_fake_directory
"""

from app.database import Base, SessionLocal, engine
from app.models.employee import EmployeeCache
from app.services.graph_client_fake import FAKE_DIRECTORY
from app.timeutil import utcnow


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        now = utcnow()
        for u in FAKE_DIRECTORY:
            existing = db.query(EmployeeCache).filter(EmployeeCache.email == u["mail"]).one_or_none()
            if existing:
                continue
            db.add(
                EmployeeCache(
                    entra_object_id=u["id"],
                    display_name=u["displayName"],
                    email=u["mail"],
                    job_title=u.get("jobTitle"),
                    department=u.get("department"),
                    last_synced_at=now,
                )
            )
        db.commit()
        print(f"Seeded {len(FAKE_DIRECTORY)} fake employees.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
