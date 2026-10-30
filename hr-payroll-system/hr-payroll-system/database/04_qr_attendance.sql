-- =====================================================================
-- Enterprise HR & Payroll System - QR attendance & shift tracking
-- Run order: 01_schema.sql -> 02_seed.sql -> 04_qr_attendance.sql
--            -> 05_seed_qr_attendance.sql   (03_demo_queries.sql optional)
-- Idempotent: safe to re-run (IF NOT EXISTS / OR REPLACE / DROP+CREATE TRIGGER).
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid(), digest()

-- ---------------------------------------------------------------------
-- 0. Supabase Auth bridge
-- The API authenticates with its own JWT (see app/security.py). If you
-- migrate to Supabase Auth, link the two here: users.auth_user_id -> auth.users.id
-- ---------------------------------------------------------------------
DO $$
BEGIN
    IF to_regclass('auth.users') IS NOT NULL THEN
        ALTER TABLE users
            ADD COLUMN IF NOT EXISTS auth_user_id UUID UNIQUE REFERENCES auth.users(id) ON DELETE SET NULL;
    END IF;
END $$;

-- ---------------------------------------------------------------------
-- 1. SHIFTS  (the shift definitions a kiosk validates scans against)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS shifts (
    shift_id       SERIAL PRIMARY KEY,
    code           VARCHAR(20)  NOT NULL UNIQUE,
    name           VARCHAR(60)  NOT NULL,
    start_time     TIME NOT NULL,
    end_time       TIME NOT NULL,
    break_minutes  INT NOT NULL DEFAULT 60 CHECK (break_minutes  >= 0),
    grace_minutes  INT NOT NULL DEFAULT 15 CHECK (grace_minutes  >= 0),
    is_overnight   BOOLEAN NOT NULL DEFAULT FALSE,
    active         BOOLEAN NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_shift_window CHECK (start_time <> end_time)
);

-- Who works which shift, and from when. work_days uses ISO weekday (1=Mon..7=Sun).
CREATE TABLE IF NOT EXISTS shift_assignments (
    assignment_id  SERIAL PRIMARY KEY,
    shift_id       INT  NOT NULL REFERENCES shifts(shift_id) ON DELETE CASCADE,
    employee_id    INT  NOT NULL REFERENCES employees(employee_id) ON DELETE CASCADE,
    effective_from DATE NOT NULL DEFAULT CURRENT_DATE,
    effective_to   DATE,
    work_days      INT[] NOT NULL DEFAULT '{1,2,3,4,5}',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_assignment_window CHECK (effective_to IS NULL OR effective_to >= effective_from),
    UNIQUE (shift_id, employee_id, effective_from)
);

