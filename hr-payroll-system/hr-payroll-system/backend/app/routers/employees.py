"""ROUTER layer: HTTP only. Validate input, check the role, call ONE service function."""
from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.employee import EmployeeCreate, EmployeeOut, EmployeeUpdate
from app.security import ADMIN_HR, get_current_user, require_role
from app.services import employee_service

router = APIRouter(prefix="/employees", tags=["Employees"])


@router.get("", response_model=list[EmployeeOut])
def list_employees(
    search: str | None = Query(None, description="Matches first name, last name or email"),
    department_id: int | None = None,
    status_filter: Literal["active", "on_leave", "resigned", "terminated"] | None = Query(
        None, alias="status"
    ),
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _user: dict = Depends(require_role(*ADMIN_HR)),
):
    return employee_service.list_employees(
        db, search=search, department_id=department_id, status=status_filter, limit=limit, skip=skip
    )


# NOTE: /me must be declared BEFORE /{employee_id}, otherwise "me" is read as an id.
@router.get("/me", response_model=EmployeeOut)
def my_profile(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    return employee_service.get_my_profile(db, user)


@router.get("/{employee_id}", response_model=EmployeeOut)
def get_employee(
    employee_id: int, user: dict = Depends(get_current_user), db: Session = Depends(get_db)
):
    return employee_service.get_employee(db, employee_id, user)


@router.post("", response_model=EmployeeOut, status_code=status.HTTP_201_CREATED)
def create_employee(
    body: EmployeeCreate,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_role(*ADMIN_HR)),
):
    return employee_service.create_employee(db, body)


@router.put("/{employee_id}", response_model=EmployeeOut)
def update_employee(
    employee_id: int,
    body: EmployeeUpdate,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_role(*ADMIN_HR)),
):
    return employee_service.update_employee(db, employee_id, body)


@router.delete("/{employee_id}")
def delete_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_role("Admin")),
):
    return employee_service.terminate_employee(db, employee_id)
