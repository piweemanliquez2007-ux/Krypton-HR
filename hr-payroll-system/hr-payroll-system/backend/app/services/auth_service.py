"""SERVICE layer: business rules and transactions. No SQL here, no HTTP objects."""
from sqlalchemy.orm import Session

from app.database import transaction
from app.errors import UnauthorizedError
from app.repositories import user_repository
from app.security import create_access_token, verify_password, validate_password_strength, audit_log


def login(db: Session, username: str, password: str) -> dict:
    user = user_repository.find_by_username(db, username)

    # Same message for every failure so attackers can't tell which usernames exist
    if user is None or not user["is_active"] or not verify_password(password, user["password_hash"]):
        audit_log("LOGIN_FAILED", {"user_id": 0, "role": "unknown"}, f"username={username}")
        raise UnauthorizedError("Invalid username or password")

    with transaction(db):
        user_repository.touch_last_login(db, user["user_id"])

    audit_log("LOGIN_SUCCESS", {"user_id": user["user_id"], "role": user["role_name"]}, f"username={username}")

    return {
        "access_token": create_access_token(user["user_id"], user["role_name"], user["employee_id"]),
        "user_id": user["user_id"],
        "username": user["username"],
        "role": user["role_name"],
        "employee_id": user["employee_id"],
    }


def change_password(db: Session, user_id: int, old_password: str, new_password: str) -> dict:
    """Allows a logged-in user to change their own password."""
    validate_password_strength(new_password)

    user = user_repository.find_by_id(db, user_id)
    if not user or not verify_password(old_password, user["password_hash"]):
        raise UnauthorizedError("Current password is incorrect")

    new_hash = __import__("app.security", fromlist=["hash_password"]).hash_password(new_password)
    with transaction(db):
        user_repository.update_password(db, user_id, new_hash)

    audit_log("PASSWORD_CHANGE", {"user_id": user_id, "role": user["role_name"]}, "password updated")
    return {"message": "Password changed successfully"}


    row = db.execute(
        text(
            """
            SELECT u.user_id, u.username, r.role_name, u.employee_id,
                   e.first_name, e.last_name
              FROM users u
              JOIN roles r ON r.role_id = u.role_id
              LEFT JOIN employees e ON e.employee_id = u.employee_id
             WHERE u.employee_id = :eid AND u.is_active
            ORDER BY u.user_id
            LIMIT 1
            """
        ),
        {"eid": employee_id},
    ).mappings().first()
    if not row:
        from app.errors import UnauthorizedError
        raise UnauthorizedError("No active user account linked to this employee")

    token = jwt.encode(
        {
            "sub": str(row["user_id"]),
            "username": row["username"],
            "role": row["role_name"],
            "emp": row["employee_id"],
            "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes),
            "iat": datetime.now(timezone.utc),
            "jti": str(uuid.uuid4()),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": row["user_id"],
        "username": row["username"],
        "role": row["role_name"],
        "employee_id": row["employee_id"],
        "full_name": f"{row['first_name'] or ''} {row['last_name'] or ''}".strip() or row["username"],
    }

