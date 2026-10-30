"""REPOSITORY layer: SQL only. No business rules, no HTTP, no commit (services commit)."""
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

# ---------------------------------------------------------------- credentials
CREDENTIAL_SELECT = """
    SELECT c.credential_id, c.employee_id, c.mode, c.status, c.require_pin,
           c.pin_hash, c.pin_set_at, c.failed_attempts, c.locked_until,
           c.seq_counter, c.last_used_seq, c.scan_count, c.last_scanned_at,
           c.issued_at, c.expires_at,
           e.employee_no, e.first_name || ' ' || e.last_name AS employee_name
      FROM qr_credentials c
      JOIN employees e ON e.employee_id = c.employee_id
"""


def find_live_credential(db: Session, employee_id: int, mode: str) -> dict | None:
    """The employee's current credential for a mode, if there is one."""
    row = db.execute(
        text(CREDENTIAL_SELECT + " WHERE c.employee_id = :emp AND c.mode = :mode "
                                 "AND c.status <> 'revoked'"),
        {"emp": employee_id, "mode": mode},
    ).mappings().first()
    return dict(row) if row else None


def find_credential_by_id(db: Session, credential_id: UUID) -> dict | None:
    row = db.execute(
        text(CREDENTIAL_SELECT + " WHERE c.credential_id = :cid"),
        {"cid": str(credential_id)},
    ).mappings().first()
    return dict(row) if row else None


def insert_credential(db: Session, employee_id: int, mode: str, require_pin: bool,
                      pin_hash: str | None) -> dict:
    """Creates a credential row. seq_counter starts at 1 so seq 0 is never valid."""
    row = db.execute(
        text(
            """
            INSERT INTO qr_credentials
                (employee_id, mode, require_pin, pin_hash, pin_set_at, seq_counter)
            VALUES (:emp, :mode, :require_pin, :pin_hash, :pin_set_at, 1)
            RETURNING credential_id, seq_counter
            """
        ),
        {
            "emp": employee_id,
            "mode": mode,
            "require_pin": require_pin,
            "pin_hash": pin_hash,
            "pin_set_at": datetime.now() if pin_hash else None,
        },
    ).mappings().one()
    return dict(row)


def revoke_credentials(db: Session, employee_id: int, mode: str) -> int:
    """Revokes every live credential of an employee for a mode."""
    result = db.execute(
        text(
            """
            UPDATE qr_credentials
               SET status = 'revoked', revoked_at = NOW()
             WHERE employee_id = :emp AND mode = :mode AND status <> 'revoked'
            """
        ),
        {"emp": employee_id, "mode": mode},
    )
    return result.rowcount


def bump_seq_counter(db: Session, credential_id: UUID) -> int:
    """Allocates the next sequence number for a dynamic QR code."""
    return db.execute(
        text(
            """
            UPDATE qr_credentials
               SET seq_counter = seq_counter + 1
             WHERE credential_id = :cid
            RETURNING seq_counter
            """
        ),
        {"cid": str(credential_id)},
    ).scalar_one()


def mark_seq_used(db: Session, credential_id: UUID, seq: int) -> bool:
    """
    Records that a sequence was consumed. Returns False if the sequence was
    already used (replay), because the WHERE clause then matches no row.
    """
    result = db.execute(
        text(
            """
            UPDATE qr_credentials
               SET last_used_seq = :seq, scan_count = scan_count + 1, last_scanned_at = NOW()
             WHERE credential_id = :cid AND last_used_seq < :seq
            """
        ),
        {"cid": str(credential_id), "seq": seq},
    )
    return result.rowcount > 0


def register_failed_pin(db: Session, credential_id: UUID, max_attempts: int,
                        lockout_seconds: int) -> dict:
    """Counts a wrong PIN and locks the credential once the limit is reached."""
    row = db.execute(
        text(
            """
            UPDATE qr_credentials
               SET failed_attempts = failed_attempts + 1,
                   locked_until = CASE
                       WHEN failed_attempts + 1 >= :max_attempts
                           THEN NOW() + (:lockout || ' seconds')::interval
                       ELSE locked_until END
             WHERE credential_id = :cid
            RETURNING failed_attempts, locked_until
            """
        ),
        {
            "cid": str(credential_id),
            "max_attempts": max_attempts,
            "lockout": lockout_seconds,
        },
    ).mappings().one()
    return dict(row)