-- ---------------------------------------------------------------------
-- 2. QR CREDENTIALS  (one per employee: what the QR code stands for)
--
-- The QR image never leaves the employee. The payload that is encoded
-- into it is signed with the server secret (HMAC-SHA256) and carries:
--     e = employee_id, c = credential_id, s = sequence, m = mode,
--     i = issued at, x = expires at
-- The row below holds the *state* of that credential (revoked? locked?
-- which PIN? which sequence was consumed last?), never the secret itself.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS qr_credentials (
    credential_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id     INT  NOT NULL REFERENCES employees(employee_id) ON DELETE CASCADE,
    mode            VARCHAR(10) NOT NULL DEFAULT 'static'
                    CHECK (mode IN ('static','dynamic')),
    status          VARCHAR(12) NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active','suspended','revoked')),
    require_pin     BOOLEAN NOT NULL DEFAULT TRUE,   -- 2nd factor: PIN + QR
    pin_hash        VARCHAR(255),                    -- bcrypt hash of the kiosk PIN
    pin_set_at      TIMESTAMPTZ,
    failed_attempts INT NOT NULL DEFAULT 0,          -- wrong-PIN counter
    locked_until    TIMESTAMPTZ,                     -- set after too many failures
    seq_counter     BIGINT NOT NULL DEFAULT 0,       -- last sequence issued
    last_used_seq   BIGINT NOT NULL DEFAULT 0,       -- last sequence accepted (replay guard)
    scan_count      BIGINT NOT NULL DEFAULT 0,
    last_scanned_at TIMESTAMPTZ,
    issued_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ,                     -- optional hard expiry of the badge
    rotated_at      TIMESTAMPTZ,
    revoked_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Also for databases that were created by an earlier version of this file.
ALTER TABLE qr_credentials ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;

-- One live credential per employee and per mode:
--   static  = printed badge (long lived, photo replay only stopped by the PIN)
--   dynamic = mobile QR (short lived, one time use, useless in a photo after the TTL)
CREATE UNIQUE INDEX IF NOT EXISTS uq_qr_credential_live_employee
    ON qr_credentials(employee_id, mode) WHERE status <> 'revoked';

CREATE INDEX IF NOT EXISTS idx_qr_credential_employee ON qr_credentials(employee_id);

-- ---------------------------------------------------------------------
-- 3. KIOSK DEVICES  (the tablets at the entrance)
-- A kiosk authenticates itself with X-Kiosk-Key, so the scan endpoint
-- cannot be called by just anyone with a stolen QR photo.
-- The key is a 32-byte random secret, so it is stored as a SHA-256 hex
-- digest (fast lookup + compare_digest); low-entropy secrets such as the
-- employee PIN use bcrypt instead (see qr_credentials.pin_hash).
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS kiosk_devices (
    device_id      VARCHAR(64) PRIMARY KEY,          -- id stored on the tablet
    label          VARCHAR(120) NOT NULL,
    location       VARCHAR(120),
    api_key_hash   CHAR(64) NOT NULL,                -- sha256 hex of the kiosk key
    status         VARCHAR(12) NOT NULL DEFAULT 'active'
                   CHECK (status IN ('active','suspended','revoked')),
    last_seen_at   TIMESTAMPTZ,
    last_ip        INET,
    scan_count     BIGINT NOT NULL DEFAULT 0,
    rejected_count BIGINT NOT NULL DEFAULT 0,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------
-- 3b. PENDING SCAN CHALLENGES  (step 1 of the QR + PIN handshake)
-- Step 1 validates the QR and creates a challenge here; step 2 sends the
-- PIN. The punch is only written once the PIN is confirmed.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS qr_scan_challenges (
    challenge_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    credential_id  UUID NOT NULL REFERENCES qr_credentials(credential_id) ON DELETE CASCADE,
    employee_id    INT  NOT NULL REFERENCES employees(employee_id) ON DELETE CASCADE,
    work_date      DATE NOT NULL,
    event_type     VARCHAR(12) NOT NULL CHECK (event_type IN ('time_in','time_out','break_in','break_out')),
    kiosk_device_id VARCHAR(64) REFERENCES kiosk_devices(device_id) ON DELETE SET NULL,
    shift_id       INT REFERENCES shifts(shift_id) ON DELETE SET NULL,
    payload_seq    BIGINT NOT NULL DEFAULT 0,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at     TIMESTAMPTZ NOT NULL,
    consumed_at    TIMESTAMPTZ,
    failed_attempts INT NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_qr_challenge_employee ON qr_scan_challenges(employee_id, expires_at);

-- ---------------------------------------------------------------------
-- 4. ATTENDANCE EVENTS  (the append-only punch log, one row per scan)
-- This is the source of truth for shift tracking: many events per day.
-- The legacy "attendance" table stays the DAILY summary that payroll reads.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS attendance_events (
    event_id        BIGSERIAL PRIMARY KEY,
    employee_id     INT NOT NULL REFERENCES employees(employee_id) ON DELETE CASCADE,
    work_date       DATE NOT NULL,
    event_type      VARCHAR(12) NOT NULL
                    CHECK (event_type IN ('time_in','time_out','break_in','break_out')),
    occurred_at     TIMESTAMPTZ NOT NULL,             -- absolute instant (UTC)
    local_time      TIME NOT NULL,                    -- wall clock at the kiosk
    source          VARCHAR(15) NOT NULL DEFAULT 'qr'
                    CHECK (source IN ('manual','qr','mobile','import')),
    method          VARCHAR(15) NOT NULL DEFAULT 'qr'
                    CHECK (method IN ('qr','pin','manual','admin','mobile')),
    shift_id        INT REFERENCES shifts(shift_id) ON DELETE SET NULL,
    credential_id   UUID REFERENCES qr_credentials(credential_id) ON DELETE SET NULL,
    kiosk_device_id VARCHAR(64) REFERENCES kiosk_devices(device_id) ON DELETE SET NULL,
    status          VARCHAR(12) NOT NULL DEFAULT 'accepted'
                    CHECK (status IN ('accepted','reverted')),
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_attendance_events_emp_date ON attendance_events(employee_id, work_date);
CREATE INDEX IF NOT EXISTS idx_attendance_events_date    ON attendance_events(work_date);
CREATE INDEX IF NOT EXISTS idx_attendance_events_kiosk   ON attendance_events(kiosk_device_id);

-- ---------------------------------------------------------------------
-- 5. QR SCAN AUDIT  (every attempt, accepted or not)
-- Used for fraud detection ("this photo was replayed 12 times") and for
-- the per-employee / per-kiosk rate limits.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS qr_scan_audit (
    audit_id      BIGSERIAL PRIMARY KEY,
    employee_id   INT REFERENCES employees(employee_id) ON DELETE SET NULL,
    credential_id UUID REFERENCES qr_credentials(credential_id) ON DELETE SET NULL,
    device_id     VARCHAR(64),
    event_id      BIGINT REFERENCES attendance_events(event_id) ON DELETE SET NULL,
    outcome       VARCHAR(20) NOT NULL
                  CHECK (outcome IN ('accepted','pin_required','pin_failed','invalid_qr',
                                     'expired','replay','locked','rate_limited','unknown_employee',
                                     'duplicate','inactive')),
    reason        VARCHAR(160),
    ip_address    INET,
    user_agent    VARCHAR(200),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_qr_scan_audit_emp    ON qr_scan_audit(employee_id, created_at);
CREATE INDEX IF NOT EXISTS idx_qr_scan_audit_device ON qr_scan_audit(device_id, created_at);
CREATE INDEX IF NOT EXISTS idx_qr_scan_audit_time   ON qr_scan_audit(created_at);

-- The outcome list has to cover every reason the service can log, including
-- the two reasons that mean "the scanned bytes were not a valid QR payload".
-- The constraint is replaced (not only created) so re-running this script also
-- upgrades a database that was created by an earlier version of the file.
ALTER TABLE qr_scan_audit DROP CONSTRAINT IF EXISTS qr_scan_audit_outcome_check;
ALTER TABLE qr_scan_audit
    ADD CONSTRAINT qr_scan_audit_outcome_check CHECK (outcome IN (
        'accepted','pin_required','pin_failed','invalid_qr','expired','replay',
        'locked','rate_limited','unknown_employee','duplicate','inactive',
        'malformed','bad_signature'));

-- ---------------------------------------------------------------------
-- 6. EXTEND THE LEGACY DAILY "attendance" TABLE
-- It stays the per-employee/per-day summary that sp_generate_payroll reads.
-- ---------------------------------------------------------------------
ALTER TABLE attendance ADD COLUMN IF NOT EXISTS shift_id     INT REFERENCES shifts(shift_id) ON DELETE SET NULL;
ALTER TABLE attendance ADD COLUMN IF NOT EXISTS source       VARCHAR(15) NOT NULL DEFAULT 'manual';
ALTER TABLE attendance ADD COLUMN IF NOT EXISTS event_count  INT NOT NULL DEFAULT 0;
ALTER TABLE attendance ADD COLUMN IF NOT EXISTS is_overnight BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE attendance ADD COLUMN IF NOT EXISTS updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW();

-- Night shift: a punch-out at 02:00 is earlier than a punch-in at 22:00.
-- The daily row now allows that when the shift is flagged as overnight.
ALTER TABLE attendance DROP CONSTRAINT IF EXISTS chk_time_order;
ALTER TABLE attendance
    ADD CONSTRAINT chk_time_order CHECK (
        time_out IS NULL OR time_in IS NULL OR time_out >= time_in OR is_overnight
    );

-- Recompute hours across midnight for overnight shifts.
CREATE OR REPLACE FUNCTION fn_attendance_compute_hours() RETURNS TRIGGER AS $$
DECLARE
    v_span   INTERVAL;
    v_hours  NUMERIC;
BEGIN
    IF NEW.time_in IS NOT NULL AND NEW.time_out IS NOT NULL THEN
        v_span := (NEW.time_out - NEW.time_in);
        IF v_span < INTERVAL '0 seconds' THEN          -- overnight shift
            v_span := v_span + INTERVAL '24 hours';
        END IF;
        v_hours := EXTRACT(EPOCH FROM v_span) / 3600.0;
        IF v_hours > 5 THEN
            v_hours := v_hours - 1;                    -- unpaid break
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

DROP TRIGGER IF EXISTS trg_attendance_compute_hours ON attendance;
CREATE TRIGGER trg_attendance_compute_hours
    BEFORE INSERT OR UPDATE OF time_in, time_out ON attendance
    FOR EACH ROW EXECUTE FUNCTION fn_attendance_compute_hours();

-- ---------------------------------------------------------------------
-- 7. VIEW: exact hours per shift (paired in->out events)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_shift_hours AS
SELECT i.employee_id,
       i.work_date,
       i.shift_id,
       s.code AS shift_code,
       s.name AS shift_name,
       COUNT(*)                                  AS segments_worked,
       ROUND(SUM(EXTRACT(EPOCH FROM (o.occurred_at - i.occurred_at)) / 3600.0)::numeric, 2)
                                                  AS hours_worked
  FROM attendance_events i
  JOIN LATERAL (
        SELECT e2.occurred_at
          FROM attendance_events e2
         WHERE e2.employee_id = i.employee_id
           AND e2.work_date   = i.work_date
           AND e2.event_type  = 'time_out'
           AND e2.status       = 'accepted'
           AND e2.occurred_at > i.occurred_at
         ORDER BY e2.occurred_at
         LIMIT 1
  ) o ON TRUE
  LEFT JOIN shifts s ON s.shift_id = i.shift_id
  WHERE i.event_type = 'time_in'
    AND i.status      = 'accepted'
  GROUP BY i.employee_id, i.work_date, i.shift_id, s.code, s.name;

-- ---------------------------------------------------------------------
-- 8. COMPATIBILITY VIEWS
-- The punch log and the scan trail are also reachable under the names used
-- in the functional specification. They are plain views over the tables
-- above, so there is still exactly one copy of the data.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW attendance_punches AS
SELECT * FROM attendance_events;

CREATE OR REPLACE VIEW attendance_scan_audit AS
SELECT * FROM qr_scan_audit;
