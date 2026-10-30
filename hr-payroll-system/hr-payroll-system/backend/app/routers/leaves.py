"""ROUTER layer: HTTP only. Validate input, check the role, call ONE service function."""
from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.leave import LeaveBalanceOut, LeaveOut, LeaveRequestCreate, LeaveReview
from app.security import ADMIN_HR, get_current_user, require_role
from app.services import leave_service

router = APIRouter(prefix="/leaves", tags=["Leaves"])


@router.post("", response_model=LeaveOut, status_code=status.HTTP_201_CREATED)
def create_leave_request(
    body: LeaveRequestCreate, user: dict = Depends(get_current_user), db: Session = Depends(get_db)
):
    return leave_service.create_leave_request(db, body, user)


@router.get("", response_model=list[LeaveOut])
def list_leaves(
    employee_id: int | None = None,
    status_filter: Literal["pending", "approved", "rejected", "cancelled"] | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return leave_service.list_leaves(
        db, user, employee_id=employee_id, status=status_filter, limit=limit, skip=skip
    )


# NOTE: /balances must be declared BEFORE /{request_id}.
@router.get("/balances", response_model=list[LeaveBalanceOut])
def leave_balances(
    employee_id: int | None = None, user: dict = Depends(get_current_user), db: Session = Depends(get_db)
):
    return leave_service.get_balances(db, user, employee_id)


@router.get("/{request_id}", response_model=LeaveOut)
def get_leave(request_id: int, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    return leave_service.get_leave(db, request_id, user)


@router.post("/{request_id}/review", response_model=LeaveOut)
def review_leave(
    request_id: int, body: LeaveReview,
    user: dict = Depends(require_role(*ADMIN_HR)), db: Session = Depends(get_db),
):
    return leave_service.review_leave(db, request_id, body.decision, user)


@router.post("/{request_id}/cancel", response_model=LeaveOut)
def cancel_leave(request_id: int, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    return leave_service.cancel_leave(db, request_id, user)
