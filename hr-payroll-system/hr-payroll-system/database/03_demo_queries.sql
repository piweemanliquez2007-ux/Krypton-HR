-- =====================================================================
-- Demo queries for the technical requirements (JOINs, subqueries, aggregates)
-- Run after 01_schema.sql and 02_seed.sql
-- =====================================================================

-- ---- A. Stored procedures in action ---------------------------------

-- A1. Generate payroll for September 2026 (period_id = 1)
CALL sp_generate_payroll(1);

-- A2. Approve a leave request (request 2, reviewed by user 2), then check the balance trigger
CALL sp_approve_leave(2, 2, 'approved');
--     Priya's Vacation used_days should be 3, Liam's Sick used_days should be 2.
SELECT employee_id, leave_type_id, allocated_days, used_days
  FROM leave_balances
 WHERE (employee_id = 3 AND leave_type_id = 1)
    OR (employee_id = 4 AND leave_type_id = 2);

-- A3. Request 3 (Omar, 12 days of Vacation) fits his 15-day balance, so it succeeds.
--     To see the "Insufficient leave balance" error, first stretch the request past 15 days:
--       UPDATE leave_requests SET start_date = '2026-11-01', end_date = '2026-11-20' WHERE request_id = 3;
CALL sp_approve_leave(3, 2, 'approved');

-- A4. Hire the applicant at the offer stage (application 1). Returns the new employee_id.
CALL sp_hire_applicant(1, 55000, CURRENT_DATE, NULL);

-- ---- B. Views --------------------------------------------------------
SELECT * FROM v_employee_summary ORDER BY department, full_name;
SELECT * FROM v_payroll_report WHERE period_name = 'September 2026' ORDER BY department, full_name;
SELECT * FROM v_recruitment_pipeline ORDER BY job_id, application_status;

-- ---- C. Multi-table JOIN: payslip with deduction breakdown -----------
SELECT e.employee_no,
       e.first_name || ' ' || e.last_name AS employee,
       d.name                             AS department,
       dt.name                            AS deduction,
       pd.amount
  FROM payslips ps
  JOIN employees          e  ON e.employee_id        = ps.employee_id
  JOIN positions          p  ON p.position_id        = e.position_id
  JOIN departments        d  ON d.department_id      = p.department_id
  JOIN payslip_deductions pd ON pd.payslip_id        = ps.payslip_id
  JOIN deduction_types    dt ON dt.deduction_type_id = pd.deduction_type_id
 WHERE ps.period_id = 1
 ORDER BY employee, deduction;

-- ---- D. Subquery: employees earning above their department average ---
SELECT e.employee_no,
       e.first_name || ' ' || e.last_name AS employee,
       d.name AS department,
       e.base_salary
  FROM employees e
  JOIN positions   p ON p.position_id   = e.position_id
  JOIN departments d ON d.department_id = p.department_id
 WHERE e.base_salary > (SELECT AVG(e2.base_salary)
                          FROM employees e2
                          JOIN positions p2 ON p2.position_id = e2.position_id
                         WHERE p2.department_id = p.department_id)
 ORDER BY department, e.base_salary DESC;

-- ---- E. Aggregates: payroll cost per department ----------------------
SELECT d.name                    AS department,
       COUNT(ps.payslip_id)      AS payslips,
       SUM(ps.gross_pay)         AS total_gross,
       SUM(ps.total_deductions)  AS total_deductions,
       SUM(ps.net_pay)           AS total_net,
       ROUND(AVG(ps.net_pay), 2) AS avg_net
  FROM payslips ps
  JOIN employees   e ON e.employee_id   = ps.employee_id
  JOIN positions   p ON p.position_id   = e.position_id
  JOIN departments d ON d.department_id = p.department_id
 WHERE ps.period_id = 1
 GROUP BY d.name
HAVING SUM(ps.net_pay) > 0
 ORDER BY total_net DESC;

-- ---- F. Subquery + aggregate: applicants who have BOTH Python and SQL -
SELECT a.applicant_id, a.first_name, a.last_name
  FROM applicants a
 WHERE a.applicant_id IN (
        SELECT aps.applicant_id
          FROM applicant_skills aps
         WHERE aps.skill_id IN (SELECT skill_id FROM skills WHERE skill_name IN ('Python', 'SQL'))
         GROUP BY aps.applicant_id
        HAVING COUNT(DISTINCT aps.skill_id) = 2);

-- ---- G. Leave usage per employee (JOIN + aggregate) ------------------
SELECT e.first_name || ' ' || e.last_name AS employee,
       SUM(lb.allocated_days)             AS allocated,
       SUM(lb.used_days)                  AS used,
       SUM(lb.allocated_days - lb.used_days) AS remaining
  FROM leave_balances lb
  JOIN employees e ON e.employee_id = lb.employee_id
 GROUP BY e.employee_id, e.first_name, e.last_name
 ORDER BY used DESC;
