import math
from datetime import timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.audit import AuditEvent
from app.models.chain import ApprovalChain, ApprovalStep, ApproverType, ChainStatus, StepStatus
from app.models.document import Document
from app.models.employee import EmployeeCache
from app.services import activity, chain_engine
from app.services.auth import get_current_user
from app.templating import templates
from app.timeutil import utcnow

router = APIRouter(tags=["dashboard"])

BUCKETS = ("total", "in_progress", "approved", "rejected")


def _bucket_of(status: str) -> str | None:
    if status in (ChainStatus.PENDING.value, ChainStatus.IN_PROGRESS.value):
        return "in_progress"
    if status == ChainStatus.APPROVED.value:
        return "approved"
    if status == ChainStatus.REJECTED.value:
        return "rejected"
    return None


def _greeting(now) -> str:
    hour = now.hour
    if hour < 12:
        return "Good morning"
    if hour < 17:
        return "Good afternoon"
    return "Good evening"


def _delta_label(curr: int, prev: int) -> str:
    if curr == prev:
        return "No change"
    if prev == 0:
        return f"+{curr} this week" if curr == 1 else f"+{curr} new this week"
    pct = round((curr - prev) / prev * 100)
    sign = "+" if pct > 0 else ""
    return f"{sign}{pct}% vs last 7 days"


def _build_stats(rows: list[tuple[ApprovalChain, Document]], now) -> dict:
    """Stat-card totals, 7-day-vs-prior-7-day deltas, and a 7-day daily series
    per bucket (also reused for the Activity Trend bar chart)."""
    totals = {b: 0 for b in BUCKETS}
    this_week = {b: 0 for b in BUCKETS}
    prev_week = {b: 0 for b in BUCKETS}
    daily = {b: [0] * 7 for b in BUCKETS}

    for chain, _document in rows:
        bucket = _bucket_of(chain.status)
        totals["total"] += 1
        if bucket:
            totals[bucket] += 1

        age_days = (now.date() - chain.created_at.date()).days
        if 0 <= age_days < 7:
            day_index = 6 - age_days
            this_week["total"] += 1
            daily["total"][day_index] += 1
            if bucket:
                this_week[bucket] += 1
                daily[bucket][day_index] += 1
        elif 7 <= age_days < 14:
            prev_week["total"] += 1
            if bucket:
                prev_week[bucket] += 1

    day_labels = []
    for i in range(7):
        day = now - timedelta(days=6 - i)
        day_labels.append(f"{day.strftime('%b')} {day.day}")

    stats = {}
    for b in BUCKETS:
        stats[b] = {
            "total": totals[b],
            "delta": _delta_label(this_week[b], prev_week[b]),
            "sparkline_points": _sparkline_points(daily[b]),
        }
    return {"stats": stats, "day_labels": day_labels, "trend": daily["total"]}


def _document_flow(my_approvals: list, rows: list[tuple[ApprovalChain, Document]]):
    """Pick the single chain to feature in the 'Document Flow' stepper: the
    sender's own pending approval if they have one, else their most recent
    routed document."""
    if my_approvals:
        _step, chain, document = my_approvals[0]
    elif rows:
        chain, document = rows[0]
    else:
        return None

    rejected = chain.status == ChainStatus.REJECTED.value
    in_review = chain.status in (ChainStatus.PENDING.value, ChainStatus.IN_PROGRESS.value)
    approved = chain.status == ChainStatus.APPROVED.value

    stages = [
        {"label": "Uploaded", "done": True, "current": False},
        {"label": "In Review", "done": approved or rejected, "current": in_review, "rejected": rejected},
        {"label": "Approved", "done": approved, "current": False},
        {"label": "Completed", "done": approved, "current": approved},
    ]
    reached_index = max(i for i, s in enumerate(stages) if s["done"] or s["current"])
    progress_pct = round(reached_index / (len(stages) - 1) * 100)
    return {"chain": chain, "document": document, "stages": stages, "progress_pct": progress_pct, "rejected": rejected}


