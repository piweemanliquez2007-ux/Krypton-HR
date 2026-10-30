-- =====================================================================
-- Sample data (fake people, sample rates). For development and demos only.
-- Requires 01_schema.sql to have been run first.
-- =====================================================================

-- bcrypt hashing for the sample user passwords (real bcrypt, works with Python bcrypt/passlib)
CREATE EXTENSION IF NOT EXISTS pgcrypto;

INSERT INTO roles (role_name) VALUES ('Admin'), ('HR'), ('Employee');

INSERT INTO departments (name, description) VALUES
    ('Human Resources', 'People operations and recruitment'),
    ('Information Technology', 'Software and infrastructure'),
    ('Finance', 'Accounting and payroll'),
    ('Operations', 'Day-to-day business operations');

INSERT INTO positions (title, department_id, min_salary, max_salary) VALUES
    ('HR Manager',         1, 40000, 70000),   -- 1
    ('HR Officer',         1, 25000, 45000),   -- 2
    ('Software Developer', 2, 35000, 90000),   -- 3
    ('IT Manager',         2, 60000, 110000),  -- 4
    ('Accountant',         3, 30000, 60000),   -- 5
    ('Operations Staff',   4, 20000, 35000);   -- 6

-- Employees (leave balances are created automatically by trigger 3)
INSERT INTO employees (first_name, last_name, email, phone, hire_date, position_id, manager_id, base_salary) VALUES
    ('Maria',  'Santos',  'maria.santos@example.com',  '0917-000-0001', '2022-01-10', 1, NULL, 55000),  -- 1
    ('James',  'Carter',  'james.carter@example.com',  '0917-000-0002', '2021-06-01', 4, NULL, 80000),  -- 2
    ('Priya',  'Nair',    'priya.nair@example.com',    '0917-000-0003', '2023-03-15', 3, 2,    60000),  -- 3
    ('Liam',   'Chen',    'liam.chen@example.com',     '0917-000-0004', '2023-08-01', 3, 2,    52000),  -- 4
    ('Sofia',  'Alvarez', 'sofia.alvarez@example.com', '0917-000-0005', '2022-09-12', 5, 1,    42000),  -- 5
    ('Omar',   'Hassan',  'omar.hassan@example.com',   '0917-000-0006', '2024-02-05', 6, 1,    28000);  -- 6

-- Users (passwords: Admin@123 / Hr@12345 / Emp@12345 -- CHANGE FOR ANYTHING REAL)
INSERT INTO users (username, password_hash, role_id, employee_id) VALUES
    ('admin',  crypt('Admin@123',  gen_salt('bf', 10)), 1, NULL),  -- 1
    ('maria',  crypt('Hr@12345',   gen_salt('bf', 10)), 2, 1),     -- 2
    ('priya',  crypt('Emp@12345',  gen_salt('bf', 10)), 3, 3),     -- 3
    ('liam',   crypt('Emp@12345',  gen_salt('bf', 10)), 3, 4);     -- 4

INSERT INTO leave_types (name, default_days_per_year, is_paid) VALUES
    ('Vacation',  15,   TRUE),
    ('Sick',      10,   TRUE),
    ('Emergency',  5,   TRUE),
    ('Unpaid',    NULL, FALSE);

-- Sample deduction rates. REPLACE with your country's real rules.
INSERT INTO deduction_types (name, calc_method, rate, max_amount) VALUES
    ('Income Tax',        'percent', 10.0000, NULL),
    ('Social Security',   'percent',  4.5000, 1350.00),
    ('Health Insurance',  'percent',  2.5000, 1000.00),
    ('Housing Fund',      'fixed',  200.0000, NULL);

INSERT INTO payroll_periods (period_name, start_date, end_date, pay_date) VALUES
    ('September 2026', '2026-09-01', '2026-09-30', '2026-09-30');

