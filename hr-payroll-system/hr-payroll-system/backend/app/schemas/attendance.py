from datetime import date, time
from typing import Literal

from pydantic import BaseModel, model_validator

from app.schemas.common import Number

AttendanceStatus = Literal["present", "late", "absent", "half_day"]


class AttendanceCreate(BaseModel):
    """Manual entry by Admin/HR. Employees use /attendance/clock-in and /clock-out instead."""

    employee_id: int
    work_date: date
    time_in: time | None = None
    time_out: time | None = None
    status: AttendanceStatus = "present"

    @model_validator(mode="after")
    def _check_times(self):
        if self.time_in and self.time_out and self.time_out < self.time_in:
            raise ValueError("time_out must be after time_in")
        return self


class AttendanceUpdate(BaseModel):
    time_in: time | None = None
    time_out: time | None = None
    status: AttendanceStatus | None = None


class AttendanceOut(BaseModel):
    attendance_id: int
    employee_id: int
    employee_name: str
    work_date: date
    time_in: time | None
    time_out: time | None
    hours_worked: Number         # computed by the database trigger
    overtime_hours: Number       # computed by the database trigger
    status: str