def _sparkline_points(values: list[int], width: int = 90, height: int = 28) -> str:
    """SVG polyline 'x,y ...' string for a small inline trend line."""
    if not values:
        return ""
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1
    step = width / (len(values) - 1) if len(values) > 1 else 0
    points = []
    for i, v in enumerate(values):
        x = round(i * step, 1)
        y = round(height - ((v - lo) / span) * (height - 4) - 2, 1)
        points.append(f"{x},{y}")
    return " ".join(points)


def _trend_chart(values: list[int], labels: list[str], width: int = 600, height: int = 140, pad_x: int = 12, pad_y: int = 16) -> dict:
    """Geometry for an SVG line/area trend chart: a polyline plus per-point
    markers (for dots + hover titles) and a closed area path for the fill."""
    usable_w = width - pad_x * 2
    usable_h = height - pad_y * 2
    hi = max(values, default=0) or 1
    step = usable_w / (len(values) - 1) if len(values) > 1 else 0

    markers = []
    for i, v in enumerate(values):
        x = round(pad_x + i * step, 1)
        y = round(pad_y + usable_h - (v / hi) * usable_h, 1)
        markers.append({"x": x, "y": y, "value": v, "label": labels[i] if i < len(labels) else ""})

    points = " ".join(f"{m['x']},{m['y']}" for m in markers)
    baseline = height - pad_y
    if markers:
        area_path = (
            f"M{markers[0]['x']},{baseline} "
            + " ".join(f"L{m['x']},{m['y']}" for m in markers)
            + f" L{markers[-1]['x']},{baseline} Z"
        )
    else:
        area_path = ""

    return {"points": points, "area_path": area_path, "markers": markers, "width": width, "height": height}


DONUT_SEGMENTS = (
    ("in_progress", "In Progress", "--seal-gold"),
    ("approved", "Approved", "--stamp-green"),
    ("rejected", "Rejected", "--stamp-red"),
)


def _donut_segments(stats: dict, radius: int = 54) -> list[dict]:
    circumference = 2 * math.pi * radius
    total = stats["total"]["total"]
    segments = []
    offset = 0.0
    for key, label, color_var in DONUT_SEGMENTS:
        count = stats[key]["total"]
        pct = (count / total * 100) if total else 0
        arc = circumference * (count / total) if total else 0
        segments.append({
            "label": label, "count": count, "pct": round(pct),
            "color_var": color_var, "dasharray": f"{arc:.2f} {circumference - arc:.2f}",
            "dashoffset": round(-offset, 2),
        })
        offset += arc
    return segments