def reset_failed_pin(db: Session, credential_id: UUID) -> None:
    db.execute(
        text(
            """
            UPDATE qr_credentials
               SET failed_attempts = 0, locked_until = NULL
             WHERE credential_id = :cid
            """
        ),
        {"cid": str(credential_id)},
    )


def set_pin(db: Session, credential_id: UUID, pin_hash: str) -> None:
    db.execute(
        text(
            """
            UPDATE qr_credentials
               SET pin_hash = :pin, pin_set_at = NOW(),
                   failed_attempts = 0, locked_until = NULL
             WHERE credential_id = :cid
            """
        ),
        {"pin": pin_hash, "cid": str(credential_id)},
    )


def set_status(db: Session, credential_id: UUID, status: str) -> None:
    db.execute(
        text("UPDATE qr_credentials SET status = :st WHERE credential_id = :cid"),
        {"st": status, "cid": str(credential_id)},
    )


# -------------------------------------------------------------------- kiosks
def find_kiosk(db: Session, device_id: str) -> dict | None:
    row = db.execute(
        text(
            """
            SELECT device_id, label, location, api_key_hash, status,
                   last_seen_at, last_ip, scan_count, rejected_count
              FROM kiosk_devices WHERE device_id = :d
            """
        ),
        {"d": device_id},
    ).mappings().first()
    return dict(row) if row else None


def insert_kiosk(db: Session, device_id: str, label: str, location: str | None,
                 api_key_hash: str) -> dict:
    row = db.execute(
        text(
            """
            INSERT INTO kiosk_devices (device_id, label, location, api_key_hash)
            VALUES (:d, :label, :loc, :hash)
            RETURNING device_id, label, location, status, created_at
            """
        ),
        {"d": device_id, "label": label, "loc": location, "hash": api_key_hash},
    ).mappings().one()
    return dict(row)


def list_kiosks(db: Session) -> list[dict]:
    rows = db.execute(
        text(
            """
            SELECT device_id, label, location, status, last_seen_at, last_ip,
                   scan_count, rejected_count, created_at
              FROM kiosk_devices ORDER BY label
            """
        )
    ).mappings().all()
    return [dict(r) for r in rows]


def touch_kiosk(db: Session, device_id: str, ip: str | None, accepted: bool) -> None:
    db.execute(
        text(
            """
            UPDATE kiosk_devices
               SET last_seen_at = NOW(), last_ip = :ip,
                   scan_count = scan_count + :up,
                   rejected_count = rejected_count + :down
             WHERE device_id = :d
            """
        ),
        {
            "d": device_id,
            "ip": ip,
            "up": 1 if accepted else 0,
            "down": 0 if accepted else 1,
        },
    )


# ------------------------------------------------------------------ challeng
def insert_challenge(db: Session, credential_id: UUID, employee_id: int, work_date: date,
                      event_type: str, device_id: str | None, shift_id: int | None,
                      seq: int, expires_at: datetime) -> UUID:
    return db.execute(
        text(
            """
            INSERT INTO qr_scan_challenges
                (credential_id, employee_id, work_date, event_type,
                 kiosk_device_id, shift_id, payload_seq, expires_at)
            VALUES (:cid, :emp, :wd, :et, :dev, :shift, :seq, :exp)
            RETURNING challenge_id
            """
        ),
        {
            "cid": str(credential_id),
            "emp": employee_id,
            "wd": work_date,
            "et": event_type,
            "dev": device_id,
            "shift": shift_id,
            "seq": seq,
            "exp": expires_at,
        },
    ).scalar_one()


def find_challenge(db: Session, challenge_id: UUID) -> dict | None:
    row = db.execute(
        text(
            """
            SELECT c.challenge_id, c.credential_id, c.employee_id, c.work_date,
                   c.event_type, c.kiosk_device_id, c.shift_id, c.payload_seq,
                   c.created_at, c.expires_at, c.consumed_at, c.failed_attempts,
                   e.employee_no, e.first_name || ' ' || e.last_name AS employee_name
              FROM qr_scan_challenges c
              JOIN employees e ON e.employee_id = c.employee_id
             WHERE c.challenge_id = :id
            """
        ),
        {"id": str(challenge_id)},
    ).mappings().first()
    return dict(row) if row else None


