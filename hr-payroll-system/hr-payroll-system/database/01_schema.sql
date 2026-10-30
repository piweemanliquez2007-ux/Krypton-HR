-- =====================================================================
-- Enterprise HR & Payroll System - PostgreSQL schema (PostgreSQL 12+)
-- Run order: 01_schema.sql -> 02_seed.sql -> 03_demo_queries.sql
-- Contents: 18 tables (3NF), 3 triggers, 3 stored procedures, 3 views
-- =====================================================================

-- ---------------------------------------------------------------------
-- 0. RESET (development only: lets you re-run the whole script)
-- The QR attendance objects (04_qr_attendance.sql) are dropped here as well,
-- so a full reset really starts from an empty database.
-- ---------------------------------------------------------------------
DROP VIEW  IF EXISTS v_recruitment_pipeline, v_payroll_report, v_employee_summary,
                       v_shift_hours, attendance_punches, attendance_scan_audit;
DROP TABLE IF EXISTS applications, applicant_skills, applicants, skills, job_postings,
                     payslip_deductions, payslips, deduction_types, payroll_periods,
                     leave_requests, leave_balances, leave_types, attendance,
                     attendance_events, qr_scan_challenges, qr_scan_audit,
                     qr_credentials, kiosk_devices, shift_assignments, shifts,
                     users, employees, positions, roles, departments CASCADE;
DROP SEQUENCE IF EXISTS employee_no_seq;

CREATE SEQUENCE employee_no_seq START 1001;

-- ---------------------------------------------------------------------
-- 1. CORE ORGANISATION TABLES
-- ---------------------------------------------------------------------
CREATE TABLE departments (
    department_id  SERIAL PRIMARY KEY,
    name           VARCHAR(100) NOT NULL UNIQUE,
    description    TEXT
);

CREATE TABLE positions (
    position_id    SERIAL PRIMARY KEY,
    title          VARCHAR(100) NOT NULL,
    department_id  INT NOT NULL REFERENCES departments(department_id) ON DELETE RESTRICT,
    min_salary     NUMERIC(12,2) NOT NULL CHECK (min_salary >= 0),
    max_salary     NUMERIC(12,2) NOT NULL,
    CONSTRAINT chk_salary_range CHECK (max_salary >= min_salary),
    UNIQUE (title, department_id)
);

