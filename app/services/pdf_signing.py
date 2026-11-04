"""Stamp a captured signature image onto a PDF.

Only PDFs can be stamped in-place; for any other file type the signature is
still recorded (SignatureRecord) but the document itself is left untouched —
callers should check `can_stamp` first.
"""

import base64

import fitz  # PyMuPDF

_STAMP_WIDTH = 170
_STAMP_HEIGHT = 55
_MARGIN = 36
_ROW_HEIGHT = _STAMP_HEIGHT + 34


def can_stamp(content_type: str, filename: str) -> bool:
    return content_type == "application/pdf" or filename.lower().endswith(".pdf")


def stamp_signature(
    *, source_path: str, output_path: str, signature_data_url: str, signer_label: str, slot_index: int
) -> None:
    """Append the signature image + label onto the last page, stacking by slot_index."""
    _, encoded = signature_data_url.split(",", 1)
    image_bytes = base64.b64decode(encoded)

    doc = fitz.open(source_path)
    page = doc[-1]

    y = _MARGIN + slot_index * _ROW_HEIGHT
    if y + _STAMP_HEIGHT + 20 > page.rect.height:
        page = doc.new_page(width=page.rect.width, height=page.rect.height)
        y = _MARGIN

    x = _MARGIN
    img_rect = fitz.Rect(x, y, x + _STAMP_WIDTH, y + _STAMP_HEIGHT)
    page.insert_image(img_rect, stream=image_bytes, keep_proportion=True)
    page.insert_text((x, y + _STAMP_HEIGHT + 14), signer_label, fontsize=9)

    doc.save(output_path)
    doc.close()