def consume_challenge(db: Session, challenge_id: UUID) -> bool:
    """Marks a challenge as used. False if it was already used (replay)."""
    result = db.execute(
        text(
            """
            UPDATE qr_scan_challenges
               SET consumed_at = NOW()
             WHERE challenge_id = :id AND consumed_at IS NULL
            """
        ),
        {"id": str(challenge_id)},
    )
    return result.rowcount > 0


def count_failed_challenge_attempts(db: Session, challenge_id: UUID) -> int:
    return db.execute(
        text(
            """
            UPDATE qr_scan_challenges
               SET failed_attempts = failed_attempts + 1
             WHERE challenge_id = :id
            RETURNING failed_attempts
            """
        ),
        {"id": str(challenge_id)},
    ).scalar_one()


def purge_expired_challenges(db: Session) -> None:
    db.execute(
        text("DELETE FROM qr_scan_challenges WHERE expires_at < NOW() - INTERVAL '1 hour'")
    )


# -------------------------------------------------------------------- events
EVENT_SELECT = """
    SELECT e.event_id, e.employee_id,
           emp.first_name || ' ' || emp.last_name AS employee_name,
           e.work_date, e.event_type, e.occurred_at,
           to_char(e.local_time, 'HH24:MI:SS') AS local_time,
           e.source, e.method, e.shift_id, s.code AS shift_code,
           e.kiosk_device_id, e.status
      FROM attendance_events e
      JOIN employees emp ON emp.employee_id = e.employee_id
      LEFT JOIN shifts s ON s.shift_id = e.shift_id
"""


def last_event_for_date(db: Session, employee_id: int, work_date: date) -> dict | None:
    """
    The most recent accepted event of the day. This is what decides whether
    the next scan is a time-in or a time-out.
    """
    row = db.execute(
        text(EVENT_SELECT + " WHERE e.employee_id = :emp AND e.work_date = :wd "
                             "AND e.status = 'accepted' ORDER BY e.occurred_at DESC LIMIT 1"),
        {"emp": employee_id, "wd": work_date},
    ).mappings().first()
    return dict(row) if row else None


def last_event_at(db: Session, employee_id: int) -> dict | None:
    """The most recent accepted event overall, used for the anti-double-scan gap."""
    row = db.execute(
        text(EVENT_SELECT + " WHERE e.employee_id = :emp AND e.status = 'accepted' "
                             "ORDER BY e.occurred_at DESC LIMIT 1"),
        {"emp": employee_id},
    ).mappings().first()
    return dict(row) if row else None


def insert_event(db: Session, employee_id: int, work_date: date, event_type: str,
                 occurred_at: datetime, local_time: str, source: str, method: str,
                 shift_id: int | None, credential_id: UUID | None,
                 device_id: str | None, notes: str | None) -> int:
    return db.execute(
        text(
            """
            INSERT INTO attendance_events
                (employee_id, work_date, event_type, occurred_at, local_time,
                 source, method, shift_id, credential_id, kiosk_device_id, notes)
            VALUES (:emp, :wd, :et, :at, :lt, :src, :m, :shift, :cred, :dev, :notes)
            RETURNING event_id
            """
        ),
        {
            "emp": employee_id,
            "wd": work_date,
            "et": event_type,
            "at": occurred_at,
            "lt": local_time,
            "src": source,
            "m": method,
            "shift": shift_id,
            "cred": str(credential_id) if credential_id else None,
            "dev": device_id,
            "notes": notes,
        },
    ).scalar_one()


