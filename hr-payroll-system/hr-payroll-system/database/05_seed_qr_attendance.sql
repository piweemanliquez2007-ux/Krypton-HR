-- =====================================================================
-- Sample shifts, shift assignments and one demo kiosk.
-- Run after 01_schema.sql + 04_qr_attendance.sql.
-- Safe to re-run (ON CONFLICT DO NOTHING).
-- =====================================================================

INSERT INTO shifts (code, name, start_time, end_time, break_minutes, grace_minutes, is_overnight) VALUES
    ('MORN', 'Morning shift',   TIME '08:00', TIME '16:00', 60, 15, FALSE),
    ('EVE',  'Evening shift',   TIME '16:00', TIME '23:59', 30, 10, FALSE),
    ('NIGHT','Night shift',     TIME '22:00', TIME '06:00', 45, 20, TRUE)
ON CONFLICT (code) DO NOTHING;

-- Everyone on the morning shift, Priya on evenings, Omar on nights.
INSERT INTO shift_assignments (shift_id, employee_id, effective_from, work_days)
SELECT s.shift_id, e.employee_id, DATE '2026-01-01', '{1,2,3,4,5}'
  FROM shifts s CROSS JOIN employees e
 WHERE s.code = 'MORN'
ON CONFLICT DO NOTHING;

INSERT INTO shift_assignments (shift_id, employee_id, effective_from, work_days)
SELECT s.shift_id, e.employee_id, DATE '2026-01-01', '{1,2,3,4,5}'
  FROM shifts s JOIN employees e ON e.employee_no = 'EMP-01004'
 WHERE s.code = 'EVE'
ON CONFLICT DO NOTHING;

INSERT INTO shift_assignments (shift_id, employee_id, effective_from, work_days)
SELECT s.shift_id, e.employee_id, DATE '2026-01-01', '{1,2,3,4,5,6}'
  FROM shifts s JOIN employees e ON e.employee_no = 'EMP-01007'
 WHERE s.code = 'NIGHT'
ON CONFLICT DO NOTHING;

-- Demo kiosk at the main entrance.
-- api_key_hash is the SHA-256 hex of the device key. The key itself is:
--     HRQ-KIOSK-KEY-3f9c1a7d5e2b48d6
-- Compute the hash with:
--     python -c "import hashlib;print(hashlib.sha256(b'HRQ-KIOSK-KEY-3f9c1a7d5e2b48d6').hexdigest())"
INSERT INTO kiosk_devices (device_id, label, location, api_key_hash)
VALUES (
    'KIOSK-ENTRANCE-01',
    'Main entrance tablet',
    'Ground floor lobby',
    encode(digest('HRQ-KIOSK-KEY-3f9c1a7d5e2b48d6', 'sha256'), 'hex')
)
ON CONFLICT (device_id) DO NOTHING;

-- QR credentials are NOT seeded: the signed QR payload is generated on
-- request and never stored, so the credential rows are created by
-- POST /api/attendance/qr/issue (Admin/HR) or by the employee self-service
-- endpoint POST /api/attendance/qr/my-qr.
