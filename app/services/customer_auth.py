from fastapi import Request
from sqlalchemy.orm import Session

from app.models.customer import Customer

SESSION_CUSTOMER_KEY = "customer_id"


def get_logged_in_customer(request: Request, db: Session) -> Customer | None:
    customer_id = request.session.get(SESSION_CUSTOMER_KEY)
    if not customer_id:
        return None
    return db.get(Customer, customer_id)


def log_in_customer(request: Request, customer: Customer) -> None:
    request.session[SESSION_CUSTOMER_KEY] = customer.id
