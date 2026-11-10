"""Seed EmployeeCache with a small fake directory, for local dev.

Run with: python -m scripts.seed_fake_directory
"""

from app.database import Base, SessionLocal, engine
from app.models.employee import EmployeeCache
from app.timeutil import utcnow

FAKE_DIRECTORY = [
    {"id": "fake-001", "displayName": "Alice Rahman", "mail": "alice@example.com", "jobTitle": "Finance Manager", "department": "Finance"},
    {"id": "fake-002", "displayName": "Bilal Hossain", "mail": "bilal@example.com", "jobTitle": "Engineering Lead", "department": "Engineering"},
    {"id": "fake-003", "displayName": "Chitra Das", "mail": "chitra@example.com", "jobTitle": "Legal Counsel", "department": "Legal"},
    {"id": "fake-004", "displayName": "Dawood Karim", "mail": "dawood@example.com", "jobTitle": "CEO", "department": "Executive"},
]


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
