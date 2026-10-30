"""ROUTER layer: HTTP only. Validate input, check the role, call ONE service function."""
from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.payroll import (
    DeductionTypeCreate,
    DeductionTypeOut,
    DeductionTypeUpdate,
    GeneratePayrollRequest,
    PayrollPeriodCreate,
    PayrollPeriodOut,
    PayrollPeriodUpdate,
    PayslipOut,
)
from app.security import ADMIN_HR, get_current_user, require_role
from app.services import payroll_service

router = APIRouter(prefix="/payroll", tags=["Payroll"])


# --- Payroll Periods ---


@router.get("/periods", response_model=list[PayrollPeriodOut])
def list_periods(
    db: Session = Depends(get_db),
    _user: dict = Depends(require_role(*ADMIN_HR)),
):
    """Lists all payroll periods."""
    return payroll_service.list_periods(db)


@router.get("/periods/{period_id}", response_model=PayrollPeriodOut)
def get_period(
    period_id: int,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_role(*ADMIN_HR)),
):
    """Returns a single payroll period."""
    return payroll_service.get_period(db, period_id)


@router.post("/periods", response_model=PayrollPeriodOut, status_code=status.HTTP_201_CREATED)
def create_period(
    body: PayrollPeriodCreate,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_role(*ADMIN_HR)),
):
    """Creates a new payroll period."""
    return payroll_service.create_period(db, body.model_dump())


@router.put("/periods/{period_id}", response_model=PayrollPeriodOut)
def update_period(
    period_id: int,
    body: PayrollPeriodUpdate,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_role(*ADMIN_HR)),
):
    """Updates a payroll period (only if status is 'open')."""
    return payroll_service.update_period(db, period_id, body.model_dump(exclude_unset=True))


# --- Generate Payroll ---


@router.post("/generate", status_code=status.HTTP_201_CREATED)
def generate_payroll(
    body: GeneratePayrollRequest,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_role(*ADMIN_HR)),
):
    """Generates payslips for all active employees in a period using sp_generate_payroll."""
    return payroll_service.generate_payroll(db, body.period_id)


# --- Payslips ---


@router.get("/payslips", response_model=list[PayslipOut])
def list_payslips(
    period_id: int | None = None,
    employee_id: int | None = None,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lists payslips. HR/Admin see all; employees see only their own."""
    if user["role"] not in ADMIN_HR:
        employee_id = user["employee_id"]
    return payroll_service.list_payslips(db, period_id=period_id, employee_id=employee_id)


@router.get("/payslips/{payslip_id}", response_model=PayslipOut)
def get_payslip(
    payslip_id: int,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns a payslip with its deductions."""
    payslip = payroll_service.get_payslip(db, payslip_id)
    if user["role"] not in ADMIN_HR and payslip["employee_id"] != user["employee_id"]:
        from app.errors import ForbiddenError
        raise ForbiddenError("You can only view your own payslip")
    return payslip


# --- Deduction Types ---


@router.get("/deductions", response_model=list[DeductionTypeOut])
def list_deductions(
    db: Session = Depends(get_db),
    _user: dict = Depends(require_role(*ADMIN_HR)),
):
    """Lists all deduction types."""
    return payroll_service.list_deduction_types(db)


@router.post("/deductions", response_model=DeductionTypeOut, status_code=status.HTTP_201_CREATED)
def create_deduction(
    body: DeductionTypeCreate,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_role(*ADMIN_HR)),
):
    """Creates a new deduction type."""
    return payroll_service.create_deduction_type(db, body.model_dump())


@router.put("/deductions/{deduction_type_id}", response_model=DeductionTypeOut)
def update_deduction(
    deduction_type_id: int,
    body: DeductionTypeUpdate,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_role(*ADMIN_HR)),
):
    """Updates a deduction type."""
    return payroll_service.update_deduction_type(db, deduction_type_id, body.model_dump(exclude_unset=True))


@router.delete("/deductions/{deduction_type_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_deduction(
    deduction_type_id: int,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_role("Admin")),
):
    """Deletes a deduction type (Admin only)."""
    payroll_service.delete_deduction_type(db, deduction_type_id)
    return None