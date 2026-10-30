from datetime import datetime, timedelta, timezone
import logging
import re

import bcrypt
import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings
from app.errors import ForbiddenError, UnauthorizedError, BusinessRuleError

logger = logging.getLogger("hr_payroll.security")

bearer_scheme = HTTPBearer()

ADMIN_HR = ("Admin", "HR")


# ---------------------------------------------------------------- passwords
def hash_password(plain: str) -> str:
    """Hashes a password using bcrypt with a random salt."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Works with the $2a$ hashes created by pgcrypto in 02_seed.sql."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def validate_password_strength(password: str) -> None:
    """
    Enforces password policy:
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character
    """
    if not password or len(password) < 8:
        raise BusinessRuleError("Password must be at least 8 characters long.")
    if not re.search(r"[A-Z]", password):
        raise BusinessRuleError("Password must contain at least one uppercase letter.")
    if not re.search(r"[a-z]", password):
        raise BusinessRuleError("Password must contain at least one lowercase letter.")
    if not re.search(r"\d", password):
        raise BusinessRuleError("Password must contain at least one digit.")
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>_\-+=\[\]\\;\'\/~`]", password):
        raise BusinessRuleError("Password must contain at least one special character.")


# --------------------------------------------------------------------- JWT
def create_access_token(user_id: int, role: str, employee_id: int | None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": str(user_id),   # JWT subject must be a string
        "role": role,
        "emp": employee_id,
        "exp": expire,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    logger.info("JWT token created for user_id=%d role=%s", user_id, role)
    return token


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    """Reads the 'Authorization: Bearer <token>' header and returns the logged-in user."""
    try:
        payload = jwt.decode(
            creds.credentials, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except jwt.ExpiredSignatureError:
        logger.warning("Expired token attempt")
        raise UnauthorizedError("Token expired, please log in again")
    except jwt.InvalidTokenError:
        logger.warning("Invalid token attempt")
        raise UnauthorizedError("Invalid token")

    return {
        "user_id": int(payload["sub"]),
        "role": payload["role"],
        "employee_id": payload.get("emp"),
    }


# -------------------------------------------------------------------- RBAC
def require_role(*allowed_roles: str):
    """
    Route guard. Example:
        user: dict = Depends(require_role("Admin", "HR"))
    """

    def checker(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] not in allowed_roles:
            logger.warning(
                "Access denied: user_id=%d role=%s attempted to access protected resource",
                user["user_id"], user["role"]
            )
            raise ForbiddenError("You do not have permission to do this")
        return user

    return checker


# ----------------------------------------------------------------- audit log
def audit_log(action: str, user: dict, details: str = "") -> None:
    """Logs security-relevant actions for compliance and investigation."""
    logger.info(
        "AUDIT: user_id=%d role=%s action=%s details=%s",
        user.get("user_id", "?"),
        user.get("role", "?"),
        action,
        details,
    )
