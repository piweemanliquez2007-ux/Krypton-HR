# HR & Payroll API (FastAPI, layered architecture)

## Setup
```bash
cd backend
python -m venv venv
venv\Scripts\activate            # Windows   (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env           # Windows   (Mac/Linux: cp .env.example .env)
# then edit .env: set DATABASE_URL password and a real JWT_SECRET
```
The database must already exist and contain 01_schema.sql + 02_seed.sql.

## Run (always from the backend/ folder)
```bash
uvicorn app.main:app --reload
```
- API docs / test page: http://localhost:8000/docs
- Health check: http://localhost:8000/health  -> should say "connected"

## Architecture (layered)
```
Browser -> ROUTER -> SERVICE -> REPOSITORY -> PostgreSQL
           (HTTP)    (rules)    (SQL only)
```
| Layer | Folder | Does | Must NOT |
|---|---|---|---|
| Router | `routers/` | Receives the request, validates it with a schema, checks the role (`require_role`), calls ONE service function, returns the result | contain SQL or business rules |
| Service | `services/` | Business rules (permissions on records, salary range, balances), transactions (`with transaction(db):`), raises `AppError`s | contain SQL or import FastAPI |
| Repository | `repositories/` | The SQL (`text()` + bound parameters) and calls to stored procedures | commit, or contain business rules |
| Schemas | `schemas/` | Pydantic models for requests and responses | |

Cross-cutting files: `security.py` (bcrypt, JWT, RBAC guard), `errors.py` (error classes and
the DB-error translator), `database.py` (session + `transaction()`), `config.py` (.env).

## Error handling
Services raise these (from `app/errors.py`), and `main.py` turns them into `{"detail": "..."}`:
`UnauthorizedError` 401, `ForbiddenError` 403, `NotFoundError` 404, `ConflictError` 409, `BusinessRuleError` 400.
Any PostgreSQL error inside `with transaction(db):` is translated automatically, including
messages from our stored procedures (for example "Insufficient leave balance" becomes a 400).

## First test (in /docs)
1. `POST /auth/login` with `{"username": "admin", "password": "Admin@123"}`
2. Copy the `access_token`, click **Authorize** (top right), paste it, confirm.
3. Try `GET /employees`, `POST /employees`, `PUT /employees/{id}`, `DELETE /employees/{id}`.

## Test the role rules (RBAC)
| Login | Try | Expected |
|---|---|---|
| admin / Admin@123 | GET /employees | 200 |
| maria / Hr@12345 (HR) | GET /employees | 200 |
| maria | DELETE /employees/6 | 403 (Admin only) |
| priya / Emp@12345 (Employee) | GET /employees | 403 |
| priya | GET /employees/3 (herself) | 200 |
| priya | GET /employees/4 (someone else) | 403 |
| no token | GET /employees | 401 or 403 |
| admin | POST /employees with base_salary outside the position's range | 400 (business rule) |
| admin | POST /employees with an existing email | 409 |

## How to add a new module (example: leaves)
Create three files and register the router in `main.py`.

**1. `repositories/leave_repository.py`** (SQL only)
```python
from sqlalchemy import text

def approve(db, request_id: int, reviewer_id: int, decision: str) -> None:
    db.execute(
        text("CALL sp_approve_leave(:req, :reviewer, :decision)"),
        {"req": request_id, "reviewer": reviewer_id, "decision": decision},
    )
```
**2. `services/leave_service.py`** (rules and transaction)
```python
from app.database import transaction
from app.repositories import leave_repository

def review_leave(db, request_id: int, decision: str, current_user: dict) -> dict:
    with transaction(db):     # commits, or rolls back and converts DB errors
        leave_repository.approve(db, request_id, current_user["user_id"], decision)
    return {"message": f"Leave request {request_id} {decision}"}
```
**3. `routers/leaves.py`** (HTTP only)
```python
router = APIRouter(prefix="/leaves", tags=["Leaves"])

@router.post("/{request_id}/review")
def review(request_id: int, decision: str,
           db: Session = Depends(get_db), user: dict = Depends(require_role(*ADMIN_HR))):
    return leave_service.review_leave(db, request_id, decision, user)
```
Procedure with an INOUT result (sp_hire_applicant), inside a repository:
```python
new_id = db.execute(
    text("CALL sp_hire_applicant(:app, :salary, :hire_date, NULL)"),
    {"app": application_id, "salary": salary, "hire_date": hire_date},
).scalar_one()
```
Rules: bound parameters only (never put user values inside the SQL string), one service
function per router function, and reads that need permission checks go through the service.

## Structure
```
app/
  main.py          app, CORS, error handlers, routers, /health
  config.py        settings from .env
  database.py      engine, get_db, transaction()
  security.py      bcrypt check, JWT, get_current_user, require_role, ADMIN_HR
  errors.py        AppError classes + DB error translation
  routers/         auth.py, employees.py, lookups.py
  services/        auth_service.py, employee_service.py, lookup_service.py
  repositories/    user_repository.py, employee_repository.py, lookup_repository.py
  schemas/         auth.py, employee.py
```

## Split of work
- Backend 1: attendance, leaves
- Backend 2: payroll (+ payslips), recruitment (+ hire), resume upload endpoint
