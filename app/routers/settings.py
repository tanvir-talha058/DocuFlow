from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.employee import EmployeeCache
from app.services import sidebar
from app.services.auth import get_current_user
from app.templating import templates

router = APIRouter(tags=["settings"])

VALID_THEMES = {"system", "light", "dark"}


@router.get("/settings")
def settings_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: EmployeeCache = Depends(get_current_user),
):
    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request, "current_user": current_user,
            "saved": request.query_params.get("saved"),
            **sidebar.build_sidebar_context(db, current_user),
        },
    )


@router.post("/settings")
def update_settings(
    display_name: str = Form(...),
    job_title: str = Form(""),
    theme_preference: str = Form("system"),
    notify_on_decision: bool = Form(False),
    db: Session = Depends(get_db),
    current_user: EmployeeCache = Depends(get_current_user),
):
    clean_name = display_name.strip()
    if not clean_name:
        raise HTTPException(status_code=400, detail="Name can't be empty")

    current_user.display_name = clean_name
    current_user.job_title = job_title.strip() or None
    current_user.theme_preference = theme_preference if theme_preference in VALID_THEMES else "system"
    current_user.notify_on_decision = notify_on_decision
    db.add(current_user)
    db.commit()
    return RedirectResponse(url="/settings?saved=1", status_code=303)
