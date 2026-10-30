"""REPOSITORY layer: SQL only. No business rules, no HTTP, no commit (services commit)."""
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session


def list_periods(db: Session) -> List[Dict[str, Any]]:
    """Returns all payroll periods."""
    rows = db.execute(
        text(
            """
            SELECT period_id, period_name, start_date, end_date, pay_date, status
              FROM payroll_periods
             ORDER BY period_id DESC
            """
        )
    ).mappings().all()
    return [dict(r) for r in rows]


def get_period(db: Session, period_id: int) -> Optional[Dict[str, Any]]:
    """Returns a single payroll period by ID."""
    row = db.execute(
        text(
            """
            SELECT period_id, period_name, start_date, end_date, pay_date, status
              FROM payroll_periods
             WHERE period_id = :id
            """
        ),
        {"id": period_id},
    ).mappings().first()
    return dict(row) if row else None


def create_period(db: Session, data: Dict[str, Any]) -> int:
    """Creates a new payroll period."""
    return db.execute(
        text(
            """
            INSERT INTO payroll_periods (period_name, start_date, end_date, pay_date, status)
            VALUES (:period_name, :start_date, :end_date, :pay_date, 'open')
            RETURNING period_id
            """
        ),
        data,
    ).scalar_one()


def update_period(db: Session, period_id: int, data: Dict[str, Any]) -> None:
    """Updates a payroll period."""
    set_clauses = []
    params = {"id": period_id}
    for key, value in data.items():
        if value is not None:
            set_clauses.append(f"{key} = :{key}")
            params[key] = value
    if not set_clauses:
        return
    db.execute(
        text(f"UPDATE payroll_periods SET {', '.join(set_clauses)} WHERE period_id = :id"),
        params,
    )


def call_generate_payroll(db: Session, period_id: int) -> None:
    """Calls stored procedure sp_generate_payroll."""
    db.execute(text("CALL sp_generate_payroll(:pid)"), {"pid": period_id})


def list_payslips(
    db: Session, period_id: int | None = None, employee_id: int | None = None
) -> List[Dict[str, Any]]:
    """Returns payslips with employee and period details."""
    conditions = []
    params: Dict[str, Any] = {}
    if period_id is not None:
        conditions.append("ps.period_id = :period_id")
        params["period_id"] = period_id
    if employee_id is not None:
        conditions.append("ps.employee_id = :employee_id")
        params["employee_id"] = employee_id

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    sql = f"""
        SELECT ps.payslip_id, ps.employee_id, e.employee_no,
               e.first_name || ' ' || e.last_name AS employee_name,
               d.name AS department,
               ps.period_id, pp.period_name,
               ps.days_paid, ps.overtime_hours,
               ps.basic_pay, ps.overtime_pay, ps.gross_pay,
               ps.total_deductions, ps.net_pay,
               ps.generated_at
          FROM payslips ps
          JOIN employees e ON e.employee_id = ps.employee_id
          JOIN payroll_periods pp ON pp.period_id = ps.period_id
          JOIN positions p ON p.position_id = e.position_id
          JOIN departments d ON d.department_id = p.department_id
          {where}
         ORDER BY ps.generated_at DESC, e.employee_no
    """
    rows = db.execute(text(sql), params).mappings().all()
    return [dict(r) for r in rows]


def get_payslip(db: Session, payslip_id: int) -> Optional[Dict[str, Any]]:
    """Returns a single payslip with deductions."""
    row = db.execute(
        text(
            """
            SELECT ps.payslip_id, ps.employee_id, e.employee_no,
                   e.first_name || ' ' || e.last_name AS employee_name,
                   d.name AS department,
                   ps.period_id, pp.period_name,
                   ps.days_paid, ps.overtime_hours,
                   ps.basic_pay, ps.overtime_pay, ps.gross_pay,
                   ps.total_deductions, ps.net_pay,
                   ps.generated_at
              FROM payslips ps
              JOIN employees e ON e.employee_id = ps.employee_id
              JOIN payroll_periods pp ON pp.period_id = ps.period_id
              JOIN positions p ON p.position_id = e.position_id
              JOIN departments d ON d.department_id = p.department_id
             WHERE ps.payslip_id = :id
            """
        ),
        {"id": payslip_id},
    ).mappings().first()
    return dict(row) if row else None


def get_payslip_deductions(db: Session, payslip_id: int) -> List[Dict[str, Any]]:
    """Returns deductions for a specific payslip."""
    rows = db.execute(
        text(
            """
            SELECT pd.payslip_id, pd.deduction_type_id, dt.name, dt.calc_method,
                   dt.rate, pd.amount
              FROM payslip_deductions pd
              JOIN deduction_types dt ON dt.deduction_type_id = pd.deduction_type_id
             WHERE pd.payslip_id = :pid
             ORDER BY dt.name
            """
        ),
        {"pid": payslip_id},
    ).mappings().all()
    return [dict(r) for r in rows]


def list_deduction_types(db: Session) -> List[Dict[str, Any]]:
    """Returns all deduction types."""
    rows = db.execute(
        text(
            """
            SELECT deduction_type_id, name, calc_method, rate, max_amount, is_active
              FROM deduction_types
             ORDER BY deduction_type_id
            """
        )
    ).mappings().all()
    return [dict(r) for r in rows]


def create_deduction_type(db: Session, data: Dict[str, Any]) -> int:
    """Creates a new deduction type."""
    return db.execute(
        text(
            """
            INSERT INTO deduction_types (name, calc_method, rate, max_amount, is_active)
            VALUES (:name, :calc_method, :rate, :max_amount, :is_active)
            RETURNING deduction_type_id
            """
        ),
        data,
    ).scalar_one()


def update_deduction_type(db: Session, deduction_type_id: int, data: Dict[str, Any]) -> None:
    """Updates a deduction type."""
    set_clauses = []
    params = {"id": deduction_type_id}
    for key, value in data.items():
        if value is not None:
            set_clauses.append(f"{key} = :{key}")
            params[key] = value
    if not set_clauses:
        return
    db.execute(
        text(f"UPDATE deduction_types SET {', '.join(set_clauses)} WHERE deduction_type_id = :id"),
        params,
    )


def delete_deduction_type(db: Session, deduction_type_id: int) -> None:
    """Deletes a deduction type."""
    db.execute(
        text("DELETE FROM deduction_types WHERE deduction_type_id = :id"),
        {"id": deduction_type_id},
    )