from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.employee import EmployeeCache
from app.schemas.employees import EmployeeOut
from app.services.auth import get_current_user
from app.services.directory import search_employees

router = APIRouter(prefix="/api/employees", tags=["employees"])


@router.get("/search", response_model=list[EmployeeOut])
def search(q: str, db: Session = Depends(get_db), _user: EmployeeCache = Depends(get_current_user)):
    employees = search_employees(db, q)
    return [EmployeeOut(id=e.id, display_name=e.display_name, email=e.email) for e in employees]
