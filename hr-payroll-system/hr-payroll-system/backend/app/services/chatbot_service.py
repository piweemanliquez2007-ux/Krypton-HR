"""SERVICE layer: AI chatbot that answers HR questions using Gemini + live DB data."""
from typing import Any, Dict, List

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.ai_service import call_gemini
from app.errors import BusinessRuleError


SYSTEM_PROMPT = """You are a helpful HR Assistant for an enterprise HR & Payroll system.
Answer questions about employees, attendance, leaves, payroll, and recruitment.
Be concise and professional. Use the database context provided to give accurate answers.
If you don't know something, say so honestly. Format responses with markdown for readability."""


def _gather_context(db: Session, user_message: str) -> str:
    """Gathers relevant database context based on keywords in the user message."""
    msg = user_message.lower()
    context_parts: List[str] = []

    # Employee count
    total = db.execute(text("SELECT COUNT(*) FROM employees WHERE status = 'active'")).scalar()
    context_parts.append(f"Active employees: {total}")

    # Departments
    depts = db.execute(text("SELECT name, COUNT(*) as cnt FROM departments d JOIN employees e ON e.employee_id IN (SELECT employee_id FROM employees WHERE position_id IN (SELECT position_id FROM positions WHERE department_id = d.department_id)) GROUP BY d.name")).mappings().all()
    if depts:
        context_parts.append("Departments: " + ", ".join(f"{d['name']} ({d['cnt']})" for d in depts))

    # Attendance today
    today = db.execute(text("SELECT COUNT(*) FROM attendance WHERE work_date = CURRENT_DATE")).scalar()
    context_parts.append(f"Present today: {today}")

    # Pending leaves
    pending = db.execute(text("SELECT COUNT(*) FROM leave_requests WHERE status = 'pending'")).scalar()
    context_parts.append(f"Pending leave requests: {pending}")

    # Latest payroll period
    period = db.execute(text("SELECT period_name, status FROM payroll_periods ORDER BY period_id DESC LIMIT 1")).mappings().first()
    if period:
        context_parts.append(f"Latest payroll period: {period['period_name']} ({period['status']})")

    # Open job postings
    jobs = db.execute(text("SELECT COUNT(*) FROM job_postings WHERE status = 'open'")).scalar()
    context_parts.append(f"Open job postings: {jobs}")

    # Pending applicants
    apps = db.execute(text("SELECT COUNT(*) FROM applicants")).scalar()
    context_parts.append(f"Total applicants in pipeline: {apps}")

    # Gross monthly payroll
    gross = db.execute(text("SELECT COALESCE(SUM(base_salary), 0) FROM employees WHERE status = 'active'")).scalar()
    context_parts.append(f"Monthly payroll (active employees): ₱{float(gross):,.2f}")

    return "\n".join(context_parts)


def chat(db: Session, user_message: str, conversation_history: List[Dict[str, str]] | None = None) -> Dict[str, Any]:
    """
    Answers an HR question using Gemini AI with live database context.
    """
    if not user_message or len(user_message.strip()) < 2:
        raise BusinessRuleError("Please enter a question.")

    context = _gather_context(db, user_message)

    # Build the full prompt with context
    prompt = f"{SYSTEM_PROMPT}\n\nDatabase Context:\n{context}\n\nUser Question: {user_message}"

    # Include conversation history if available
    contents = []
    if conversation_history:
        for msg in conversation_history[-6:]:  # keep last 6 messages for context
            contents.append({
                "parts": [{"text": f"User: {msg.get('user', '')}\nAssistant: {msg.get('assistant', '')}"}]
            })
    contents.append({"parts": [{"text": prompt}]})

    response = call_gemini(contents)

    return {
        "response": response,
        "context_used": context,
    }