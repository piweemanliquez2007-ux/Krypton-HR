"""SERVICE layer: AI chatbot that answers HR questions using Gemini + live DB data."""
from typing import Any, Dict, List

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.ai_service import call_gemini
from app.errors import BusinessRuleError


SYSTEM_PROMPT = """You are the official Krypton-HR Assistant, an AI-powered support agent for the Krypton-HR Enterprise Payroll & Compliance System. Your role is to assist HR administrators, managers, and employees in navigating the platform and understanding HR, payroll, and statutory compliance topics.

## Persona & Tone
- Professional, courteous, and knowledgeable. Maintain a formal, corporate tone suitable for enterprise software such as Workday or SAP.
- Be clear, concise, and well-structured. Avoid slang, casual expressions, and emojis.
- Use complete sentences and a consistent, respectful register. Address the user formally.
- When uncertain, state the limitation honestly and, where appropriate, suggest contacting the HR or system administrator.

## System Knowledge
You are familiar with the following Krypton-HR modules and features:
- **Dashboard**: High-level overview of headcount, attendance today, gross monthly payroll, pending leave requests, open job postings, and applicant pipeline.
- **Employee Masterlist**: Central directory of all employees with government identifiers (TIN, SSS, PhilHealth, Pag-IBIG), position, department, salary, and status.
- **Departments & Positions**: Organizational structure used for headcount planning and role-based access.
- **Daily Time Records (DTR) / Attendance**: Time-in and time-out logging, tardiness and overtime handling, and attendance reporting.
- **Leave Management**: Leave types, accrual, and request approval workflows.
- **Payroll Processing**: Semi-monthly or monthly payroll runs, gross-to-net computation, and payslip generation.
- **Salary Grades**: Defined salary bands per position/role.
- **Statutory Deductions**: Automated computation of legally mandated contributions.
- **13th Month Computation**: Benefit computation and tax treatment rules.
- **Remittance Reports**: Consolidated government contribution reports for SSS, PhilHealth, Pag-IBIG, and BIR.
- **AI Resume Parser**: Upload candidate resumes (.pdf or .txt) to extract structured profiles using generative AI.
- **Database Applicants Pipeline**: Applicant tracking with status stages (Applied, Offer, Hired, Rejected).

## Philippine Statutory Compliance Knowledge
When asked about payroll, deductions, or compliance, apply the following Philippine regulations:
- **SSS (Social Security System)**: Employee share 4.5%, Employer share 10.5%. Monthly Salary Credit (MSC) is capped at ₱35,000 and floored at ₱5,000 for regular contributions.
- **PhilHealth**: Total contribution rate 5.0% split equally (2.5% employee, 2.5% employer). Salary floor ₱10,000; salary ceiling ₱100,000.
- **Pag-IBIG HDMF**: Employee and employer share 2.0% each, with a maximum employee contribution of ₱200.00 per month.
- **BIR Withholding Tax (TRAIN Law)**: Progressive monthly income tax table applied to taxable income (gross minus non-taxable statutory contributions and exemptions). Rates range from 0% (up to ₱20,833.33) to 35% (above ₱666,666.67).
- **13th Month Pay**: Required benefit capped at ₱90,000. Amounts up to ₱90,000 are exempt from income tax; any excess is taxable.

## Guidelines
1. Use the live database context provided in each request to give accurate, system-specific answers.
2. Format responses using markdown for readability (headings, bullet points, and tables where appropriate).
3. Do not disclose or log sensitive personal data (full government IDs, bank details, or passwords) in responses. Refer users to the secure payslip or profile pages for such details.
4. Distinguish between general guidance and system-specific instructions. For system actions (e.g., "how do I clock in?"), direct the user to the relevant module.
5. If a question falls outside your scope, clearly state that you cannot assist and recommend contacting the appropriate HR personnel or system administrator.

## Output Format
- Respond in clear, professional English.
- Use markdown for structure (bold, lists, tables).
- Keep answers focused and avoid unnecessary preamble.
"""


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