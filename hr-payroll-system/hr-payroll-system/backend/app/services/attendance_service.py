"""SERVICE layer: business rules and transactions. No SQL here, no HTTP objects."""
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.config import settings
from app.database import transaction
from app.errors import BusinessRuleError, ConflictError, ForbiddenError, NotFoundError
from app.repositories import attendance_repository as repo
from app.schemas.attendance import AttendanceCreate, AttendanceUpdate
from app.security import ADMIN_HR

LATE_AFTER = time(8, 15)      # business rule: clocking in after 08:15 counts as late


def _now() -> datetime:
    return datetime.now(ZoneInfo(settings.company_timezone))


def _own_employee_id(user: dict) -> int:
    if user["employee_id"] is None:
        raise ForbiddenError("This account is not linked to an employee record")
    return user["employee_id"]


def _get_or_404(db: Session, attendance_id: int) -> dict:
    record = repo.find_by_id(db, attendance_id)
    if record is None:
        raise NotFoundError(f"Attendance record {attendance_id} not found")
    return record


# ------------------------------------------------------- employee self-service
def clock_in(db: Session, user: dict) -> dict:
    employee_id = _own_employee_id(user)
    now = _now()
    today = now.date()

    if repo.find_by_employee_and_date(db, employee_id, today):
        raise ConflictError("You already clocked in today")

    clock_time = now.time().replace(microsecond=0)
    status = "late" if clock_time > LATE_AFTER else "present"
    with transaction(db):
        new_id = repo.insert(db, {
            "employee_id": employee_id, "work_date": today,
            "time_in": clock_time, "time_out": None, "status": status,
        })
    return _get_or_404(db, new_id)


def clock_out(db: Session, user: dict) -> dict:
    employee_id = _own_employee_id(user)
    now = _now()
    record = repo.find_by_employee_and_date(db, employee_id, now.date())

    if record is None or record["time_in"] is None:
        raise BusinessRuleError("You have not clocked in today")
    if record["time_out"] is not None:
        raise ConflictError("You already clocked out today")

    clock_time = now.time().replace(microsecond=0)
    if clock_time < record["time_in"]:
        raise BusinessRuleError("Clock-out time cannot be before clock-in time")

    with transaction(db):
        repo.update(db, record["attendance_id"], {"time_out": clock_time})   # trigger computes hours
    return _get_or_404(db, record["attendance_id"])


# -------------------------------------------------------------------- reads
def list_attendance(
    db: Session, user: dict, *, employee_id: int | None, date_from: date | None,
    date_to: date | None, limit: int, skip: int,
) -> list[dict]:
    if user["role"] not in ADMIN_HR:              # employees only ever see their own records
        employee_id = _own_employee_id(user)
    return repo.search(db, employee_id=employee_id, date_from=date_from,
                       date_to=date_to, limit=limit, skip=skip)


def get_attendance(db: Session, attendance_id: int, user: dict) -> dict:
    record = _get_or_404(db, attendance_id)
    if user["role"] not in ADMIN_HR and record["employee_id"] != user["employee_id"]:
        raise ForbiddenError("You can only view your own attendance")
    return record


# ------------------------------------------------------- Admin/HR management
def create_attendance(db: Session, data: AttendanceCreate) -> dict:
    if repo.find_by_employee_and_date(db, data.employee_id, data.work_date):
        raise ConflictError("Attendance for this employee and date already exists")
    with transaction(db):
        new_id = repo.insert(db, data.model_dump())
    return _get_or_404(db, new_id)


def update_attendance(db: Session, attendance_id: int, data: AttendanceUpdate) -> dict:
    changes = data.model_dump(exclude_unset=True)
    if not changes:
        raise BusinessRuleError("No fields to update")
    current = _get_or_404(db, attendance_id)

    time_in = changes.get("time_in", current["time_in"])
    time_out = changes.get("time_out", current["time_out"])
    if time_in and time_out and time_out < time_in:
        raise BusinessRuleError("time_out must be after time_in")

    with transaction(db):
        repo.update(db, attendance_id, changes)
    return _get_or_404(db, attendance_id)


def delete_attendance(db: Session, attendance_id: int) -> dict:
    _get_or_404(db, attendance_id)
    with transaction(db):
        repo.delete(db, attendance_id)
    return {"message": f"Attendance record {attendance_id} deleted"}
