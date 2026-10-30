"""SERVICE layer: business rules and transactions. No SQL here, no HTTP objects."""
from decimal import Decimal

from sqlalchemy.orm import Session

from app.database import transaction
from app.errors import BusinessRuleError, ForbiddenError, NotFoundError
from app.repositories import employee_repository, lookup_repository, user_repository
from app.schemas.employee import EmployeeCreate, EmployeeUpdate
from app.security import ADMIN_HR


# ------------------------------------------------------------------ helpers
def _get_or_404(db: Session, employee_id: int) -> dict:
    employee = employee_repository.find_by_id(db, employee_id)
    if employee is None:
        raise NotFoundError(f"Employee {employee_id} not found")
    return employee


def _check_salary_in_range(db: Session, position_id: int, salary: Decimal) -> None:
    """Business rule: salary must fall inside the position's min/max range."""
    position = lookup_repository.get_position(db, position_id)
    if position is None:
        raise NotFoundError(f"Position {position_id} does not exist")
    if not (position["min_salary"] <= salary <= position["max_salary"]):
        raise BusinessRuleError(
            f"Salary {salary} is outside the range for {position['title']} "
            f"({position['min_salary']} - {position['max_salary']})"
        )


# -------------------------------------------------------------------- reads
def list_employees(db: Session, *, search, department_id, status, limit, skip) -> list[dict]:
    return employee_repository.search(
        db, search=search, department_id=department_id, status=status, limit=limit, skip=skip
    )


def get_employee(db: Session, employee_id: int, current_user: dict) -> dict:
    # Business rule: Admin/HR can view anyone; an Employee can only view their own record
    if current_user["role"] not in ADMIN_HR and current_user["employee_id"] != employee_id:
        raise ForbiddenError("You can only view your own record")
    return _get_or_404(db, employee_id)


def get_my_profile(db: Session, current_user: dict) -> dict:
    if current_user["employee_id"] is None:
        raise NotFoundError("This account is not linked to an employee record")
    return _get_or_404(db, current_user["employee_id"])


# ------------------------------------------------------------------- writes
def create_employee(db: Session, data: EmployeeCreate) -> dict:
    _check_salary_in_range(db, data.position_id, data.base_salary)
    with transaction(db):
        new_id = employee_repository.insert(db, data.model_dump())
    return _get_or_404(db, new_id)


def update_employee(db: Session, employee_id: int, data: EmployeeUpdate) -> dict:
    changes = data.model_dump(exclude_unset=True)     # only the fields the client actually sent
    if not changes:
        raise BusinessRuleError("No fields to update")

    current = _get_or_404(db, employee_id)

    if "position_id" in changes or "base_salary" in changes:
        position_id = changes.get("position_id") or current["position_id"]
        salary = changes.get("base_salary") or current["base_salary"]
        _check_salary_in_range(db, position_id, salary)

    with transaction(db):
        employee_repository.update(db, employee_id, changes)
    return _get_or_404(db, employee_id)


def terminate_employee(db: Session, employee_id: int) -> dict:
    """Soft delete: payslips and attendance must keep pointing at this employee, so we
    mark them 'terminated' and disable their login instead of removing the row."""
    _get_or_404(db, employee_id)
    with transaction(db):
        employee_repository.set_status(db, employee_id, "terminated")
        user_repository.set_active_by_employee(db, employee_id, False)
    return {"message": f"Employee {employee_id} terminated and login disabled"}
