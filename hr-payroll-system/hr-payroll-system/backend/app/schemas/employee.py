from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_serializer

EmployeeStatus = Literal["active", "on_leave", "resigned", "terminated"]


class EmployeeCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=50)
    last_name: str = Field(min_length=1, max_length=50)
    email: EmailStr
    phone: str | None = Field(None, max_length=30)
    birth_date: date | None = None
    hire_date: date | None = None            # defaults to today in the database
    position_id: int
    manager_id: int | None = None
    base_salary: Decimal = Field(gt=0, max_digits=12, decimal_places=2)   # monthly


class EmployeeUpdate(BaseModel):
    """Every field is optional: send only what you want to change."""

    first_name: str | None = Field(None, min_length=1, max_length=50)
    last_name: str | None = Field(None, min_length=1, max_length=50)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=30)
    birth_date: date | None = None
    hire_date: date | None = None
    position_id: int | None = None
    manager_id: int | None = None
    base_salary: Decimal | None = Field(None, gt=0, max_digits=12, decimal_places=2)
    status: EmployeeStatus | None = None


class EmployeeOut(BaseModel):
    employee_id: int
    employee_no: str
    first_name: str
    last_name: str
    email: str
    phone: str | None
    birth_date: date | None
    hire_date: date
    position_id: int
    position: str
    department_id: int
    department: str
    manager_id: int | None
    base_salary: Decimal
    status: str

    @field_serializer("base_salary", when_used="json")
    def _salary_as_number(self, value: Decimal) -> float:
        return float(value)      # JSON number instead of a string, easier for React
