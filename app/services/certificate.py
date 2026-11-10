"""Certificate of Completion for a fully approved chain.

`build_certificate_data` gathers everything the certificate states (document,
requester, every approver with their sent / opened / approved times, captured
signatures and the SHA-256 fingerprint of the final file). The same data drives
both the PDF (`generate_certificate`) and the on-screen certificate page, so the
two can never disagree.
"""

from __future__ import annotations

import base64
import hashlib
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path

import fitz  # PyMuPDF
from sqlalchemy.orm import Session

from app.config import settings
from app.models.audit import AuditEvent
from app.models.chain import ApprovalChain, ApprovalStep, ApproverType
from app.models.document import Document
from app.models.employee import EmployeeCache
from app.models.signature import SignatureRecord

# Upay is in Dhaka; timestamps are stored as naive UTC.
TZ_OFFSET = timedelta(hours=6)
TZ_LABEL = "Dhaka time (GMT+6)"

LOGO_PATH = Path("app/static/images/upay-logo.png")

# ---- Palette (from the Upay logo) ----
_BLUE = (0 / 255, 80 / 255, 160 / 255)          # #0050A0
_INK = (20 / 255, 26 / 255, 46 / 255)           # #141A2E
_INK_SOFT = (78 / 255, 85 / 255, 104 / 255)     # #4E5568
_INK_FAINT = (122 / 255, 128 / 255, 145 / 255)  # #7A8091
_RULE = (216 / 255, 220 / 255, 230 / 255)       # #D8DCE6
_PANEL = (246 / 255, 248 / 255, 251 / 255)      # #F6F8FB
_YELLOW = (240 / 255, 200 / 255, 0 / 255)       # #F0C800
_GREEN = (30 / 255, 107 / 255, 67 / 255)        # #1E6B43
_WHITE = (1, 1, 1)

_PAGE_W, _PAGE_H = 595, 842  # A4 @ 72dpi
_M = 50  # margin


# ---------------------------------------------------------------- data

def certificate_number(chain: ApprovalChain) -> str:
    year = (chain.completed_at or chain.created_at).year
    return f"DF-{year}-{chain.id.replace('-', '')[:8].upper()}"


def local_time(value: datetime | None) -> datetime | None:
    return value + TZ_OFFSET if value else None


def fmt_dt(value: datetime | None, with_time: bool = True) -> str:
    v = local_time(value)
    if v is None:
        return "—"
    return v.strftime("%d %b %Y, %H:%M") if with_time else v.strftime("%d %b %Y")


