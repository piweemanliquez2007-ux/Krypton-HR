-- Stored Procedure 1: monthly attendance summary per employee
CREATE OR REPLACE FUNCTION sp_attendance_summary(p_employee_id INT, p_year INT, p_month INT)
RETURNS TABLE (work_days INT, present INT, late INT, absent INT) AS $$
BEGIN
  RETURN QUERY
  SELECT COUNT(*)::INT,
         COUNT(*) FILTER (WHERE status='present')::INT,
         COUNT(*) FILTER (WHERE status='late')::INT,
         COUNT(*) FILTER (WHERE status='absent')::INT
  FROM attendance
  WHERE employee_id = p_employee_id
    AND EXTRACT(YEAR FROM work_date) = p_year
    AND EXTRACT(MONTH FROM work_date) = p_month;
END; $$ LANGUAGE plpgsql;

-- Stored Procedure 2: leave balance
CREATE OR REPLACE FUNCTION sp_leave_balance(p_employee_id INT, p_leave_type_id INT)
RETURNS NUMERIC AS $$
DECLARE bal NUMERIC;
BEGIN
  SELECT COALESCE(SUM(used_days),0) INTO bal FROM leave_balances
  WHERE employee_id=p_employee_id AND leave_type_id=p_leave_type_id;
  RETURN (SELECT COALESCE(SUM(allocated_days),0) FROM leave_balances WHERE employee_id=p_employee_id AND leave_type_id=p_leave_type_id) - bal;
END; $$ LANGUAGE plpgsql;

-- Stored Procedure 3: payroll total for a period
CREATE OR REPLACE FUNCTION sp_payroll_total(p_period_id INT)
RETURNS NUMERIC AS $$
DECLARE total NUMERIC;
BEGIN
  SELECT COALESCE(SUM(net_pay),0) INTO total FROM payslips WHERE period_id=p_period_id;
  RETURN total;
END; $$ LANGUAGE plpgsql;

-- Trigger 1: audit employee status changes
CREATE TABLE IF NOT EXISTS employee_audit (audit_id SERIAL PRIMARY KEY, employee_id INT, old_status VARCHAR, new_status VARCHAR, changed_at TIMESTAMP DEFAULT NOW());
CREATE OR REPLACE FUNCTION trg_employee_status_audit() RETURNS TRIGGER AS $$
BEGIN
  IF OLD.status IS DISTINCT FROM NEW.status THEN
    INSERT INTO employee_audit(employee_id, old_status, new_status) VALUES (NEW.employee_id, OLD.status, NEW.status);
  END IF;
  RETURN NEW;
END; $$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS trg_employee_status ON employees;
CREATE TRIGGER trg_employee_status AFTER UPDATE ON employees FOR EACH ROW EXECUTE FUNCTION trg_employee_status_audit();

-- Trigger 2: auto-update leave balance on approval
CREATE OR REPLACE FUNCTION trg_leave_approved() RETURNS TRIGGER AS $$
BEGIN
  IF NEW.status='approved' AND OLD.status IS DISTINCT FROM 'approved' THEN
    UPDATE leave_balances SET used_days = used_days + (NEW.end_date - NEW.start_date + 1)
    WHERE employee_id=NEW.employee_id AND leave_type_id=NEW.leave_type_id;
  END IF;
  RETURN NEW;
END; $$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS trg_leave_approved ON leave_requests;
CREATE TRIGGER trg_leave_approved AFTER UPDATE ON leave_requests FOR EACH ROW EXECUTE FUNCTION trg_leave_approved();

-- View 1: employee directory
CREATE OR REPLACE VIEW v_employee_directory AS
SELECT e.employee_id, e.first_name, e.last_name, e.email, d.name AS department, p.title AS position, e.status
FROM employees e LEFT JOIN positions p ON p.position_id=e.position_id
LEFT JOIN departments d ON d.department_id=p.department_id;

-- View 2: attendance summary
CREATE OR REPLACE VIEW v_attendance_summary AS
SELECT employee_id, COUNT(*) AS total_records,
  COUNT(*) FILTER (WHERE status='present') AS present,
  COUNT(*) FILTER (WHERE status='late') AS late,
  COUNT(*) FILTER (WHERE status='absent') AS absent
FROM attendance GROUP BY employee_id;

-- View 3: leave summary
CREATE OR REPLACE VIEW v_leave_summary AS
SELECT lr.employee_id, lt.name AS leave_type, COUNT(*) AS requests,
  COALESCE(SUM(lr.end_date - lr.start_date + 1),0) AS days
FROM leave_requests lr JOIN leave_types lt ON lt.leave_type_id=lr.leave_type_id
GROUP BY lr.employee_id, lt.name;
