from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import Number


class LeaveRequestCreate(BaseModel):
    employee_id: int | None = None        # only Admin/HR may file for someone else
    leave_type_id: int
    start_date: date
    end_date: date
    reason: str | None = Field(None, max_length=500)

    @model_validator(mode="after")
    def _check_dates(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class LeaveReview(BaseModel):
    decision: Literal["approved", "rejected"]


class LeaveOut(BaseModel):
    request_id: int
    employee_id: int
    employee_name: str
    leave_type_id: int
    leave_type: str
    start_date: date
    end_date: date
    days_requested: int
    reason: str | None
    status: str
    reviewed_by: int | None
    reviewed_at: datetime | None
    created_at: datetime


class LeaveBalanceOut(BaseModel):
    employee_id: int
    leave_type_id: int
    leave_type: str
    leave_year: int
    allocated_days: Number
    used_days: Number
    remaining_days: Number