def _recent_activity(db: Session, chain_ids: list[str], limit: int = 6) -> list[dict]:
    if not chain_ids:
        return []
    events = (
        db.query(AuditEvent)
        .filter(AuditEvent.chain_id.in_(chain_ids))
        .order_by(AuditEvent.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {"event": event, "label": activity.event_label(event.event_type), "tone": activity.event_tone(event.event_type)}
        for event in events
    ]


def _build_tracking(db: Session, chain_ids: list[str]) -> dict[str, dict]:
    """Per-chain 'who's seen it' summary for the dashboard list.

    Keyed by chain_id: {seen, total, pending_approver_name, last_activity}
    where last_activity is the most recent of notified_at/last_viewed_at/decided_at
    across that chain's steps.
    """
    if not chain_ids:
        return {}
    steps = (
        db.query(ApprovalStep)
        .filter(ApprovalStep.chain_id.in_(chain_ids))
        .order_by(ApprovalStep.step_order)
        .all()
    )
    by_chain: dict[str, list[ApprovalStep]] = {}
    for step in steps:
        by_chain.setdefault(step.chain_id, []).append(step)

    approver_ids = {s.approver_employee_id for s in steps if s.approver_employee_id}
    approvers = {
        e.id: e for e in db.query(EmployeeCache).filter(EmployeeCache.id.in_(approver_ids)).all()
    } if approver_ids else {}

    tracking: dict[str, dict] = {}
    for chain_id, chain_steps in by_chain.items():
        seen = sum(1 for s in chain_steps if s.first_viewed_at is not None)
        total = len(chain_steps)
        last_activity = None
        for s in chain_steps:
            for ts in (s.notified_at, s.last_viewed_at, s.decided_at):
                if ts is not None and (last_activity is None or ts > last_activity):
                    last_activity = ts

        pending = next((s for s in chain_steps if s.status == StepStatus.PENDING.value), None)
        pending_approver_name = None
        if pending is not None:
            if pending.approver_type == ApproverType.CUSTOMER.value:
                customer = chain_engine.resolve_approver(db, pending)
                pending_approver_name = customer.display_name if customer else None
            else:
                approver = approvers.get(pending.approver_employee_id)
                pending_approver_name = approver.display_name if approver else None

        tracking[chain_id] = {
            "seen": seen,
            "total": total,
            "steps": chain_steps,
            "pending_approver_name": pending_approver_name,
            "last_activity": last_activity,
        }
    return tracking


@router.get("/")
def dashboard(
    request: Request,
    db: Session = Depends(get_db),
    current_user: EmployeeCache = Depends(get_current_user),
):
    rows = (
        db.query(ApprovalChain, Document)
        .join(Document, Document.id == ApprovalChain.document_id)
        .filter(ApprovalChain.initiator_employee_id == current_user.id)
        .order_by(ApprovalChain.created_at.desc())
        .all()
    )

    # Steps actually waiting on this employee right now: it's their step, it's
    # pending, and the chain hasn't moved past or before it.
    my_approvals = (
        db.query(ApprovalStep, ApprovalChain, Document)
        .join(ApprovalChain, ApprovalChain.id == ApprovalStep.chain_id)
        .join(Document, Document.id == ApprovalChain.document_id)
        .filter(
            ApprovalStep.approver_type == ApproverType.EMPLOYEE.value,
            ApprovalStep.approver_employee_id == current_user.id,
            ApprovalStep.status == StepStatus.PENDING.value,
            ApprovalChain.status == ChainStatus.IN_PROGRESS.value,
            ApprovalChain.current_step_order == ApprovalStep.step_order,
        )
        .order_by(ApprovalChain.created_at.desc())
        .all()
    )
    initiator_ids = {chain.initiator_employee_id for _step, chain, _document in my_approvals}
    initiators = {
        e.id: e for e in db.query(EmployeeCache).filter(EmployeeCache.id.in_(initiator_ids)).all()
    } if initiator_ids else {}

    chain_ids = [chain.id for chain, _document in rows]
    tracking = _build_tracking(db, chain_ids)
    now = utcnow()
    overview = _build_stats(rows, now)
    donut = _donut_segments(overview["stats"])
    trend_chart = _trend_chart(overview["trend"], overview["day_labels"])
    document_flow = _document_flow(my_approvals, rows)
    recent_activity = _recent_activity(db, chain_ids)

    storage_used_bytes = sum(document.size_bytes for _chain, document in rows)
    storage_pct = (
        min(100, round(storage_used_bytes / settings.storage_quota_bytes * 100))
        if settings.storage_quota_bytes else 0
    )

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request, "current_user": current_user, "chains": rows,
            "my_approvals": my_approvals, "initiators": initiators, "tracking": tracking,
            "stats": overview["stats"], "day_labels": overview["day_labels"], "trend": overview["trend"],
            "trend_chart": trend_chart,
            "donut": donut, "donut_total": overview["stats"]["total"]["total"],
            "document_flow": document_flow, "recent_activity": recent_activity,
            "storage_used_bytes": storage_used_bytes, "storage_quota_bytes": settings.storage_quota_bytes,
            "storage_pct": storage_pct, "now": now, "pending_approvals_count": len(my_approvals),
            "notifications_preview": [
                {"chain_id": chain.id, "title": chain.title or document.original_filename, "step_order": step.step_order}
                for step, chain, document in my_approvals[:5]
            ],
            "greeting": _greeting(now), "today_label": f"{now.strftime('%b')} {now.day}, {now.year}",
        },
    )
