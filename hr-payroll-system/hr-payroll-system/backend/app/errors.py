import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError

logger = logging.getLogger("hr_payroll")


class AppError(Exception):
    """
    Base class for errors we raise on purpose. Services and security code raise these;
    the handler registered in main.py turns them into JSON: {"detail": "<message>"}.
    Nothing below the router layer needs to know about HTTP.
    """

    status_code = 500

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class UnauthorizedError(AppError):      # not logged in / bad token
    status_code = 401


class ForbiddenError(AppError):         # logged in, but the role is not allowed
    status_code = 403


class NotFoundError(AppError):
    status_code = 404


class ConflictError(AppError):          # duplicates (e.g. email already used)
    status_code = 409


class BusinessRuleError(AppError):      # a rule was broken (bad input, insufficient balance...)
    status_code = 400


class RateLimitError(AppError):         # too many scans (per kiosk / per employee)
    status_code = 429


class LockedError(AppError):            # credential locked after repeated failed PINs
    status_code = 423


def translate_db_error(exc: DBAPIError) -> AppError:
    """
    Convert a PostgreSQL error into one of our errors.
    Errors raised by our stored procedures (RAISE EXCEPTION, e.g. "Insufficient leave
    balance") have SQLSTATE P0001, and their message is shown to the client.
    """
    orig = getattr(exc, "orig", None)
    code = getattr(orig, "pgcode", None)
    diag = getattr(orig, "diag", None)
    message = getattr(diag, "message_primary", None) or "Database error"
    constraint = getattr(diag, "constraint_name", None)

    if code == "P0001":      # RAISE EXCEPTION inside a stored procedure
        return BusinessRuleError(message)
    if code == "23505":      # unique_violation
        return ConflictError(f"Duplicate value ({constraint}).")
    if code == "23503":      # foreign_key_violation
        return BusinessRuleError("A referenced record does not exist, or this record is still in use.")
    if code == "23502":      # not_null_violation
        return BusinessRuleError("A required field is missing or null.")
    if code == "23514":      # check_violation
        return BusinessRuleError(f"A value breaks a rule ({constraint}).")

    logger.error("Unexpected database error: %s", exc)     # full detail stays in the server log
    return AppError("Unexpected database error.")


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError):
        headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
        return JSONResponse(
            status_code=exc.status_code, content={"detail": exc.message}, headers=headers
        )
