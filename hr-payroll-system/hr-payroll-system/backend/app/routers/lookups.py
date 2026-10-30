"""ROUTER layer: HTTP only. Validate input, check the role, call ONE service function."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import get_current_user
from app.services import lookup_service

router = APIRouter(prefix="/lookups", tags=["Lookups"], dependencies=[Depends(get_current_user)])


@router.get("/departments")
def departments(db: Session = Depends(get_db)):
    return lookup_service.departments(db)


@router.get("/positions")
def positions(db: Session = Depends(get_db)):
    return lookup_service.positions(db)


@router.get("/leave-types")
def leave_types(db: Session = Depends(get_db)):
    return lookup_service.leave_types(db)