def upsert_daily_attendance(db: Session, employee_id: int, work_date: date,
                             local_time: str, event_type: str, shift_id: int | None,
                             is_overnight: bool, source: str,
                             status: str = "present") -> int:
    """
    Keeps the legacy daily "attendance" summary in sync with the event log,
    because sp_generate_payroll reads that table.
    The first event of the day sets time_in, the last one sets time_out.
    The status is only ever upgraded (present -> late), never downgraded, so a
    later punch cannot erase a late arrival that was already recorded.
    """
    return db.execute(
        text(
            """
            INSERT INTO attendance
                (employee_id, work_date, time_in, time_out, status, shift_id,
                 source, event_count, is_overnight, updated_at)
            VALUES (:emp, :wd,
                    CASE WHEN :et IN ('time_in','break_in') THEN CAST(:lt AS TIME) END,
                    NULL,
                    :status,
                    :shift, :src, 1, :overnight, NOW())
            ON CONFLICT (employee_id, work_date) DO UPDATE
                SET time_in = CASE
                        WHEN :et IN ('time_in','break_in')
                             AND (attendance.time_in IS NULL OR CAST(:lt AS TIME) < attendance.time_in)
                             THEN CAST(:lt AS TIME)
                        ELSE attendance.time_in END,
                    time_out = CASE
                        WHEN :et IN ('time_out','break_out')
                             AND (attendance.time_out IS NULL OR CAST(:lt AS TIME) > attendance.time_out)
                             THEN CAST(:lt AS TIME)
                        ELSE attendance.time_out END,
                    event_count = attendance.event_count + 1,
                    shift_id = COALESCE(attendance.shift_id, :shift),
                    is_overnight = :overnight,
                    source = :src,
                    status = CASE WHEN :status = 'late' THEN 'late'
                                  ELSE attendance.status END,
                    updated_at = NOW()
            RETURNING attendance_id
            """
        ),
        {
            "emp": employee_id,
            "wd": work_date,
            "lt": local_time,
            "et": event_type,
            "shift": shift_id,
            "src": source,
            "overnight": is_overnight,
            "status": status,
        },
    ).scalar_one()


def list_events(db: Session, *, employee_id: int | None = None,
                work_date: date | None = None, device_id: str | None = None,
                limit: int = 100, skip: int = 0) -> list[dict]:
    conditions: list[str] = []
    params: dict = {"limit": limit, "skip": skip}
    if employee_id is not None:
        conditions.append("e.employee_id = :emp")
        params["emp"] = employee_id
    if work_date is not None:
        conditions.append("e.work_date = :wd")
        params["wd"] = work_date
    if device_id is not None:
        conditions.append("e.kiosk_device_id = :dev")
        params["dev"] = device_id
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = db.execute(
        text(f"{EVENT_SELECT} {where} ORDER BY e.occurred_at DESC LIMIT :limit OFFSET :skip"),
        params,
    ).mappings().all()
    return [dict(r) for r in rows]


# --------------------------------------------------------------------- audit
def insert_audit(db: Session, outcome: str, employee_id: int | None,
                 credential_id: UUID | None, device_id: str | None,
                 event_id: int | None, reason: str | None, ip: str | None,
                 user_agent: str | None) -> None:
    db.execute(
        text(
            """
            INSERT INTO qr_scan_audit
                (employee_id, credential_id, device_id, event_id, outcome,
                 reason, ip_address, user_agent)
            VALUES (:emp, :cred, :dev, :ev, :out, :reason, :ip, :ua)
            """
        ),
        {
            "emp": employee_id,
            "cred": str(credential_id) if credential_id else None,
            "dev": device_id,
            "ev": event_id,
            "out": outcome,
            "reason": reason,
            "ip": ip,
            "ua": (user_agent or "")[:200] or None,
        },
    )


def count_scans_since(db: Session, employee_id: int | None, device_id: str | None,
                      minutes: int) -> int:
    """Counts recent scans for the rate limit (per employee, per kiosk)."""
    if employee_id is not None:
        row = db.execute(
            text(
                """
                SELECT COUNT(*) FROM qr_scan_audit
                 WHERE employee_id = :emp AND created_at > NOW() - (:mins || ' minutes')::interval
                """
            ),
            {"emp": employee_id, "mins": minutes},
        ).scalar_one()
    else:
        row = db.execute(
            text(
                """
                SELECT COUNT(*) FROM qr_scan_audit
                 WHERE device_id = :dev AND created_at > NOW() - (:mins || ' minutes')::interval
                """
            ),
            {"dev": device_id, "mins": minutes},
        ).scalar_one()
    return int(row)


