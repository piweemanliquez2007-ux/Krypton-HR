from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import Number

# What the employee does at the kiosk.
PunchType = Literal["time_in", "time_out", "break_in", "break_out"]
CredentialMode = Literal["static", "dynamic"]


# ------------------------------------------------------------------ requests
class QrScanRequest(BaseModel):
    """
    Step 1 of the kiosk handshake: the employee holds their QR up to the tablet.

    qr_payload is the raw text decoded from the QR image by the kiosk scanner.
    It is NOT the employee id: it is a signed payload, so a photo of somebody
    else's badge cannot be edited into a different employee.
    """

    qr_payload: str = Field(..., min_length=10, max_length=512)
    pin: str | None = Field(
        None, min_length=4, max_length=8,
        description="Kiosk PIN. Sent on step 2 (or in step 1 for a fast path).",
    )
    device_id: str | None = Field(
        None, min_length=3, max_length=64,
        description="Optional in the body. The X-Device-Id header is authoritative, "
                    "because that is the id the kiosk key is checked against.",
    )
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    client_time: datetime | None = Field(
        None, description="Device clock at scan time. Informational only."
    )


class QrScanConfirmRequest(BaseModel):
    """Step 2: the employee types their PIN on the kiosk keypad."""

    challenge_id: str = Field(..., min_length=36, max_length=36)
    pin: str = Field(..., min_length=4, max_length=8)


class QrIssueRequest(BaseModel):
    """Admin/HR issues (or re-issues) the QR badge of an employee."""

    employee_id: int
    mode: CredentialMode = "static"
    require_pin: bool = True
    pin: str | None = Field(None, min_length=4, max_length=8)


class QrRotateRequest(BaseModel):
    """Admin/HR revokes a credential and issues a fresh one."""

    employee_id: int
    mode: CredentialMode = "static"
    reason: str | None = Field(None, max_length=200)


class KioskRegisterRequest(BaseModel):
    """Admin/HR enrolls a new kiosk tablet."""

    device_id: str = Field(..., min_length=3, max_length=64)
    label: str = Field(..., min_length=2, max_length=120)
    location: str | None = Field(None, max_length=120)


class ShiftCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=20)
    name: str = Field(..., min_length=2, max_length=60)
    start_time: str = Field(..., pattern=r"^\d{2}:\d{2}$")
    end_time: str = Field(..., pattern=r"^\d{2}:\d{2}$")
    break_minutes: int = Field(60, ge=0, le=240)
    grace_minutes: int = Field(15, ge=0, le=120)
    is_overnight: bool = False
    work_days: list[int] = Field(default_factory=lambda: [1, 2, 3, 4, 5])
    employee_ids: list[int] = Field(default_factory=list)

    @field_validator("work_days")
    @classmethod
    def _valid_days(cls, value: list[int]) -> list[int]:
        if not value or any(d < 1 or d > 7 for d in value):
            raise ValueError("work_days must use ISO weekday numbers 1 (Mon) to 7 (Sun)")
        return sorted(set(value))

    @field_validator("start_time", "end_time")
    @classmethod
    def _valid_time(cls, value: str) -> str:
        hour, minute = (int(part) for part in value.split(":"))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError("Time must be HH:MM in 24-hour format")
        return value


# ----------------------------------------------------------------- responses
class QrScanResponse(BaseModel):
    """
    Step 1 result. status is one of:
      punched    - the punch was recorded (no PIN was required)
      pin_required - step 1 passed, the kiosk must now ask for the PIN
    """

    status: Literal["punched", "pin_required"]
    event_id: int | None = None
    event_type: PunchType | None = None
    employee_id: int | None = None
    employee_name: str | None = None
    work_date: date | None = None
    punched_at: datetime | None = None
    local_time: str | None = None
    challenge_id: str | None = None
    challenge_expires_at: datetime | None = None
    message: str


class QrCredentialOut(BaseModel):
    credential_id: str
    employee_id: int
    employee_name: str
    mode: CredentialMode
    status: str
    require_pin: bool
    seq: int
    qr_payload: str | None = Field(
        None, description="The signed text to encode as a QR image. Static only."
    )
    issued_at: datetime
    expires_at: datetime | None
    last_scanned_at: datetime | None
    scan_count: int


class KioskOut(BaseModel):
    device_id: str
    label: str
    location: str | None = None
    status: str
    last_seen_at: datetime | None = None
    scan_count: int = 0
    api_key: str | None = Field(
        None, description="Only returned once, when the kiosk is registered."
    )


class ShiftOut(BaseModel):
    shift_id: int
    code: str
    name: str
    start_time: str
    end_time: str
    break_minutes: int
    grace_minutes: int
    is_overnight: bool
    assigned_employees: list[str] = Field(default_factory=list)


class AttendanceEventOut(BaseModel):
    event_id: int
    employee_id: int
    employee_name: str
    work_date: date
    event_type: str
    occurred_at: datetime
    local_time: str
    source: str
    method: str
    shift_code: str | None
    kiosk_device_id: str | None
    status: str


class ShiftHoursOut(BaseModel):
    employee_id: int
    work_date: date
    shift_id: int | None
    shift_code: str | None
    shift_name: str | None
    segments_worked: int
    hours_worked: Number
