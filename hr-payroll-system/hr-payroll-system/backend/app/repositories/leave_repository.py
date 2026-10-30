"""REPOSITORY layer: SQL only. No business rules, no HTTP, no commit (services commit)."""
from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

BASE_SELECT = """
    SELECT lr.request_id, lr.employee_id,
           e.first_name || ' ' || e.last_name AS employee_name,
           lr.leave_type_id, lt.name AS leave_type,
           lr.start_date, lr.end_date, lr.days_requested, lr.reason, lr.status,
           lr.reviewed_by, lr.reviewed_at, lr.created_at
      FROM leave_requests lr
      JOIN employees   e  ON e.employee_id    = lr.employee_id
      JOIN leave_types lt ON lt.leave_type_id = lr.leave_type_id
"""


def find_by_id(db: Session, request_id: int) -> dict | None:
    row = db.execute(
        text(BASE_SELECT + " WHERE lr.request_id = :id"), {"id": request_id}
    ).mappings().first()
    return dict(row) if row else None


def search(
    db: Session, *, employee_id: int | None = None, status: str | None = None,
    limit: int = 50, skip: int = 0,
) -> list[dict]:
    conditions: list[str] = []
    params: dict = {"limit": limit, "skip": skip}
    if employee_id is not None:
        conditions.append("lr.employee_id = :emp")
        params["emp"] = employee_id
    if status:
        conditions.append("lr.status = :status")
        params["status"] = status

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = db.execute(
        text(f"{BASE_SELECT} {where} ORDER BY lr.created_at DESC LIMIT :limit OFFSET :skip"), params
    ).mappings().all()
    return [dict(r) for r in rows]


def insert(db: Session, data: dict) -> int:
    return db.execute(
        text(
            """
            INSERT INTO leave_requests (employee_id, leave_type_id, start_date, end_date, reason)
            VALUES (:employee_id, :leave_type_id, :start_date, :end_date, :reason)
            RETURNING request_id
            """
        ),
        data,
    ).scalar_one()


def count_overlaps(db: Session, employee_id: int, start_date: date, end_date: date) -> int:
    return db.execute(
        text(
            """
            SELECT COUNT(*) FROM leave_requests
             WHERE employee_id = :emp
               AND status IN ('pending', 'approved')
               AND start_date <= :end_date
               AND end_date   >= :start_date
            """
        ),
        {"emp": employee_id, "start_date": start_date, "end_date": end_date},
    ).scalar_one()


def call_review(db: Session, request_id: int, reviewer_user_id: int, decision: str) -> None:
    """Stored procedure checks the balance; a trigger then deducts the days."""
    db.execute(
        text("CALL sp_approve_leave(:req, :reviewer, :decision)"),
        {"req": request_id, "reviewer": reviewer_user_id, "decision": decision},
    )


def set_cancelled(db: Session, request_id: int) -> None:
    """A trigger gives the days back if the request had been approved."""
    db.execute(text("UPDATE leave_requests SET status = 'cancelled' WHERE request_id = :id"), {"id": request_id})


def balances(db: Session, employee_id: int, year: int) -> list[dict]:
    rows = db.execute(
        text(
            """
            SELECT lb.employee_id, lb.leave_type_id, lt.name AS leave_type, lb.leave_year,
                   lb.allocated_days, lb.used_days,
                   (lb.allocated_days - lb.used_days) AS remaining_days
              FROM leave_balances lb
              JOIN leave_types lt ON lt.leave_type_id = lb.leave_type_id
             WHERE lb.employee_id = :emp AND lb.leave_year = :year
             ORDER BY lt.name
            """
        ),
        {"emp": employee_id, "year": year},
    ).mappings().all()
    return [dict(r) for r in rows]
