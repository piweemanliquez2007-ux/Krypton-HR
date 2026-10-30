"""SERVICE layer: business rules and transactions. No SQL here, no HTTP objects."""
from sqlalchemy.orm import Session

from app.repositories import lookup_repository


def departments(db: Session) -> list[dict]:
    return lookup_repository.list_departments(db)


def positions(db: Session) -> list[dict]:
    return lookup_repository.list_positions(db)


def leave_types(db: Session) -> list[dict]:
    return lookup_repository.list_leave_types(db)
