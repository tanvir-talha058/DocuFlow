from sqlalchemy.orm import Session

from app.models.employee import EmployeeCache
from app.services.graph_client import get_graph_client
from app.timeutil import utcnow


def search_employees(db: Session, query: str, limit: int = 10) -> list[EmployeeCache]:
    """Search the org directory via Graph and upsert results into the local cache."""
    query = query.strip()
    if not query:
        return []

    graph_users = get_graph_client().search_users(query)
    now = utcnow()
    for u in graph_users:
        mail = u.get("mail")
        if not mail:
            continue
        existing = db.query(EmployeeCache).filter(EmployeeCache.email == mail).one_or_none()
        if existing:
            existing.display_name = u.get("displayName", existing.display_name)
            existing.job_title = u.get("jobTitle")
            existing.department = u.get("department")
            existing.last_synced_at = now
        else:
            db.add(
                EmployeeCache(
                    entra_object_id=u["id"],
                    display_name=u.get("displayName", mail),
                    email=mail,
                    job_title=u.get("jobTitle"),
                    department=u.get("department"),
                    last_synced_at=now,
                )
            )
    db.commit()

    return (
        db.query(EmployeeCache)
        .filter(
            EmployeeCache.display_name.ilike(f"%{query}%")
            | EmployeeCache.email.ilike(f"%{query}%")
        )
        .limit(limit)
        .all()
    )
