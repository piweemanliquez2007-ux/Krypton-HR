"""ROUTER layer: HTTP only."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import get_current_user
from app.services import chatbot_service

router = APIRouter(prefix="/chatbot", tags=["Chatbot"])


@router.post("/chat")
def chat(
    body: dict,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """
    AI-powered HR chatbot.
    Body: {"message": "...", "history": [{"user": "...", "assistant": "..."}]}
    """
    message = body.get("message", "")
    history = body.get("history", [])
    return chatbot_service.chat(db, message, history)