def list_audit(db: Session, *, employee_id: int | None = None, device_id: str | None = None,
               limit: int = 100) -> list[dict]:
    conditions: list[str] = []
    params: dict = {"limit": limit}
    if employee_id is not None:
        conditions.append("a.employee_id = :emp")
        params["emp"] = employee_id
    if device_id is not None:
        conditions.append("a.device_id = :dev")
        params["dev"] = device_id
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = db.execute(
        text(
            f"""
            SELECT a.audit_id, a.employee_id, a.device_id, a.outcome, a.reason,
                   a.ip_address, a.created_at,
                   e.employee_no, e.first_name || ' ' || e.last_name AS employee_name
              FROM qr_scan_audit a
              LEFT JOIN employees e ON e.employee_id = a.employee_id
              {where}
             ORDER BY a.created_at DESC
             LIMIT :limit
            """
        ),
        params,
    ).mappings().all()
    return [dict(r) for r in rows]


# -------------------------------------------------------------------- shifts
def list_shifts(db: Session) -> list[dict]:
    rows = db.execute(
        text(
            """
            SELECT s.shift_id, s.code, s.name,
                   to_char(s.start_time, 'HH24:MI') AS start_time,
                   to_char(s.end_time, 'HH24:MI') AS end_time,
                   s.break_minutes, s.grace_minutes, s.is_overnight,
                   COALESCE(
                       (SELECT array_agg(e.employee_no ORDER BY e.employee_no)
                          FROM shift_assignments sa
                          JOIN employees e ON e.employee_id = sa.employee_id
                         WHERE sa.shift_id = s.shift_id), '{}') AS assigned_employees
              FROM shifts s WHERE s.active ORDER BY s.start_time
            """
        )
    ).mappings().all()
    return [dict(r) for r in rows]


def insert_shift(db: Session, code: str, name: str, start_time: str, end_time: str,
                 break_minutes: int, grace_minutes: int, is_overnight: bool) -> int:
    return db.execute(
        text(
            """
            INSERT INTO shifts (code, name, start_time, end_time, break_minutes,
                                grace_minutes, is_overnight)
            VALUES (:code, :name, CAST(:start AS TIME), CAST(:end AS TIME),
                    :brk, :grace, :night)
            RETURNING shift_id
            """
        ),
        {
            "code": code, "name": name, "start": start_time, "end": end_time,
            "brk": break_minutes, "grace": grace_minutes, "night": is_overnight,
        },
    ).scalar_one()


def assign_shift(db: Session, shift_id: int, employee_id: int,
                 work_days: list[int]) -> None:
    db.execute(
        text(
            """
            INSERT INTO shift_assignments (shift_id, employee_id, work_days)
            VALUES (:shift, :emp, CAST(:days AS INT[]))
            ON CONFLICT (shift_id, employee_id, effective_from) DO UPDATE
                SET work_days = EXCLUDED.work_days
            """
        ),
        {"shift": shift_id, "emp": employee_id, "days": "{" + ",".join(map(str, work_days)) + "}"},
    )


def current_shift_for(db: Session, employee_id: int, work_date: date,
                      iso_weekday: int) -> dict | None:
    """
    The shift the employee is rostered on for that date, used to label punches
    and to flag out-of-shift scans.
    """
    row = db.execute(
        text(
            """
            SELECT s.shift_id, s.code, s.name, s.start_time, s.end_time,
                   s.break_minutes, s.grace_minutes, s.is_overnight
              FROM shift_assignments a
              JOIN shifts s ON s.shift_id = a.shift_id
             WHERE a.employee_id = :emp
               AND a.effective_from <= :wd
               AND (a.effective_to IS NULL OR a.effective_to >= :wd)
               AND :dow = ANY(a.work_days)
               AND s.active
             ORDER BY a.effective_from DESC, s.start_time
             LIMIT 1
            """
        ),
        {"emp": employee_id, "wd": work_date, "dow": iso_weekday},
    ).mappings().first()
    return dict(row) if row else None


def shift_hours(db: Session, employee_id: int, work_date: date) -> list[dict]:
    rows = db.execute(
        text(
            """
            SELECT employee_id, work_date, shift_id, shift_code, shift_name,
                   segments_worked, hours_worked
              FROM v_shift_hours
             WHERE employee_id = :emp AND work_date = :wd
             ORDER BY shift_id
            """
        ),
        {"emp": employee_id, "wd": work_date},
    ).mappings().all()
    return [dict(r) for r in rows]
