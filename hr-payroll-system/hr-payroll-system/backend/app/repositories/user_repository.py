"""REPOSITORY layer: SQL only. No business rules, no HTTP, no commit (services commit)."""
from sqlalchemy import text
from sqlalchemy.orm import Session


def find_by_username(db: Session, username: str) -> dict | None:
    row = db.execute(
        text(
            """
            SELECT u.user_id, u.username, u.password_hash, u.is_active,
                   u.employee_id, r.role_name
              FROM users u
              JOIN roles r ON r.role_id = u.role_id
             WHERE u.username = :username
            """
        ),
        {"username": username},
    ).mappings().first()
    return dict(row) if row else None


def find_by_id(db: Session, user_id: int) -> dict | None:
    row = db.execute(
        text(
            """
            SELECT u.user_id, u.username, u.password_hash, u.is_active,
                   u.employee_id, r.role_name
              FROM users u
              JOIN roles r ON r.role_id = u.role_id
             WHERE u.user_id = :id
            """
        ),
        {"id": user_id},
    ).mappings().first()
    return dict(row) if row else None


def update_password(db: Session, user_id: int, password_hash: str) -> None:
    db.execute(
        text("UPDATE users SET password_hash = :hash WHERE user_id = :id"),
        {"hash": password_hash, "id": user_id},
    )


def touch_last_login(db: Session, user_id: int) -> None:
    db.execute(text("UPDATE users SET last_login = NOW() WHERE user_id = :id"), {"id": user_id})


def set_active_by_employee(db: Session, employee_id: int, is_active: bool) -> None:
    db.execute(
        text("UPDATE users SET is_active = :active WHERE employee_id = :id"),
        {"active": is_active, "id": employee_id},
    )
