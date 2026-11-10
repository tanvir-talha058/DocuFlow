from sqlalchemy.orm import Session

from app.models.employee import EmployeeCache


def search_employees(db: Session, query: str, limit: int = 10) -> list[EmployeeCache]:
    """Search the locally cached employee directory by name or email."""
    query = query.strip()
    if not query:
        return []

    return (
        db.query(EmployeeCache)
        .filter(
            EmployeeCache.display_name.ilike(f"%{query}%")
            | EmployeeCache.email.ilike(f"%{query}%")
        )
        .limit(limit)
        .all()
    )
