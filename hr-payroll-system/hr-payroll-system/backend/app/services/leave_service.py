"""SERVICE layer: business rules and transactions. No SQL here, no HTTP objects."""
from datetime import date

from sqlalchemy.orm import Session

from app.database import transaction
from app.errors import BusinessRuleError, ConflictError, ForbiddenError, NotFoundError
from app.repositories import leave_repository as repo
from app.schemas.leave import LeaveRequestCreate
from app.security import ADMIN_HR


def _get_or_404(db: Session, request_id: int) -> dict:
    leave = repo.find_by_id(db, request_id)
    if leave is None:
        raise NotFoundError(f"Leave request {request_id} not found")
    return leave


def _own_employee_id(user: dict) -> int:
    if user["employee_id"] is None:
        raise ForbiddenError("This account is not linked to an employee record")
    return user["employee_id"]


def _check_owner_or_staff(leave: dict, user: dict) -> None:
    if user["role"] not in ADMIN_HR and leave["employee_id"] != user["employee_id"]:
        raise ForbiddenError("You can only access your own leave requests")


# ------------------------------------------------------------------- create
def create_leave_request(db: Session, data: LeaveRequestCreate, user: dict) -> dict:
    if data.employee_id is not None and user["role"] not in ADMIN_HR and data.employee_id != user["employee_id"]:
        raise ForbiddenError("You can only file leave for yourself")

    employee_id = data.employee_id if (data.employee_id and user["role"] in ADMIN_HR) else _own_employee_id(user)

    if repo.count_overlaps(db, employee_id, data.start_date, data.end_date) > 0:
        raise ConflictError("A pending or approved leave request already overlaps these dates")

    with transaction(db):
        new_id = repo.insert(db, {
            "employee_id": employee_id, "leave_type_id": data.leave_type_id,
            "start_date": data.start_date, "end_date": data.end_date, "reason": data.reason,
        })
    return _get_or_404(db, new_id)


# -------------------------------------------------------------------- reads
def list_leaves(
    db: Session, user: dict, *, employee_id: int | None, status: str | None, limit: int, skip: int
) -> list[dict]:
    if user["role"] not in ADMIN_HR:
        employee_id = _own_employee_id(user)
    return repo.search(db, employee_id=employee_id, status=status, limit=limit, skip=skip)


def get_leave(db: Session, request_id: int, user: dict) -> dict:
    leave = _get_or_404(db, request_id)
    _check_owner_or_staff(leave, user)
    return leave


def get_balances(db: Session, user: dict, employee_id: int | None) -> list[dict]:
    target = employee_id if (employee_id and user["role"] in ADMIN_HR) else _own_employee_id(user)
    return repo.balances(db, target, date.today().year)


# ------------------------------------------------------------------ actions
def review_leave(db: Session, request_id: int, decision: str, user: dict) -> dict:
    leave = _get_or_404(db, request_id)

    # Business rule: nobody approves or rejects their own leave
    if leave["employee_id"] == user["employee_id"]:
        raise ForbiddenError("You cannot review your own leave request")

    with transaction(db):
        repo.call_review(db, request_id, user["user_id"], decision)   # sp_approve_leave
    return _get_or_404(db, request_id)


def cancel_leave(db: Session, request_id: int, user: dict) -> dict:
    leave = _get_or_404(db, request_id)
    _check_owner_or_staff(leave, user)

    if leave["status"] not in ("pending", "approved"):
        raise BusinessRuleError(f"A {leave['status']} request cannot be cancelled")
    if leave["status"] == "approved" and leave["start_date"] < date.today():
        raise BusinessRuleError("Approved leave that has already started cannot be cancelled")

    with transaction(db):
        repo.set_cancelled(db, request_id)
    return _get_or_404(db, request_id)
