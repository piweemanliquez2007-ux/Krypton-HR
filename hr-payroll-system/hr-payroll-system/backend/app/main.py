from fastapi import Depends, FastAPI, Request
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.errors import register_error_handlers
from app.middleware import rate_limit_middleware, security_headers_middleware
from app.routers import (attendance, auth, chatbot, employees, leaves, lookups,
                        payroll, qr_attendance, recruitment)

app = FastAPI(title="HR & Payroll API", version="1.2.0")

# Security middleware (order matters: rate limit first, then headers, then CORS)
app.middleware("http")(rate_limit_middleware)
app.middleware("http")(security_headers_middleware)

# CORS: allow development frontend origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Device-Id", "X-Device-Secret"],
)

# Turns our AppError subclasses into clean JSON responses ({"detail": "..."})
register_error_handlers(app)

app.include_router(auth.router)
app.include_router(employees.router)
app.include_router(lookups.router)
app.include_router(attendance.router)
app.include_router(qr_attendance.router)
app.include_router(leaves.router)
app.include_router(payroll.router)
app.include_router(chatbot.router)
app.include_router(recruitment.router)


@app.get("/", include_in_schema=False)
def root():
    """Redirect root visitors directly to interactive Swagger docs."""
    return RedirectResponse(url="/docs")


@app.get("/health", tags=["Health"])
def health(db: Session = Depends(get_db)):
    """If this returns 'connected', your database settings in .env are correct."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}
