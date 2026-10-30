"""REPOSITORY layer: SQL only. No business rules, no HTTP, no commit (services commit)."""
from sqlalchemy import text
from sqlalchemy.orm import Session


def list_departments(db: Session) -> list[dict]:
    rows = db.execute(text("SELECT department_id, name FROM departments ORDER BY name")).mappings().all()
    return [dict(r) for r in rows]


def list_positions(db: Session) -> list[dict]:
    rows = db.execute(
        text(
            """
            SELECT p.position_id, p.title, p.department_id, d.name AS department,
                   p.min_salary, p.max_salary
              FROM positions p
              JOIN departments d ON d.department_id = p.department_id
             ORDER BY d.name, p.title
            """
        )
    ).mappings().all()
    return [dict(r) for r in rows]


def get_position(db: Session, position_id: int) -> dict | None:
    row = db.execute(
        text("SELECT position_id, title, min_salary, max_salary FROM positions WHERE position_id = :id"),
        {"id": position_id},
    ).mappings().first()
    return dict(row) if row else None


def list_leave_types(db: Session) -> list[dict]:
    rows = db.execute(
        text("SELECT leave_type_id, name, default_days_per_year, is_paid FROM leave_types ORDER BY name")
    ).mappings().all()
    return [dict(r) for r in rows]
