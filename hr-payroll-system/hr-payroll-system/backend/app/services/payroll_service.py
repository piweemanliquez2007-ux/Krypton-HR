"""SERVICE layer: Business rules. Calls repositories, manages transactions."""
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.database import transaction
from app.errors import BusinessRuleError, NotFoundError
from app.repositories import payroll_repository


def list_periods(db: Session) -> List[Dict[str, Any]]:
    return payroll_repository.list_periods(db)


def get_period(db: Session, period_id: int) -> Dict[str, Any]:
    period = payroll_repository.get_period(db, period_id)
    if not period:
        raise NotFoundError(f"Payroll period {period_id} not found")
    return period


def create_period(db: Session, data: Dict[str, Any]) -> Dict[str, Any]:
    if data["end_date"] < data["start_date"]:
        raise BusinessRuleError("End date must be on or after start date")
    with transaction(db):
        period_id = payroll_repository.create_period(db, data)
    return payroll_repository.get_period(db, period_id)


def update_period(db: Session, period_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    period = get_period(db, period_id)
    if period["status"] != "open":
        raise BusinessRuleError(f"Cannot modify period with status '{period['status']}'")
    if "start_date" in data and "end_date" in data:
        if data["end_date"] < data["start_date"]:
            raise BusinessRuleError("End date must be on or after start date")
    elif "start_date" in data:
        if data["start_date"] > period["end_date"]:
            raise BusinessRuleError("Start date must be on or before end date")
    elif "end_date" in data:
        if data["end_date"] < period["start_date"]:
            raise BusinessRuleError("End date must be on or after start date")
    with transaction(db):
        payroll_repository.update_period(db, period_id, data)
    return payroll_repository.get_period(db, period_id)


def generate_payroll(db: Session, period_id: int) -> Dict[str, Any]:
    period = get_period(db, period_id)
    if period["status"] != "open":
        raise BusinessRuleError(f"Period is '{period['status']}' and cannot be regenerated")
    with transaction(db):
        payroll_repository.call_generate_payroll(db, period_id)
    return {"status": "success", "message": f"Payroll generated for period {period['period_name']}"}


def list_payslips(
    db: Session, period_id: Optional[int] = None, employee_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    return payroll_repository.list_payslips(db, period_id, employee_id)


def get_payslip(db: Session, payslip_id: int) -> Dict[str, Any]:
    payslip = payroll_repository.get_payslip(db, payslip_id)
    if not payslip:
        raise NotFoundError(f"Payslip {payslip_id} not found")
    payslip["deductions"] = payroll_repository.get_payslip_deductions(db, payslip_id)
    return payslip


def list_deduction_types(db: Session) -> List[Dict[str, Any]]:
    return payroll_repository.list_deduction_types(db)


def create_deduction_type(db: Session, data: Dict[str, Any]) -> Dict[str, Any]:
    if data["calc_method"] == "percent" and data["rate"] > 100:
        raise BusinessRuleError("Percentage rate cannot exceed 100%")
    with transaction(db):
        dt_id = payroll_repository.create_deduction_type(db, data)
    return {"deduction_type_id": dt_id, **data}


def update_deduction_type(db: Session, deduction_type_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    existing = payroll_repository.list_deduction_types(db)
    if not any(d["deduction_type_id"] == deduction_type_id for d in existing):
        raise NotFoundError(f"Deduction type {deduction_type_id} not found")
    if "rate" in data and data["rate"] is not None:
        if "calc_method" in data and data["calc_method"] == "percent" and data["rate"] > 100:
            raise BusinessRuleError("Percentage rate cannot exceed 100%")
        elif "calc_method" not in data:
            existing_dt = next(d for d in existing if d["deduction_type_id"] == deduction_type_id)
            if existing_dt["calc_method"] == "percent" and data["rate"] > 100:
                raise BusinessRuleError("Percentage rate cannot exceed 100%")
    with transaction(db):
        payroll_repository.update_deduction_type(db, deduction_type_id, data)
    return {**data, "deduction_type_id": deduction_type_id}


def delete_deduction_type(db: Session, deduction_type_id: int) -> None:
    existing = payroll_repository.list_deduction_types(db)
    if not any(d["deduction_type_id"] == deduction_type_id for d in existing):
        raise NotFoundError(f"Deduction type {deduction_type_id} not found")
    with transaction(db):
        payroll_repository.delete_deduction_type(db, deduction_type_id)