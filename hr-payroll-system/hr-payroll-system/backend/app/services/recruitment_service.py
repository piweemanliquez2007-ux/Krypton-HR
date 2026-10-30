from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.database import transaction
from app.errors import BusinessRuleError, NotFoundError
from app.repositories import recruitment_repository
from app.services.ai_service import extract_text_from_pdf, parse_resume_with_gemini


def parse_and_save_resume(
    db: Session,
    file_bytes: bytes,
    filename: str,
    job_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Extracts text from the uploaded resume file, passes it to Google Gemini,
    and inserts the candidate into the database inside a transaction.
    """
    if filename.lower().endswith(".pdf"):
        resume_text = extract_text_from_pdf(file_bytes)
    else:
        try:
            resume_text = file_bytes.decode("utf-8", errors="ignore")
        except Exception:
            resume_text = ""

    if not resume_text or len(resume_text.strip()) < 20:
        raise BusinessRuleError("Unable to extract readable text from the uploaded resume.")

    # Call AI Parser
    parsed = parse_resume_with_gemini(resume_text)

    first_name = (parsed.get("first_name") or "Unknown").strip()
    last_name = (parsed.get("last_name") or "Candidate").strip()
    email = (parsed.get("email") or f"applicant_{filename.replace(' ', '_')}@example.com").strip()
    phone = parsed.get("phone")
    education = parsed.get("education")
    years_exp = float(parsed.get("years_experience") or 0.0)
    skills = parsed.get("skills") or []

    with transaction(db):
        app_id = recruitment_repository.insert_applicant(
            db=db,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            education=education,
            years_experience=years_exp,
            resume_file=filename,
            resume_text=resume_text,
            source="ai_parsed",
        )

        for s in skills:
            s_name = s.get("name") if isinstance(s, dict) else str(s)
            s_conf = s.get("confidence", 0.8) if isinstance(s, dict) else 0.8
            if s_name:
                skill_id = recruitment_repository.get_or_create_skill(db, s_name)
                recruitment_repository.link_applicant_skill(db, app_id, skill_id, s_conf)

        application_id = None
        if job_id:
            application_id = recruitment_repository.create_application(
                db=db,
                applicant_id=app_id,
                job_id=job_id,
                notes=f"Auto-applied via AI Resume Parser for {filename}",
            )

    return {
        "applicant_id": app_id,
        "application_id": application_id,
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "phone": phone,
        "education": education,
        "years_experience": years_exp,
        "skills": skills,
        "message": f"Resume for {first_name} {last_name} successfully parsed and stored in database.",
    }


def get_applicants(db: Session) -> List[Dict[str, Any]]:
    return recruitment_repository.list_applicants(db)


def get_jobs(db: Session) -> List[Dict[str, Any]]:
    return recruitment_repository.list_jobs(db)


def hire_applicant(
    db: Session,
    applicant_id: int,
    job_id: int,
    base_salary: float,
    hire_date: Optional[str] = None,
) -> Dict[str, Any]:
    from datetime import date
    h_date = hire_date or str(date.today())
    with transaction(db):
        app_id = recruitment_repository.get_or_create_application(db, applicant_id, job_id)
        # sp_hire_applicant requires application to be at 'offer' stage
        recruitment_repository.set_application_status(db, app_id, "offer")
        new_emp_id = recruitment_repository.hire_applicant(db, app_id, base_salary, h_date)

    return {
        "status": "success",
        "new_employee_id": new_emp_id,
        "message": f"Candidate successfully hired as Employee #{new_emp_id}!",
    }


def reject_applicant(
    db: Session,
    applicant_id: int,
    job_id: Optional[int] = 1,
    reason: Optional[str] = "Candidate did not meet current requirements",
) -> Dict[str, Any]:
    with transaction(db):
        app_id = recruitment_repository.get_or_create_application(db, applicant_id, job_id or 1)
        recruitment_repository.set_application_status(db, app_id, "rejected", reason)

    return {
        "status": "success",
        "message": "Candidate application has been rejected.",
    }
