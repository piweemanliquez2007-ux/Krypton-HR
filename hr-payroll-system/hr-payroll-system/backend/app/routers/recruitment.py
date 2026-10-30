from typing import Optional
from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import ADMIN_HR, require_role
from app.services import recruitment_service

router = APIRouter(prefix="/recruitment", tags=["Recruitment & AI"])


@router.post("/parse-resume")
async def parse_resume(
    file: UploadFile = File(...),
    job_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    user: dict = Depends(require_role(*ADMIN_HR)),
):
    """
    AI Integration endpoint:
    Upload a candidate resume (PDF or text) to extract contact details,
    education, experience, and skills, saving directly into relational tables.
    """
    file_bytes = await file.read()
    return recruitment_service.parse_and_save_resume(
        db=db,
        file_bytes=file_bytes,
        filename=file.filename or "resume.pdf",
        job_id=job_id,
    )


@router.get("/applicants")
def list_applicants(
    db: Session = Depends(get_db),
    user: dict = Depends(require_role(*ADMIN_HR)),
):
    """Lists all applicants and their parsed skills from the relational tables."""
    return recruitment_service.get_applicants(db)


@router.get("/jobs")
def list_jobs(db: Session = Depends(get_db)):
    """Lists open job postings."""
    return recruitment_service.get_jobs(db)


from pydantic import BaseModel


class HireRequest(BaseModel):
    applicant_id: int
    job_id: int = 1
    base_salary: float
    hire_date: Optional[str] = None


class RejectRequest(BaseModel):
    applicant_id: int
    job_id: Optional[int] = 1
    reason: Optional[str] = None


@router.post("/hire")
def hire(
    req: HireRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role(*ADMIN_HR)),
):
    """Hires an applicant through stored procedure sp_hire_applicant."""
    return recruitment_service.hire_applicant(
        db=db,
        applicant_id=req.applicant_id,
        job_id=req.job_id,
        base_salary=req.base_salary,
        hire_date=req.hire_date,
    )


@router.post("/reject")
def reject(
    req: RejectRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role(*ADMIN_HR)),
):
    """Marks an applicant's application as rejected."""
    return recruitment_service.reject_applicant(
        db=db,
        applicant_id=req.applicant_id,
        job_id=req.job_id,
        reason=req.reason,
    )
