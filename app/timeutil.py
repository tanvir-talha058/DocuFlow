from datetime import datetime, timezone


def utcnow() -> datetime:
    """Naive UTC datetime, matching SQLite's DateTime storage (no tzinfo)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
