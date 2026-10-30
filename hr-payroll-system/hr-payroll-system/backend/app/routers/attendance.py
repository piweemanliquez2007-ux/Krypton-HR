"""ROUTER layer: HTTP only. Validate input, check the role, call ONE service function."""
from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.attendance import AttendanceCreate, AttendanceOut, AttendanceUpdate
from app.security import ADMIN_HR, get_current_user, require_role
from app.services import attendance_service

router = APIRouter(prefix="/attendance", tags=["Attendance"])


@router.post("/clock-in", response_model=AttendanceOut, status_code=status.HTTP_201_CREATED)
def clock_in(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    return attendance_service.clock_in(db, user)


@router.post("/clock-out", response_model=AttendanceOut)
def clock_out(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    return attendance_service.clock_out(db, user)


@router.get("", response_model=list[AttendanceOut])
def list_attendance(
    employee_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return attendance_service.list_attendance(
        db, user, employee_id=employee_id, date_from=date_from, date_to=date_to, limit=limit, skip=skip
    )


@router.get("/{attendance_id}", response_model=AttendanceOut)
def get_attendance(attendance_id: int, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    return attendance_service.get_attendance(db, attendance_id, user)


@router.post("", response_model=AttendanceOut, status_code=status.HTTP_201_CREATED)
def create_attendance(
    body: AttendanceCreate, db: Session = Depends(get_db), _user: dict = Depends(require_role(*ADMIN_HR))
):
    return attendance_service.create_attendance(db, body)


@router.put("/{attendance_id}", response_model=AttendanceOut)
def update_attendance(
    attendance_id: int, body: AttendanceUpdate,
    db: Session = Depends(get_db), _user: dict = Depends(require_role(*ADMIN_HR)),
):
    return attendance_service.update_attendance(db, attendance_id, body)


@router.delete("/{attendance_id}")
def delete_attendance(
    attendance_id: int, db: Session = Depends(get_db), _user: dict = Depends(require_role(*ADMIN_HR))
):
    return attendance_service.delete_attendance(db, attendance_id)
