"""ROUTER layer: HTTP only. Validate input, check the role, call ONE service function."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.errors import BusinessRuleError
from app.schemas.auth import ChangePasswordRequest, LoginRequest, TokenResponse
from app.security import get_current_user
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    return auth_service.login(db, body.username, body.password)


@router.post("/change-password")
def change_password(
    body: ChangePasswordRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Allows a logged-in user to change their own password."""
    return auth_service.change_password(db, user["user_id"], body.old_password, body.new_password)


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    """Returns who the token belongs to. Handy for the frontend after a page refresh."""
    return user
