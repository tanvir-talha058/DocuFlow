from pydantic import BaseModel


class EmployeeOut(BaseModel):
    id: str
    display_name: str
    email: str
