"""REPOSITORY layer: SQL only. No business rules, no HTTP, no commit (services commit)."""
from sqlalchemy import text
from sqlalchemy.orm import Session

BASE_SELECT = """
    SELECT e.employee_id, e.employee_no, e.first_name, e.last_name, e.email, e.phone,
           e.birth_date, e.hire_date, e.position_id, p.title AS position,
           d.department_id, d.name AS department, e.manager_id, e.base_salary, e.status
      FROM employees e
      JOIN positions   p ON p.position_id   = e.position_id
      JOIN departments d ON d.department_id = p.department_id
"""

# Columns that an update is allowed to change (a whitelist, so nothing else can be touched)
UPDATABLE_COLUMNS = {
    "first_name", "last_name", "email", "phone", "birth_date", "hire_date",
    "position_id", "manager_id", "base_salary", "status",
}


def find_by_id(db: Session, employee_id: int) -> dict | None:
    row = db.execute(
        text(BASE_SELECT + " WHERE e.employee_id = :id"), {"id": employee_id}
    ).mappings().first()
    return dict(row) if row else None


def search(
    db: Session,
    *,
    search: str | None = None,
    department_id: int | None = None,
    status: str | None = None,
    limit: int = 50,
    skip: int = 0,
) -> list[dict]:
    # The f-string below only joins fixed, hard-coded fragments.
    # User input always travels as bound parameters (:q, :dept, ...), never inside the SQL text.
    conditions: list[str] = []
    params: dict = {"limit": limit, "skip": skip}

    if search:
        conditions.append("(e.first_name ILIKE :q OR e.last_name ILIKE :q OR e.email ILIKE :q)")
        params["q"] = f"%{search}%"
    if department_id is not None:
        conditions.append("d.department_id = :dept")
        params["dept"] = department_id
    if status:
        conditions.append("e.status = :status")
        params["status"] = status

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = db.execute(
        text(f"{BASE_SELECT} {where} ORDER BY e.employee_id LIMIT :limit OFFSET :skip"), params
    ).mappings().all()
    return [dict(r) for r in rows]


def insert(db: Session, data: dict) -> int:
    """Returns the new employee_id. (A DB trigger also creates the leave balances.)"""
    return db.execute(
        text(
            """
            INSERT INTO employees (first_name, last_name, email, phone, birth_date,
                                   hire_date, position_id, manager_id, base_salary)
            VALUES (:first_name, :last_name, :email, :phone, :birth_date,
                    COALESCE(:hire_date, CURRENT_DATE), :position_id, :manager_id, :base_salary)
            RETURNING employee_id
            """
        ),
        data,
    ).scalar_one()


def update(db: Session, employee_id: int, changes: dict) -> bool:
    columns = {col: val for col, val in changes.items() if col in UPDATABLE_COLUMNS}
    if not columns:
        return False
    # Column names come from the whitelist above; values are bound parameters.
    set_clause = ", ".join(f"{col} = :{col}" for col in columns)
    result = db.execute(
        text(f"UPDATE employees SET {set_clause} WHERE employee_id = :id"),
        {**columns, "id": employee_id},
    )
    return result.rowcount > 0


def set_status(db: Session, employee_id: int, new_status: str) -> bool:
    result = db.execute(
        text("UPDATE employees SET status = :status WHERE employee_id = :id"),
        {"status": new_status, "id": employee_id},
    )
    return result.rowcount > 0