-- Department is reached through positions (employee -> position -> department)
-- so it is NOT repeated in employees. This keeps the design in 3NF.
CREATE TABLE employees (
    employee_id   SERIAL PRIMARY KEY,
    employee_no   VARCHAR(20) NOT NULL UNIQUE
                  DEFAULT ('EMP-' || LPAD(nextval('employee_no_seq')::TEXT, 5, '0')),
    first_name    VARCHAR(50)  NOT NULL,
    last_name     VARCHAR(50)  NOT NULL,
    email         VARCHAR(120) NOT NULL UNIQUE,
    phone         VARCHAR(30),
    birth_date    DATE,
    hire_date     DATE NOT NULL DEFAULT CURRENT_DATE,
    position_id   INT NOT NULL REFERENCES positions(position_id) ON DELETE RESTRICT,
    manager_id    INT REFERENCES employees(employee_id) ON DELETE SET NULL,
    base_salary   NUMERIC(12,2) NOT NULL CHECK (base_salary > 0),   -- monthly
    status        VARCHAR(15) NOT NULL DEFAULT 'active'
                  CHECK (status IN ('active', 'on_leave', 'resigned', 'terminated')),
    created_at    TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------
-- 2. SECURITY TABLES (used by JWT + RBAC in the API)
-- ---------------------------------------------------------------------
CREATE TABLE roles (
    role_id    SERIAL PRIMARY KEY,
    role_name  VARCHAR(30) NOT NULL UNIQUE          -- Admin, HR, Employee
);

CREATE TABLE users (
    user_id        SERIAL PRIMARY KEY,
    username       VARCHAR(50)  NOT NULL UNIQUE,
    password_hash  VARCHAR(255) NOT NULL,           -- bcrypt hash, never plain text
    role_id        INT NOT NULL REFERENCES roles(role_id),
    employee_id    INT UNIQUE REFERENCES employees(employee_id) ON DELETE SET NULL,
    is_active      BOOLEAN NOT NULL DEFAULT TRUE,
    last_login     TIMESTAMP,
    created_at     TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------
-- 3. ATTENDANCE
-- ---------------------------------------------------------------------
CREATE TABLE attendance (
    attendance_id   SERIAL PRIMARY KEY,
    employee_id     INT  NOT NULL REFERENCES employees(employee_id) ON DELETE CASCADE,
    work_date       DATE NOT NULL,
    time_in         TIME,
    time_out        TIME,
    hours_worked    NUMERIC(5,2) NOT NULL DEFAULT 0,   -- filled by trigger
    overtime_hours  NUMERIC(5,2) NOT NULL DEFAULT 0,   -- filled by trigger
    status          VARCHAR(10) NOT NULL DEFAULT 'present'
                    CHECK (status IN ('present', 'late', 'absent', 'half_day')),
    UNIQUE (employee_id, work_date),
    CONSTRAINT chk_time_order CHECK (time_out IS NULL OR time_in IS NULL OR time_out >= time_in)
);

-- ---------------------------------------------------------------------
-- 4. LEAVES
-- ---------------------------------------------------------------------
CREATE TABLE leave_types (
    leave_type_id        SERIAL PRIMARY KEY,
    name                 VARCHAR(50) NOT NULL UNIQUE,
    default_days_per_year INT CHECK (default_days_per_year >= 0),   -- NULL = no limit
    is_paid              BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE leave_balances (
    employee_id     INT NOT NULL REFERENCES employees(employee_id) ON DELETE CASCADE,
    leave_type_id   INT NOT NULL REFERENCES leave_types(leave_type_id),
    leave_year      INT NOT NULL,
    allocated_days  NUMERIC(5,1) NOT NULL CHECK (allocated_days >= 0),
    used_days       NUMERIC(5,1) NOT NULL DEFAULT 0 CHECK (used_days >= 0),
    PRIMARY KEY (employee_id, leave_type_id, leave_year),
    CONSTRAINT chk_balance CHECK (used_days <= allocated_days)
);

CREATE TABLE leave_requests (
    request_id      SERIAL PRIMARY KEY,
    employee_id     INT  NOT NULL REFERENCES employees(employee_id) ON DELETE CASCADE,
    leave_type_id   INT  NOT NULL REFERENCES leave_types(leave_type_id),
    start_date      DATE NOT NULL,
    end_date        DATE NOT NULL,
    -- calendar days, computed by the database (weekends included: simplification)
    days_requested  INT GENERATED ALWAYS AS (end_date - start_date + 1) STORED,
    reason          TEXT,
    status          VARCHAR(10) NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'approved', 'rejected', 'cancelled')),
    reviewed_by     INT REFERENCES users(user_id),
    reviewed_at     TIMESTAMP,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_leave_dates CHECK (end_date >= start_date)
);

-- ---------------------------------------------------------------------
-- 5. PAYROLL
-- ---------------------------------------------------------------------
CREATE TABLE payroll_periods (
    period_id    SERIAL PRIMARY KEY,
    period_name  VARCHAR(50) NOT NULL UNIQUE,
    start_date   DATE NOT NULL,
    end_date     DATE NOT NULL,
    pay_date     DATE,
    status       VARCHAR(10) NOT NULL DEFAULT 'open'
                 CHECK (status IN ('open', 'processed', 'paid')),
    CONSTRAINT chk_period_dates CHECK (end_date >= start_date)
);

-- Deduction rates live in a table so they can change without touching code.
CREATE TABLE deduction_types (
    deduction_type_id  SERIAL PRIMARY KEY,
    name               VARCHAR(60) NOT NULL UNIQUE,
    calc_method        VARCHAR(10) NOT NULL CHECK (calc_method IN ('percent', 'fixed')),
    rate               NUMERIC(10,4) NOT NULL CHECK (rate >= 0),   -- % or fixed amount
    max_amount         NUMERIC(12,2),                              -- optional cap
    is_active          BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE payslips (
    payslip_id        SERIAL PRIMARY KEY,
    employee_id       INT NOT NULL REFERENCES employees(employee_id) ON DELETE RESTRICT,
    period_id         INT NOT NULL REFERENCES payroll_periods(period_id) ON DELETE RESTRICT,
    days_paid         NUMERIC(5,1) NOT NULL DEFAULT 0,
    overtime_hours    NUMERIC(6,2) NOT NULL DEFAULT 0,
    basic_pay         NUMERIC(12,2) NOT NULL,
    overtime_pay      NUMERIC(12,2) NOT NULL DEFAULT 0,
    gross_pay         NUMERIC(12,2) NOT NULL,
    total_deductions  NUMERIC(12,2) NOT NULL DEFAULT 0,
    net_pay           NUMERIC(12,2) NOT NULL,
    generated_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (employee_id, period_id),
    CONSTRAINT chk_gross CHECK (gross_pay = basic_pay + overtime_pay),
    CONSTRAINT chk_net   CHECK (net_pay = gross_pay - total_deductions)
);

CREATE TABLE payslip_deductions (
    payslip_id         INT NOT NULL REFERENCES payslips(payslip_id) ON DELETE CASCADE,
    deduction_type_id  INT NOT NULL REFERENCES deduction_types(deduction_type_id),
    amount             NUMERIC(12,2) NOT NULL CHECK (amount >= 0),
    PRIMARY KEY (payslip_id, deduction_type_id)
);

-- ---------------------------------------------------------------------
-- 6. RECRUITMENT (+ AI resume parsing target tables)
-- ---------------------------------------------------------------------
CREATE TABLE job_postings (
    job_id        SERIAL PRIMARY KEY,
    position_id   INT NOT NULL REFERENCES positions(position_id),
    description   TEXT,
    requirements  TEXT,
    slots         INT NOT NULL DEFAULT 1 CHECK (slots > 0),
    status        VARCHAR(10) NOT NULL DEFAULT 'open'
                  CHECK (status IN ('open', 'on_hold', 'closed')),
    posted_date   DATE NOT NULL DEFAULT CURRENT_DATE,
    closing_date  DATE,
    created_by    INT REFERENCES users(user_id),
    CONSTRAINT chk_job_dates CHECK (closing_date IS NULL OR closing_date >= posted_date)
);

CREATE TABLE skills (
    skill_id    SERIAL PRIMARY KEY,
    skill_name  VARCHAR(60) NOT NULL UNIQUE
);

CREATE TABLE applicants (
    applicant_id      SERIAL PRIMARY KEY,
    first_name        VARCHAR(50)  NOT NULL,
    last_name         VARCHAR(50)  NOT NULL,
    email             VARCHAR(120) NOT NULL UNIQUE,
    phone             VARCHAR(30),
    education         VARCHAR(200),
    years_experience  NUMERIC(4,1) CHECK (years_experience >= 0),
    resume_file       VARCHAR(255),
    resume_text       TEXT,                        -- raw text extracted from the resume
    source            VARCHAR(10) NOT NULL DEFAULT 'manual'
                      CHECK (source IN ('manual', 'ai_parsed')),
    created_at        TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE applicant_skills (
    applicant_id  INT NOT NULL REFERENCES applicants(applicant_id) ON DELETE CASCADE,
    skill_id      INT NOT NULL REFERENCES skills(skill_id),
    confidence    NUMERIC(3,2) CHECK (confidence BETWEEN 0 AND 1),   -- AI confidence score
    PRIMARY KEY (applicant_id, skill_id)
);

CREATE TABLE applications (
    application_id  SERIAL PRIMARY KEY,
    job_id          INT NOT NULL REFERENCES job_postings(job_id) ON DELETE CASCADE,
    applicant_id    INT NOT NULL REFERENCES applicants(applicant_id) ON DELETE CASCADE,
    status          VARCHAR(10) NOT NULL DEFAULT 'applied'
                    CHECK (status IN ('applied', 'screening', 'interview', 'offer', 'hired', 'rejected')),
    applied_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    notes           TEXT,
    UNIQUE (job_id, applicant_id)
);

-- ---------------------------------------------------------------------
-- 7. INDEXES (foreign keys and common filters)
-- ---------------------------------------------------------------------
CREATE INDEX idx_employees_position   ON employees(position_id);
CREATE INDEX idx_employees_manager    ON employees(manager_id);
CREATE INDEX idx_employees_status     ON employees(status);
CREATE INDEX idx_attendance_date      ON attendance(work_date);
CREATE INDEX idx_leave_req_emp_status ON leave_requests(employee_id, status);
CREATE INDEX idx_payslips_period      ON payslips(period_id);
CREATE INDEX idx_applications_job     ON applications(job_id, status);
CREATE INDEX idx_applicant_skills_sk  ON applicant_skills(skill_id);

-- =====================================================================
-- 8. TRIGGERS
-- =====================================================================

-- TRIGGER 1: compute hours_worked and overtime_hours on attendance insert/update.
-- Assumptions: 1 hour unpaid break if shift > 5 hours; standard day = 8 hours.
CREATE OR REPLACE FUNCTION fn_attendance_compute_hours() RETURNS TRIGGER AS $$
DECLARE
    v_hours NUMERIC;
BEGIN
    IF NEW.time_in IS NOT NULL AND NEW.time_out IS NOT NULL THEN
        v_hours := EXTRACT(EPOCH FROM (NEW.time_out - NEW.time_in)) / 3600.0;
        IF v_hours > 5 THEN
            v_hours := v_hours - 1;
        END IF;
        NEW.hours_worked   := ROUND(v_hours, 2);
        NEW.overtime_hours := GREATEST(ROUND(v_hours - 8, 2), 0);
    ELSE
        NEW.hours_worked   := 0;
        NEW.overtime_hours := 0;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_attendance_compute_hours
BEFORE INSERT OR UPDATE OF time_in, time_out ON attendance
FOR EACH ROW EXECUTE FUNCTION fn_attendance_compute_hours();

-- TRIGGER 2: keep leave_balances.used_days in sync with leave request status.
-- Approved -> deduct days. Approved then cancelled -> give the days back.
CREATE OR REPLACE FUNCTION fn_leave_balance_update() RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status = 'approved' AND OLD.status <> 'approved' THEN
        UPDATE leave_balances
           SET used_days = used_days + NEW.days_requested
         WHERE employee_id   = NEW.employee_id
           AND leave_type_id = NEW.leave_type_id
           AND leave_year    = EXTRACT(YEAR FROM NEW.start_date)::INT;
    ELSIF OLD.status = 'approved' AND NEW.status = 'cancelled' THEN
        UPDATE leave_balances
           SET used_days = used_days - NEW.days_requested
         WHERE employee_id   = NEW.employee_id
           AND leave_type_id = NEW.leave_type_id
           AND leave_year    = EXTRACT(YEAR FROM NEW.start_date)::INT;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_leave_balance_update
AFTER UPDATE OF status ON leave_requests
FOR EACH ROW WHEN (OLD.status IS DISTINCT FROM NEW.status)
EXECUTE FUNCTION fn_leave_balance_update();

-- TRIGGER 3 (bonus): every new employee automatically gets this year's leave balances.
CREATE OR REPLACE FUNCTION fn_employee_init_leave_balances() RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO leave_balances (employee_id, leave_type_id, leave_year, allocated_days)
    SELECT NEW.employee_id, lt.leave_type_id, EXTRACT(YEAR FROM CURRENT_DATE)::INT, lt.default_days_per_year
      FROM leave_types lt
     WHERE lt.default_days_per_year IS NOT NULL;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_employee_init_leave_balances
AFTER INSERT ON employees
FOR EACH ROW EXECUTE FUNCTION fn_employee_init_leave_balances();

-- =====================================================================
-- 9. STORED PROCEDURES
-- =====================================================================

-- PROCEDURE 1: generate payslips for every active employee in a period.
-- Rules (edit constants to match your business rules):
--   * base_salary is MONTHLY; daily rate = base_salary / 22; hourly = daily / 8
--   * paid days = days present/late (half_day = 0.5) + approved PAID leave days
--   * basic pay is capped at base_salary
--   * overtime is paid at 1.25x the hourly rate
--   * each active deduction_type is applied to gross pay (percent) or as a fixed amount
CREATE OR REPLACE PROCEDURE sp_generate_payroll(p_period_id INT)
LANGUAGE plpgsql AS $$
DECLARE
    v_period      payroll_periods%ROWTYPE;
    v_emp         RECORD;
    v_std_days    CONSTANT NUMERIC := 22;
    v_ot_mult     CONSTANT NUMERIC := 1.25;
    v_daily       NUMERIC;
    v_hourly      NUMERIC;
    v_present     NUMERIC;
    v_ot_hours    NUMERIC;
    v_leave_days  NUMERIC;
    v_paid_days   NUMERIC;
    v_basic       NUMERIC;
    v_ot_pay      NUMERIC;
    v_gross       NUMERIC;
    v_total_ded   NUMERIC;
    v_payslip_id  INT;
BEGIN
    SELECT * INTO v_period FROM payroll_periods WHERE period_id = p_period_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Payroll period % not found', p_period_id;
    END IF;
    IF v_period.status <> 'open' THEN
        RAISE EXCEPTION 'Payroll period % is already % and cannot be regenerated', p_period_id, v_period.status;
    END IF;

    FOR v_emp IN
        SELECT employee_id, base_salary
          FROM employees
         WHERE status IN ('active', 'on_leave')
           AND hire_date <= v_period.end_date
    LOOP
        v_daily  := ROUND(v_emp.base_salary / v_std_days, 2);
        v_hourly := ROUND(v_daily / 8, 2);

        SELECT COALESCE(SUM(CASE status
                               WHEN 'present'  THEN 1
                               WHEN 'late'     THEN 1
                               WHEN 'half_day' THEN 0.5
                               ELSE 0 END), 0),
               COALESCE(SUM(overtime_hours), 0)
          INTO v_present, v_ot_hours
          FROM attendance
         WHERE employee_id = v_emp.employee_id
           AND work_date BETWEEN v_period.start_date AND v_period.end_date;

        SELECT COALESCE(SUM(LEAST(lr.end_date, v_period.end_date)
                          - GREATEST(lr.start_date, v_period.start_date) + 1), 0)
          INTO v_leave_days
          FROM leave_requests lr
          JOIN leave_types lt ON lt.leave_type_id = lr.leave_type_id
         WHERE lr.employee_id = v_emp.employee_id
           AND lr.status = 'approved'
           AND lt.is_paid
           AND lr.start_date <= v_period.end_date
           AND lr.end_date   >= v_period.start_date;

        v_paid_days := v_present + v_leave_days;
        v_basic     := LEAST(v_emp.base_salary, ROUND(v_daily * v_paid_days, 2));
        v_ot_pay    := ROUND(v_ot_hours * v_hourly * v_ot_mult, 2);
        v_gross     := v_basic + v_ot_pay;

        INSERT INTO payslips (employee_id, period_id, days_paid, overtime_hours,
                              basic_pay, overtime_pay, gross_pay, total_deductions, net_pay)
        VALUES (v_emp.employee_id, p_period_id, v_paid_days, v_ot_hours,
                v_basic, v_ot_pay, v_gross, 0, v_gross)
        RETURNING payslip_id INTO v_payslip_id;

        INSERT INTO payslip_deductions (payslip_id, deduction_type_id, amount)
        SELECT v_payslip_id,
               dt.deduction_type_id,
               ROUND(CASE
                        WHEN dt.calc_method = 'fixed'  THEN dt.rate
                        WHEN dt.max_amount IS NULL     THEN v_gross * dt.rate / 100
                        ELSE LEAST(v_gross * dt.rate / 100, dt.max_amount)
                     END, 2)
          FROM deduction_types dt
         WHERE dt.is_active;

        SELECT COALESCE(SUM(amount), 0) INTO v_total_ded
          FROM payslip_deductions WHERE payslip_id = v_payslip_id;

        UPDATE payslips
           SET total_deductions = v_total_ded,
               net_pay          = v_gross - v_total_ded
         WHERE payslip_id = v_payslip_id;
    END LOOP;

    UPDATE payroll_periods SET status = 'processed' WHERE period_id = p_period_id;
END;
$$;

-- PROCEDURE 2: approve or reject a pending leave request.
-- Checks the balance first; trigger trg_leave_balance_update then deducts the days.
CREATE OR REPLACE PROCEDURE sp_approve_leave(
    p_request_id  INT,
    p_reviewer_id INT,
    p_decision    VARCHAR DEFAULT 'approved'
)
LANGUAGE plpgsql AS $$
DECLARE
    v_req        leave_requests%ROWTYPE;
    v_limit      INT;
    v_remaining  NUMERIC;
BEGIN
    IF p_decision NOT IN ('approved', 'rejected') THEN
        RAISE EXCEPTION 'Decision must be approved or rejected (got %)', p_decision;
    END IF;

    SELECT * INTO v_req FROM leave_requests WHERE request_id = p_request_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Leave request % not found', p_request_id;
    END IF;
    IF v_req.status <> 'pending' THEN
        RAISE EXCEPTION 'Leave request % is already %', p_request_id, v_req.status;
    END IF;

    IF p_decision = 'approved' THEN
        SELECT default_days_per_year INTO v_limit
          FROM leave_types WHERE leave_type_id = v_req.leave_type_id;

        IF v_limit IS NOT NULL THEN                   -- NULL = unlimited (e.g. unpaid leave)
            SELECT allocated_days - used_days INTO v_remaining
              FROM leave_balances
             WHERE employee_id   = v_req.employee_id
               AND leave_type_id = v_req.leave_type_id
               AND leave_year    = EXTRACT(YEAR FROM v_req.start_date)::INT;

            IF NOT FOUND THEN
                RAISE EXCEPTION 'No leave balance found for employee % in year %',
                                v_req.employee_id, EXTRACT(YEAR FROM v_req.start_date)::INT;
            END IF;
            IF v_remaining < v_req.days_requested THEN
                RAISE EXCEPTION 'Insufficient leave balance: % day(s) left, % requested',
                                v_remaining, v_req.days_requested;
            END IF;
        END IF;
    END IF;

    UPDATE leave_requests
       SET status      = p_decision,
           reviewed_by = p_reviewer_id,
           reviewed_at = NOW()
     WHERE request_id = p_request_id;
END;
$$;

-- PROCEDURE 3: convert an applicant (application at 'offer' stage) into an employee.
-- Returns the new employee_id through the INOUT parameter.
CREATE OR REPLACE PROCEDURE sp_hire_applicant(
    p_application_id INT,
    p_base_salary    NUMERIC,
    p_hire_date      DATE DEFAULT CURRENT_DATE,
    INOUT p_employee_id INT DEFAULT NULL
)
LANGUAGE plpgsql AS $$
DECLARE
    v_app          applications%ROWTYPE;
    v_ap           applicants%ROWTYPE;
    v_position_id  INT;
    v_min          NUMERIC;
    v_max          NUMERIC;
BEGIN
    SELECT * INTO v_app FROM applications WHERE application_id = p_application_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Application % not found', p_application_id;
    END IF;
    IF v_app.status <> 'offer' THEN
        RAISE EXCEPTION 'Application % must be at the offer stage (current stage: %)',
                        p_application_id, v_app.status;
    END IF;

    SELECT * INTO v_ap FROM applicants WHERE applicant_id = v_app.applicant_id;

    SELECT p.position_id, p.min_salary, p.max_salary
      INTO v_position_id, v_min, v_max
      FROM job_postings j
      JOIN positions p ON p.position_id = j.position_id
     WHERE j.job_id = v_app.job_id;

    IF p_base_salary < v_min OR p_base_salary > v_max THEN
        RAISE EXCEPTION 'Salary % is outside the position range % - %', p_base_salary, v_min, v_max;
    END IF;

    INSERT INTO employees (first_name, last_name, email, phone, hire_date, position_id, base_salary)
    VALUES (v_ap.first_name, v_ap.last_name, v_ap.email, v_ap.phone,
            p_hire_date, v_position_id, p_base_salary)
    RETURNING employee_id INTO p_employee_id;      -- leave balances are created by trigger 3

    UPDATE applications SET status = 'hired' WHERE application_id = p_application_id;
END;
$$;

-- =====================================================================
-- 10. VIEWS
-- =====================================================================

-- VIEW 1: employee + position + department + manager
CREATE OR REPLACE VIEW v_employee_summary AS
SELECT e.employee_id,
       e.employee_no,
       e.first_name || ' ' || e.last_name  AS full_name,
       e.email,
       d.name                              AS department,
       p.title                             AS position,
       e.base_salary,
       e.hire_date,
       e.status,
       m.first_name || ' ' || m.last_name  AS manager_name
  FROM employees e
  JOIN positions   p ON p.position_id   = e.position_id
  JOIN departments d ON d.department_id = p.department_id
  LEFT JOIN employees m ON m.employee_id = e.manager_id;

-- VIEW 2: payslips per period with employee and department
CREATE OR REPLACE VIEW v_payroll_report AS
SELECT pp.period_id,
       pp.period_name,
       e.employee_id,
       e.employee_no,
       e.first_name || ' ' || e.last_name AS full_name,
       d.name                             AS department,
       ps.days_paid,
       ps.overtime_hours,
       ps.basic_pay,
       ps.overtime_pay,
       ps.gross_pay,
       ps.total_deductions,
       ps.net_pay
  FROM payslips ps
  JOIN employees       e  ON e.employee_id   = ps.employee_id
  JOIN payroll_periods pp ON pp.period_id    = ps.period_id
  JOIN positions       p  ON p.position_id   = e.position_id
  JOIN departments     d  ON d.department_id = p.department_id;

-- VIEW 3: recruitment pipeline (applications per job and stage; jobs with none show 0)
CREATE OR REPLACE VIEW v_recruitment_pipeline AS
SELECT j.job_id,
       p.title                       AS job_title,
       d.name                        AS department,
       j.status                      AS job_status,
       a.status                      AS application_status,
       COUNT(a.application_id)       AS total_applications
  FROM job_postings j
  JOIN positions   p ON p.position_id   = j.position_id
  JOIN departments d ON d.department_id = p.department_id
  LEFT JOIN applications a ON a.job_id = j.job_id
 GROUP BY j.job_id, p.title, d.name, j.status, a.status;
