"""Import the employee directory from an Excel roster into EmployeeCache.

Expects a sheet with columns "Employee Name", "Email", "Designation" (extra
columns are ignored). Rows without an email are skipped, since email is the
unique key used for approver search, login, and notifications.

Upserts by email, so re-running after the roster changes is safe: existing
employees get their name/title refreshed, new rows get added, nothing is
duplicated or deleted.

Run with: python -m scripts.import_employees_from_excel [path/to/employees.xlsx]
"""

import sys

import openpyxl

from app.database import Base, SessionLocal, engine
from app.models.employee import EmployeeCache
from app.timeutil import utcnow

DEFAULT_PATH = "employees.xlsx"


def _entra_object_id_for(email: str) -> str:
    """A stable fake id for rows that don't have a real Azure AD object id yet."""
    return f"xlsx:{email.lower()}"


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PATH

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.worksheets[0]
    rows = list(ws.iter_rows(min_row=2, values_only=True))

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        now = utcnow()
        created, updated, skipped = 0, 0, []

        for i, row in enumerate(rows, start=2):
            name = (row[0] or "").strip() if row and row[0] else ""
            email = (row[1] or "").strip().lower() if len(row) > 1 and row[1] else ""
            job_title = (row[2] or "").strip() if len(row) > 2 and row[2] else None

            if not name:
                continue  # blank row
            if not email:
                skipped.append(f"row {i}: {name!r} has no email")
                continue

            existing = db.query(EmployeeCache).filter(EmployeeCache.email == email).one_or_none()
            if existing:
                existing.display_name = name
                existing.job_title = job_title
                existing.last_synced_at = now
                updated += 1
            else:
                db.add(
                    EmployeeCache(
                        entra_object_id=_entra_object_id_for(email),
                        display_name=name,
                        email=email,
                        job_title=job_title,
                        last_synced_at=now,
                    )
                )
                created += 1

        db.commit()
        print(f"Imported {created} new employee(s), updated {updated} existing.")
        if skipped:
            print(f"Skipped {len(skipped)} row(s) with no email:")
            for line in skipped:
                print(f"  - {line}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
