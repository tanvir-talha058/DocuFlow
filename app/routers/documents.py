from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.chain import ApprovalChain
from app.models.document import Document
from app.models.employee import EmployeeCache
from app.services import sidebar
from app.services.auth import get_current_user
from app.templating import templates

router = APIRouter(tags=["documents"])


@router.get("/documents")
def document_list(
    request: Request,
    db: Session = Depends(get_db),
    current_user: EmployeeCache = Depends(get_current_user),
):
    rows = (
        db.query(Document, ApprovalChain)
        .outerjoin(ApprovalChain, ApprovalChain.document_id == Document.id)
        .filter(Document.uploaded_by_employee_id == current_user.id)
        .order_by(Document.uploaded_at.desc())
        .all()
    )

    return templates.TemplateResponse(
        "documents.html",
        {
            "request": request, "current_user": current_user, "documents": rows,
            **sidebar.build_sidebar_context(db, current_user),
        },
    )
