"""REPOSITORY layer: SQL only. No business rules, no HTTP, no commit (services commit)."""
from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

BASE_SELECT = """
    SELECT a.attendance_id, a.employee_id,
           e.first_name || ' ' || e.last_name AS employee_name,
           a.work_date, a.time_in, a.time_out, a.hours_worked, a.overtime_hours, a.status
      FROM attendance a
      JOIN employees e ON e.employee_id = a.employee_id
"""

UPDATABLE_COLUMNS = {"time_in", "time_out", "status"}


def find_by_id(db: Session, attendance_id: int) -> dict | None:
    row = db.execute(
        text(BASE_SELECT + " WHERE a.attendance_id = :id"), {"id": attendance_id}
    ).mappings().first()
    return dict(row) if row else None


def find_by_employee_and_date(db: Session, employee_id: int, work_date: date) -> dict | None:
    row = db.execute(
        text(BASE_SELECT + " WHERE a.employee_id = :emp AND a.work_date = :d"),
        {"emp": employee_id, "d": work_date},
    ).mappings().first()
    return dict(row) if row else None


def search(
    db: Session,
    *,
    employee_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 50,
    skip: int = 0,
) -> list[dict]:
    # Only fixed fragments are joined below; user values are bound parameters.
    conditions: list[str] = []
    params: dict = {"limit": limit, "skip": skip}
    if employee_id is not None:
        conditions.append("a.employee_id = :emp")
        params["emp"] = employee_id
    if date_from is not None:
        conditions.append("a.work_date >= :date_from")
        params["date_from"] = date_from
    if date_to is not None:
        conditions.append("a.work_date <= :date_to")
        params["date_to"] = date_to

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = db.execute(
        text(f"{BASE_SELECT} {where} ORDER BY a.work_date DESC, a.employee_id LIMIT :limit OFFSET :skip"),
        params,
    ).mappings().all()
    return [dict(r) for r in rows]


def insert(db: Session, data: dict) -> int:
    """hours_worked / overtime_hours are filled in by the database trigger."""
    return db.execute(
        text(
            """
            INSERT INTO attendance (employee_id, work_date, time_in, time_out, status)
            VALUES (:employee_id, :work_date, :time_in, :time_out, :status)
            RETURNING attendance_id
            """
        ),
        data,
    ).scalar_one()


def update(db: Session, attendance_id: int, changes: dict) -> bool:
    columns = {c: v for c, v in changes.items() if c in UPDATABLE_COLUMNS}
    if not columns:
        return False
    set_clause = ", ".join(f"{c} = :{c}" for c in columns)   # names come from the whitelist
    result = db.execute(
        text(f"UPDATE attendance SET {set_clause} WHERE attendance_id = :id"),
        {**columns, "id": attendance_id},
    )
    return result.rowcount > 0


def delete(db: Session, attendance_id: int) -> bool:
    result = db.execute(text("DELETE FROM attendance WHERE attendance_id = :id"), {"id": attendance_id})
    return result.rowcount > 0
