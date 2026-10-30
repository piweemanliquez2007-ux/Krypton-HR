from typing import Any, Dict, List, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session


def get_or_create_skill(db: Session, skill_name: str) -> int:
    """Finds existing skill or inserts a new one, returning skill_id."""
    clean_name = skill_name.strip()[:60]
    row = db.execute(
        text("SELECT skill_id FROM skills WHERE LOWER(skill_name) = LOWER(:name)"),
        {"name": clean_name},
    ).fetchone()
    if row:
        return row[0]

    return db.execute(
        text("INSERT INTO skills (skill_name) VALUES (:name) RETURNING skill_id"),
        {"name": clean_name},
    ).scalar_one()


def insert_applicant(
    db: Session,
    first_name: str,
    last_name: str,
    email: str,
    phone: Optional[str],
    education: Optional[str],
    years_experience: float,
    resume_file: Optional[str],
    resume_text: str,
    source: str = "ai_parsed",
) -> int:
    """Inserts a new applicant or updates if email already exists."""
    sql = """
        INSERT INTO applicants (
            first_name, last_name, email, phone, education,
            years_experience, resume_file, resume_text, source
        )
        VALUES (
            :first_name, :last_name, :email, :phone, :education,
            :years_experience, :resume_file, :resume_text, :source
        )
        ON CONFLICT (email) DO UPDATE SET
            first_name = EXCLUDED.first_name,
            last_name = EXCLUDED.last_name,
            phone = EXCLUDED.phone,
            education = EXCLUDED.education,
            years_experience = EXCLUDED.years_experience,
            resume_file = EXCLUDED.resume_file,
            resume_text = EXCLUDED.resume_text,
            source = EXCLUDED.source
        RETURNING applicant_id
    """
    return db.execute(
        text(sql),
        {
            "first_name": first_name[:50],
            "last_name": last_name[:50],
            "email": email[:120],
            "phone": (phone[:30] if phone else None),
            "education": (education[:200] if education else None),
            "years_experience": round(float(years_experience), 1),
            "resume_file": resume_file,
            "resume_text": resume_text,
            "source": source,
        },
    ).scalar_one()


def link_applicant_skill(db: Session, applicant_id: int, skill_id: int, confidence: float) -> None:
    """Associates a skill with an applicant and records the confidence score."""
    conf = min(max(round(float(confidence), 2), 0.0), 1.0)
    db.execute(
        text("""
            INSERT INTO applicant_skills (applicant_id, skill_id, confidence)
            VALUES (:app_id, :skill_id, :conf)
            ON CONFLICT (applicant_id, skill_id) DO UPDATE SET confidence = EXCLUDED.confidence
        """),
        {"app_id": applicant_id, "skill_id": skill_id, "conf": conf},
    )


def create_application(db: Session, applicant_id: int, job_id: int, notes: Optional[str] = None) -> int:
    """Links an applicant to a job posting."""
    return db.execute(
        text("""
            INSERT INTO applications (job_id, applicant_id, status, notes)
            VALUES (:job_id, :applicant_id, 'applied', :notes)
            ON CONFLICT (job_id, applicant_id) DO UPDATE SET status = 'applied'
            RETURNING application_id
        """),
        {"job_id": job_id, "applicant_id": applicant_id, "notes": notes},
    ).scalar_one()


def get_or_create_application(db: Session, applicant_id: int, job_id: int) -> int:
    """Finds existing application or creates one for the applicant."""
    row = db.execute(
        text("SELECT application_id FROM applications WHERE applicant_id = :aid AND job_id = :jid"),
        {"aid": applicant_id, "jid": job_id},
    ).fetchone()
    if row:
        return row[0]
    return db.execute(
        text("""
            INSERT INTO applications (job_id, applicant_id, status)
            VALUES (:jid, :aid, 'applied')
            RETURNING application_id
        """),
        {"jid": job_id, "aid": applicant_id},
    ).scalar_one()


def set_application_status(db: Session, application_id: int, status: str, notes: Optional[str] = None) -> None:
    """Updates application status (e.g. offer, hired, rejected)."""
    db.execute(
        text("""
            UPDATE applications
               SET status = :status,
                   notes = COALESCE(:notes, notes)
             WHERE application_id = :app_id
        """),
        {"status": status, "app_id": application_id, "notes": notes},
    )


def list_applicants(db: Session) -> List[Dict[str, Any]]:
    """Returns all applicants with their application status, target job, and parsed skills."""
    sql = """
        SELECT a.applicant_id, a.first_name, a.last_name, a.email, a.phone,
               a.education, a.years_experience, a.source, a.created_at,
               app.application_id,
               COALESCE(app.status, 'applied') AS application_status,
               COALESCE(j.job_id, 1) AS job_id,
               COALESCE(pos.title, 'Software Developer') AS job_title,
               COALESCE(pos.min_salary, 35000.00) AS min_salary,
               COALESCE(pos.max_salary, 90000.00) AS max_salary,
               COALESCE(
                   json_agg(
                       json_build_object('name', s.skill_name, 'confidence', ask.confidence)
                   ) FILTER (WHERE s.skill_id IS NOT NULL), '[]'
               ) AS skills
          FROM applicants a
          LEFT JOIN (
              SELECT DISTINCT ON (applicant_id) application_id, applicant_id, job_id, status
                FROM applications
               ORDER BY applicant_id, application_id DESC
          ) app ON a.applicant_id = app.applicant_id
          LEFT JOIN job_postings j ON app.job_id = j.job_id
          LEFT JOIN positions pos ON j.position_id = pos.position_id
          LEFT JOIN applicant_skills ask ON a.applicant_id = ask.applicant_id
          LEFT JOIN skills s ON ask.skill_id = s.skill_id
         GROUP BY a.applicant_id, app.application_id, app.status, j.job_id, pos.title, pos.min_salary, pos.max_salary
         ORDER BY a.created_at DESC
    """
    rows = db.execute(text(sql)).mappings().all()
    return [dict(r) for r in rows]


def list_jobs(db: Session) -> List[Dict[str, Any]]:
    """Returns open job postings with department and position titles."""
    sql = """
        SELECT jp.job_id, jp.slots, jp.status, jp.posted_date, jp.closing_date,
               jp.description, jp.requirements,
               pos.position_id, pos.title AS position_title,
               pos.min_salary, pos.max_salary,
               d.name AS department_name
          FROM job_postings jp
          JOIN positions pos ON jp.position_id = pos.position_id
          JOIN departments d ON pos.department_id = d.department_id
         WHERE jp.status = 'open'
         ORDER BY jp.job_id ASC
    """
    rows = db.execute(text(sql)).mappings().all()
    return [dict(r) for r in rows]


def hire_applicant(db: Session, application_id: int, base_salary: float, hire_date: str) -> int:
    """Calls stored procedure sp_hire_applicant."""
    return db.execute(
        text("CALL sp_hire_applicant(:app, :salary, :hdate, NULL)"),
        {"app": application_id, "salary": base_salary, "hdate": hire_date},
    ).scalar_one()