def fmt_duration(start: datetime | None, end: datetime | None) -> str:
    if not start or not end:
        return "—"
    minutes = max(int((end - start).total_seconds() // 60), 0)
    days, rem = divmod(minutes, 1440)
    hours, mins = divmod(rem, 60)
    if days:
        return f"{days} day{'s' if days != 1 else ''} {hours} h"
    if hours:
        return f"{hours} h {mins} min"
    return f"{max(mins, 1)} min"


def file_sha256(path: str | None) -> str | None:
    if not path or not Path(path).exists():
        return None
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def certificate_url(chain: ApprovalChain) -> str:
    return f"{settings.base_url.rstrip('/')}/chains/{chain.id}/certificate"


def build_certificate_data(db: Session, chain: ApprovalChain) -> dict:
    document = db.get(Document, chain.document_id)
    initiator = db.get(EmployeeCache, chain.initiator_employee_id)
    steps = (
        db.query(ApprovalStep)
        .filter(ApprovalStep.chain_id == chain.id)
        .order_by(ApprovalStep.step_order)
        .all()
    )

    from app.services.chain_engine import resolve_approver  # avoid import cycle

    approvers = []
    for step in steps:
        who = resolve_approver(db, step)
        sig = db.query(SignatureRecord).filter(SignatureRecord.step_id == step.id).one_or_none()
        decided = step.approved_at or step.decided_at
        approvers.append({
            "order": step.step_order,
            "name": who.display_name if who else "Unknown",
            "email": who.email if who else "",
            "role": "External signer" if step.approver_type == ApproverType.CUSTOMER.value else "Employee",
            "job_title": getattr(who, "job_title", None),
            "status": step.status,
            "sent_at": step.notified_at,
            "opened_at": step.first_viewed_at,
            "decided_at": decided,
            "view_count": step.view_count or 0,
            "signature_data_url": sig.image_data_url if sig else None,
        })

    names_by_step = {s.id: a["name"] for s, a in zip(steps, approvers)}
    order_by_step = {s.id: s.step_order for s in steps}
    requester = initiator.display_name if initiator else "the requester"
    events = []
    for ev in (
        db.query(AuditEvent)
        .filter(AuditEvent.chain_id == chain.id)
        .order_by(AuditEvent.created_at)
        .all()
    ):
        who = names_by_step.get(ev.step_id, "")
        step_no = order_by_step.get(ev.step_id)
        text = {
            "CHAIN_CREATED": f"Approval started by {requester}",
            "EMAIL_SENT": f"Review request sent to {who} (step {step_no})" if who else "Review request sent",
            "REMINDER_SENT": f"Reminder sent to {who}" if who else "Reminder sent",
            "STEP_VIEWED": f"Opened by {who}" if who else "Document opened",
            "STEP_APPROVED": f"Approved by {who}" if who else "Step approved",
            "CHAIN_COMPLETED": "All approvals complete",
            "TOKEN_INVALIDATED": "Earlier review link replaced",
        }.get(ev.event_type)
        if text:
            events.append({"at": ev.created_at, "text": text, "type": ev.event_type})

    final_path = document.signed_path or document.stored_path
    final_sha = file_sha256(final_path)
    original_sha = file_sha256(document.stored_path) if document.signed_path else final_sha

    return {
        "chain": chain,
        "document": document,
        "number": certificate_number(chain),
        "title": chain.title or document.original_filename,
        "has_custom_title": bool(chain.title),
        "file_name": document.original_filename,
        "file_kind": (document.content_type or "file").split("/")[-1].upper(),
        "file_size": document.size_bytes,
        "requested_by": initiator.display_name if initiator else "Unknown",
        "requested_by_email": initiator.email if initiator else "",
        "started_at": chain.created_at,
        "completed_at": chain.completed_at,
        "duration": fmt_duration(chain.created_at, chain.completed_at),
        "approvers": approvers,
        "events": events,
        "final_sha256": final_sha,
        "original_sha256": original_sha,
        "is_signed_copy": bool(document.signed_path),
        "url": certificate_url(chain),
        "tz_label": TZ_LABEL,
    }


# ---------------------------------------------------------------- PDF helpers

@lru_cache(maxsize=1)
def _logo_png() -> bytes | None:
    """The source logo is ~5000px wide; shrink it once so certificates stay small."""
    if not LOGO_PATH.exists():
        return None
    pix = fitz.Pixmap(str(LOGO_PATH))
    while pix.width > 700:
        pix.shrink(1)
    return pix.tobytes("png")


def _size(num: int | None) -> str:
    if not num:
        return ""
    for unit in ("bytes", "KB", "MB", "GB"):
        if num < 1024 or unit == "GB":
            return f"{num:.0f} {unit}" if unit == "bytes" else f"{num:.1f} {unit}"
        num /= 1024
    return ""


def _text(page, x, y, text, size=9.5, font="helv", color=_INK):
    page.insert_text((x, y), text, fontsize=size, fontname=font, color=color)


def _width(text, size, font="helv"):
    return fitz.get_text_length(text, fontname=font, fontsize=size)


def _fit(text: str, max_w: float, size: float, font="helv") -> str:
    if _width(text, size, font) <= max_w:
        return text
    while text and _width(text + "…", size, font) > max_w:
        text = text[:-1]
    return text.rstrip() + "…"


def _wrap(text: str, max_w: float, size: float, font: str, max_lines: int) -> list[str]:
    words, lines, line = text.split(), [], ""
    for word in words:
        trial = f"{line} {word}".strip()
        if _width(trial, size, font) <= max_w:
            line = trial
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = _fit(lines[-1] + " …", max_w, size, font)
    return [_fit(l, max_w, size, font) for l in lines]


def _seal(page, cx: float, cy: float, date_label: str) -> None:
    """The one bold element: a round 'Approved' stamp in the approval green."""
    page.draw_circle((cx, cy), 41, color=_GREEN, width=2.2)
    page.draw_circle((cx, cy), 35.5, color=_GREEN, width=0.7, dashes="[2 1.6] 0")
    # check mark
    shape = page.new_shape()
    shape.draw_polyline([(cx - 9, cy - 9), (cx - 3, cy - 3), (cx + 9, cy - 16)])
    shape.finish(color=_GREEN, width=2.6, lineCap=1, lineJoin=1, closePath=False)
    shape.commit()
    label = "APPROVED"
    _text(page, cx - _width(label, 9.5, "hebo") / 2, cy + 8, label, 9.5, "hebo", _GREEN)
    _text(page, cx - _width(date_label, 6.8) / 2, cy + 19, date_label, 6.8, "helv", _GREEN)


def _footer(page, data: dict, page_no: int, page_count: int) -> None:
    y = _PAGE_H - 40
    page.draw_line((_M, y - 14), (_PAGE_W - _M, y - 14), color=_RULE, width=0.6)
    lead = "Verify online: "
    _text(page, _M, y, lead, 7.5, "helv", _INK_FAINT)
    url = data["url"]
    url_x = _M + _width(lead, 7.5)
    _text(page, url_x, y, url, 7.5, "helv", _BLUE)
    page.insert_link({
        "kind": fitz.LINK_URI,
        "from": fitz.Rect(url_x, y - 8, url_x + _width(url, 7.5), y + 2),
        "uri": url,
    })
    right = f"{data['number']}   Page {page_no} of {page_count}"
    _text(page, _PAGE_W - _M - _width(right, 7.5), y, right, 7.5, "helv", _INK_FAINT)
    note = f"Issued by DocuFlow for Upay. All times are {data['tz_label']}."
    _text(page, _M, y + 11, note, 7, "helv", _INK_FAINT)


# ---------------------------------------------------------------- PDF

def _render_pdf(data: dict) -> fitz.Document:
    doc = fitz.open()
    page = doc.new_page(width=_PAGE_W, height=_PAGE_H)
    right = _PAGE_W - _M
    content_w = right - _M

    # Top accent: Upay blue band with a short yellow segment.
    page.draw_rect(fitz.Rect(0, 0, _PAGE_W, 6), color=None, fill=_BLUE)
    page.draw_rect(fitz.Rect(_M, 6, _M + 64, 9), color=None, fill=_YELLOW)

    # Header: logo left, certificate number right.
    y = 30
    logo = _logo_png()
    if logo:
        page.insert_image(fitz.Rect(_M, y, _M + 92, y + 47), stream=logo, keep_proportion=True)
    else:
        _text(page, _M, y + 28, "upay", 22, "hebo", _BLUE)
    for i, (label, value, font) in enumerate([
        ("Certificate no.", data["number"], "cobo"),
        ("Issued", fmt_dt(data["completed_at"], with_time=False), "helv"),
    ]):
        ly = y + 12 + i * 22
        _text(page, right - _width(label, 7.5), ly, label, 7.5, "helv", _INK_FAINT)
        _text(page, right - _width(value, 9.5, font), ly + 11, value, 9.5, font, _INK)

    # Title
    y = 112
    _text(page, _M, y, "Certificate of Completion", 28, "tibo", _INK)
    y += 20
    intro = ("This certifies that the document below was reviewed and approved by every "
             "person in its approval chain, in the order shown.")
    for line in _wrap(intro, content_w, 10, "helv", 2):
        _text(page, _M, y, line, 10, "helv", _INK_SOFT)
        y += 14

    # Document panel with the seal.
    y += 10
    panel = fitz.Rect(_M, y, right, y + 104)
    page.draw_rect(panel, color=_RULE, fill=_PANEL, width=0.8, radius=0.06)
    page.draw_rect(fitz.Rect(_M, y, _M + 3.5, y + 104), color=None, fill=_BLUE)
    tx, tw = _M + 20, content_w - 20 - 112
    _text(page, tx, y + 22, "Document", 8, "helv", _INK_FAINT)
    ty = y + 42
    for line in _wrap(data["title"], tw, 17, "tibo", 2):
        _text(page, tx, ty, line, 17, "tibo", _BLUE)
        ty += 20
    meta = data["file_name"] if data["has_custom_title"] else ""
    meta_bits = [b for b in [meta, data["file_kind"], _size(data["file_size"])] if b]
    _text(page, tx, ty - 2, _fit(", ".join(meta_bits), tw, 8.5), 8.5, "helv", _INK_SOFT)
    _seal(page, right - 58, y + 52, fmt_dt(data["completed_at"], with_time=False))
    y = panel.y1 + 22

    # Key facts row.
    facts = [
        ("Requested by", data["requested_by"]),
        ("Started", fmt_dt(data["started_at"])),
        ("Completed", fmt_dt(data["completed_at"])),
        ("Time taken", data["duration"]),
        ("Approvers", str(len(data["approvers"]))),
    ]
    col_w = content_w / len(facts)
    for i, (label, value) in enumerate(facts):
        fx = _M + i * col_w
        if i:
            page.draw_line((fx - 8, y - 8), (fx - 8, y + 22), color=_RULE, width=0.6)
        _text(page, fx, y, label, 7.5, "helv", _INK_FAINT)
        _text(page, fx, y + 14, _fit(value, col_w - 14, 9.5, "hebo"), 9.5, "hebo", _INK)
    y += 46

    # Approval record.
    def section_heading(pg, yy, title):
        _text(pg, _M, yy, title, 13, "tibo", _INK)
        pg.draw_line((_M, yy + 8), (right, yy + 8), color=_RULE, width=0.6)
        return yy + 28

    y = section_heading(page, y, "Approval record")
    cols = [("Sent", "sent_at"), ("Opened", "opened_at"), ("Approved", "decided_at")]
    col_x = [_M + 238, _M + 314, _M + 390]
    row_h = 52
    approvers = data["approvers"]
    for idx, a in enumerate(approvers):
        if y + row_h > _PAGE_H - 150:
            page = doc.new_page(width=_PAGE_W, height=_PAGE_H)
            page.draw_rect(fitz.Rect(0, 0, _PAGE_W, 6), color=None, fill=_BLUE)
            y = section_heading(page, 50, "Approval record (continued)")

        # Timeline dot + connector.
        cx = _M + 10
        if idx < len(approvers) - 1:
            page.draw_line((cx, y + 4), (cx, y + row_h - 4), color=_GREEN, width=1.2)
        page.draw_circle((cx, y - 3), 10, color=_GREEN, fill=_GREEN)
        num = str(a["order"])
        _text(page, cx - _width(num, 9, "hebo") / 2, y + 0.3, num, 9, "hebo", _WHITE)

        nx = _M + 30
        _text(page, nx, y, _fit(a["name"], 190, 10.5, "hebo"), 10.5, "hebo", _INK)
        role = a["role"] + (f", {a['job_title']}" if a.get("job_title") else "")
        _text(page, nx, y + 13, _fit(role, 190, 8), 8, "helv", _INK_SOFT)
        _text(page, nx, y + 24, _fit(a["email"], 190, 8), 8, "helv", _INK_FAINT)

        for (label, key), x in zip(cols, col_x):
            _text(page, x, y - 1, label, 7, "helv", _INK_FAINT)
            value = local_time(a[key])
            line1 = value.strftime("%d %b %Y") if value else "—"
            line2 = value.strftime("%H:%M") if value else ""
            color = _GREEN if key == "decided_at" and value else _INK
            font = "hebo" if key == "decided_at" and value else "helv"
            _text(page, x, y + 11, line1, 8.5, font, color)
            _text(page, x, y + 22, line2, 8, "helv", _INK_SOFT)

        sig_rect = fitz.Rect(right - 64, y - 12, right, y + 26)
        if a["signature_data_url"] and "," in a["signature_data_url"]:
            try:
                raw = base64.b64decode(a["signature_data_url"].split(",", 1)[1])
                page.insert_image(sig_rect, stream=raw, keep_proportion=True)
                page.draw_line((sig_rect.x0, sig_rect.y1 + 1), (sig_rect.x1, sig_rect.y1 + 1), color=_RULE, width=0.5)
            except Exception:
                pass
        y += row_h
        if idx < len(approvers) - 1:
            page.draw_line((nx, y - 14), (right, y - 14), color=_RULE, width=0.4, dashes="[1.5 2] 0")

    # Fingerprint.
    if y > _PAGE_H - 170:
        page = doc.new_page(width=_PAGE_W, height=_PAGE_H)
        page.draw_rect(fitz.Rect(0, 0, _PAGE_W, 6), color=None, fill=_BLUE)
        y = 50
    y += 6
    fingerprint_page = doc.page_count
    y = section_heading(page, y, "Document fingerprint")
    sha = data["final_sha256"] or "Unavailable (file not found)"
    box = fitz.Rect(_M, y - 12, right, y + 34)
    page.draw_rect(box, color=_RULE, fill=_PANEL, width=0.6, radius=0.12)
    _text(page, _M + 12, y + 3, "SHA-256" + (" of the signed copy" if data["is_signed_copy"] else ""), 7.5, "helv", _INK_FAINT)
    _text(page, _M + 12, y + 20, sha, 8.6, "cour", _INK)
    y = box.y1 + 16
    explain = ("Any change to the file, even one character, produces a different fingerprint. "
               "To check a copy, upload it on the verification page linked below.")
    for line in _wrap(explain, content_w, 8, "helv", 2):
        _text(page, _M, y, line, 8, "helv", _INK_SOFT)
        y += 11

    # Event history (from the audit log), continuing onto new pages if long.
    events = data["events"]
    if events:
        y += 16
        if y > _PAGE_H - 140:
            page = doc.new_page(width=_PAGE_W, height=_PAGE_H)
            page.draw_rect(fitz.Rect(0, 0, _PAGE_W, 6), color=None, fill=_BLUE)
            y = 50
        y = section_heading(page, y, "Event history")
        for ev in events:
            if y > _PAGE_H - 78:
                page = doc.new_page(width=_PAGE_W, height=_PAGE_H)
                page.draw_rect(fitz.Rect(0, 0, _PAGE_W, 6), color=None, fill=_BLUE)
                y = section_heading(page, 50, "Event history (continued)")
            dot = _GREEN if ev["type"] in ("STEP_APPROVED", "CHAIN_COMPLETED") else _BLUE
            page.draw_circle((_M + 4, y - 3), 2.4, color=dot, fill=dot)
            _text(page, _M + 14, y, fmt_dt(ev["at"]), 8.5, "helv", _INK_SOFT)
            strong = ev["type"] in ("STEP_APPROVED", "CHAIN_COMPLETED")
            _text(page, _M + 120, y, _fit(ev["text"], content_w - 120, 8.5), 8.5, "hebo" if strong else "helv", _INK)
            y += 16

    count = doc.page_count
    for i in range(count):
        _footer(doc[i], data, i + 1, count)

    doc.set_metadata({
        "title": f"Certificate of Completion: {data['title']}",
        "author": "DocuFlow by Upay",
        "subject": f"Approval record for {data['file_name']}",
        "keywords": f"{data['number']}, certificate of completion, approval",
        "creator": "DocuFlow",
        "producer": "DocuFlow",
    })
    doc.set_toc([[1, "Certificate of Completion", 1], [2, "Approval record", 1], [2, "Document fingerprint", fingerprint_page]])
    return doc


def generate_certificate(db: Session, chain: ApprovalChain) -> str:
    """Render the certificate PDF for a fully approved chain and return its path."""
    data = build_certificate_data(db, chain)
    doc = _render_pdf(data)
    output_path = str(Path(settings.upload_dir) / f"{chain.id}_certificate.pdf")
    doc.save(output_path, garbage=3, deflate=True)
    doc.close()
    return output_path