-- Attendance for September 2026 (weekdays, 08:00-17:00). Hours/overtime are computed by the trigger.
INSERT INTO attendance (employee_id, work_date, time_in, time_out)
SELECT e.employee_id, d::DATE, TIME '08:00',
       CASE WHEN e.employee_id = 3 AND EXTRACT(ISODOW FROM d) = 5 THEN TIME '19:00'  -- Priya: Friday overtime
            ELSE TIME '17:00' END
  FROM employees e
 CROSS JOIN generate_series(DATE '2026-09-01', DATE '2026-09-30', INTERVAL '1 day') AS d
 WHERE EXTRACT(ISODOW FROM d) < 6
   AND NOT (e.employee_id = 5 AND d::DATE IN ('2026-09-15', '2026-09-16', '2026-09-17'))  -- Sofia: 3 absences
   AND NOT (e.employee_id = 4 AND d::DATE IN ('2026-09-08', '2026-09-09'));               -- Liam: sick leave

-- Omar was late once (UPDATE also fires the hours trigger)
UPDATE attendance SET time_in = '09:30', status = 'late'
 WHERE employee_id = 6 AND work_date = '2026-09-02';

-- Initialize leave balances for 2026
INSERT INTO leave_balances (employee_id, leave_type_id, leave_year, allocated_days, used_days)
SELECT e.employee_id, lt.leave_type_id, 2026, COALESCE(lt.default_days_per_year, 0), 0
  FROM employees e
 CROSS JOIN leave_types lt
 WHERE lt.default_days_per_year IS NOT NULL
ON CONFLICT DO NOTHING;

-- Leave requests, then approve one through the stored procedure
INSERT INTO leave_requests (employee_id, leave_type_id, start_date, end_date, reason) VALUES
    (4, 2, '2026-09-08', '2026-09-09', 'Flu'),            -- 1: Liam, Sick
    (3, 1, '2026-10-12', '2026-10-14', 'Family trip'),    -- 2: Priya, Vacation
    (6, 1, '2026-12-20', '2026-12-31', 'Year-end break'); -- 3: Omar, Vacation (12 days)

CALL sp_approve_leave(1, 2, 'approved');   -- Liam's sick leave approved by Maria (user 2)

-- Recruitment
INSERT INTO skills (skill_name) VALUES
    ('Python'), ('SQL'), ('React'), ('JavaScript'), ('Accounting'), ('Communication'), ('Project Management');

INSERT INTO job_postings (position_id, description, requirements, slots, closing_date, created_by) VALUES
    (3, 'Build and maintain internal web applications', 'Python, SQL, React', 2, '2026-11-30', 2),   -- 1
    (2, 'Support recruitment and employee records',     'Communication',      1, '2026-11-15', 2);   -- 2

INSERT INTO applicants (first_name, last_name, email, phone, education, years_experience, source, resume_text) VALUES
    ('Daniel', 'Okafor', 'daniel.okafor@example.com', '0917-100-0001', 'BS Computer Science', 3.0, 'ai_parsed',
     'Software developer with 3 years of experience in Python, SQL and React.'),          -- 1
    ('Elena',  'Petrova','elena.petrova@example.com', '0917-100-0002', 'BS Information Technology', 1.5, 'ai_parsed',
     'Junior developer skilled in JavaScript and SQL.'),                                  -- 2
    ('Grace',  'Lim',    'grace.lim@example.com',     '0917-100-0003', 'BA Psychology', 2.0, 'manual',
     'HR assistant with strong communication skills.');                                   -- 3

INSERT INTO applicant_skills (applicant_id, skill_id, confidence) VALUES
    (1, 1, 0.98), (1, 2, 0.95), (1, 3, 0.90),
    (2, 4, 0.92), (2, 2, 0.88),
    (3, 6, 0.97);

INSERT INTO applications (job_id, applicant_id, status) VALUES
    (1, 1, 'offer'),        -- 1: ready to hire
    (1, 2, 'interview'),    -- 2
    (2, 3, 'screening');    -- 3
